#!/usr/bin/env python3
"""Click-level extraction for sperm whale coda clips.

Design principle: emit *measurements*, never type names.  Coda "types" are
derived downstream under an explicitly declared naming scheme (see
docs/PROTOCOL.md), because the field uses several incompatible schemes.

Output per clip: click onset times -> nClicks, ICIs, duration.

Calibration knobs are exposed on the command line (`--max-ici`,
`--rel-floor-db`, `--discard-oversized`) so that the experiments reported in
docs/FINDINGS.md can be re-run rather than taken on trust.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile
from scipy.signal import butter, sosfiltfilt, hilbert, find_peaks


# Recording-condition profiles.  Far-field (towed/boat hydrophone) clips have
# multipath, reverberation and lower SNR; animal-borne tag clips are near-field
# and much hotter, but carry flow noise.
PROFILES: dict[str, dict] = {
    "farfield": dict(
        band=(2000.0, 20000.0),
        env_lp=800.0,
        thr_k=3.0,          # candidate over-generation; two-means split follows
        # Peaks this far below the loudest click *in their own run* are echoes
        # and reverberation, not clicks.  Applied per run, never per clip: a
        # clip-global floor deletes a quiet coda sitting next to a loud one.
        rel_floor_db=-12.0,
        min_gap=0.020,      # merges the ~2-5 ms multi-pulse train of one click
        # Calibrated, not guessed: in the published Dominica table the largest
        # observed inter-click interval inside a coda is 0.80 s and the 99th
        # percentile is 0.49 s.  A looser split gap chains separate codas
        # together and inflates click counts (measured: 1.0 s gave median 8
        # clicks against 5 in the reference table).
        max_ici=0.55,
        min_clicks=3,
        max_clicks=10,      # Dominica scheme documents 1-10 clicks per coda
        min_ici=0.025,      # closer than this is one click, not two
    ),
    "tag": dict(
        band=(1000.0, 20000.0),
        env_lp=1200.0,
        thr_k=3.0,
        rel_floor_db=-12.0,
        min_gap=0.018,
        max_ici=0.55,
        max_clicks=10,
        min_clicks=3,
        min_ici=0.025,
    ),
}


@dataclass
class Coda:
    t0: float
    clicks: list[float]
    icis: list[float]
    duration: float
    peak_snr: float
    profile: str
    train_like: bool = False

    @property
    def n_clicks(self) -> int:
        return len(self.clicks)


def load_mono(path: Path) -> tuple[np.ndarray, int]:
    sr, x = wavfile.read(str(path))
    if x.ndim > 1:
        x = x.astype(np.float64).mean(axis=1)
    else:
        x = x.astype(np.float64)
    # int16 full scale; tolerate float files already in [-1, 1]
    if np.max(np.abs(x)) > 1.5:
        x = x / 32768.0
    return x, sr


def bandpass(x: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    hi = min(hi, 0.45 * sr)
    sos = butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
    return sosfiltfilt(sos, x)


def envelope(x: np.ndarray, sr: int, lp: float) -> np.ndarray:
    env = np.abs(hilbert(x))
    win = max(1, int(sr / lp))
    kernel = np.ones(win) / win
    return np.convolve(env, kernel, mode="same")


def two_means_threshold(v: np.ndarray, iters: int = 50) -> float:
    """Split log-heights into a quiet and a loud mode; return the boundary.

    Coda clicks are typically well above the background echolocation /
    flow-noise floor within a cut clip, so a two-mode split adapts per clip
    where a single global multiplier does not (clips differ by >10x in level).
    """
    lv = np.log(np.asarray(v, dtype=float) + 1e-30)
    lo, hi = np.percentile(lv, 10), np.percentile(lv, 90)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        a, b = lv[lv <= mid], lv[lv > mid]
        if a.size == 0 or b.size == 0:
            break
        nlo, nhi = a.mean(), b.mean()
        if abs(nlo - lo) < 1e-12 and abs(nhi - hi) < 1e-12:
            break
        lo, hi = nlo, nhi
    return float(np.exp(0.5 * (lo + hi)))


def is_train(icis: list[float], min_n: int = 8, cv_max: float = 0.20) -> bool:
    """Regular, sustained click runs are echolocation, not codas.

    Codas are rhythmic but structured (rubato/ornamentation vary the spacing);
    echolocation trains sit at a near-constant inter-click interval.  Flagging
    (rather than silently dropping) keeps the decision auditable.
    """
    if len(icis) < min_n:
        return False
    arr = np.asarray(icis, dtype=float)
    return float(arr.std() / (arr.mean() + 1e-12)) < cv_max


def _merge_pulses(times: np.ndarray, heights: np.ndarray, min_ici: float):
    """Collapse peaks closer than `min_ici` into one click (keeps the loudest).

    A sperm whale click is a multi-pulse burst.  Merging here, rather than
    discarding a whole coda when two pulses survive, is the difference between
    losing a fifth of the clips and losing none.
    """
    if times.size == 0:
        return times, heights
    keep_t, keep_h = [times[0]], [heights[0]]
    for t, h in zip(times[1:], heights[1:]):
        if t - keep_t[-1] < min_ici:
            if h > keep_h[-1]:
                keep_t[-1], keep_h[-1] = t, h
        else:
            keep_t.append(t)
            keep_h.append(h)
    return np.asarray(keep_t), np.asarray(keep_h)


def _runs(times: np.ndarray, heights: np.ndarray, max_ici: float):
    """Yield (times, heights) for each maximal group separated by > max_ici."""
    if times.size == 0:
        return
    start = 0
    for i in range(1, times.size + 1):
        if i == times.size or times[i] - times[i - 1] > max_ici:
            yield times[start:i], heights[start:i]
            start = i


def _split_oversized(times: np.ndarray, heights: np.ndarray, max_clicks: int, depth: int = 0):
    """Break runs longer than a coda can be, at their widest gap.

    Cutting at the widest gap keeps the rhythmically natural boundaries.
    Discarding oversized runs instead is tempting and wrong: echolocation
    clicks trail codas constantly, so most clips contain one long run and would
    yield nothing (measured: 339 of 1501 clips lose their coda that way).
    """
    if times.size <= max_clicks or depth > 200:
        yield times, heights
        return
    gaps = np.diff(times)
    cut = int(np.argmax(gaps))
    yield from _split_oversized(times[: cut + 1], heights[: cut + 1], max_clicks, depth + 1)
    yield from _split_oversized(times[cut + 1 :], heights[cut + 1 :], max_clicks, depth + 1)


def peak_candidates(x: np.ndarray, sr: int, p: dict):
    """All peaks above the noise floor, before any coda logic.

    Split out from `detect_codas` so that calibration can compute this once per
    clip and then sweep the coda-level parameters in memory, instead of
    re-filtering 45 minutes of audio for every setting tried.
    """
    y = bandpass(x, sr, *p["band"])
    env = envelope(y, sr, p["env_lp"])
    med = float(np.median(env))
    mad = float(np.median(np.abs(env - med))) or float(np.std(env)) or 1e-12
    thr = med + p["thr_k"] * 1.4826 * mad
    idx, props = find_peaks(
        env,
        height=thr,
        distance=max(1, int(p["min_gap"] * sr)),
        prominence=0.5 * (thr - med),
    )
    return idx / float(sr), props["peak_heights"], med


def codas_from_candidates(times: np.ndarray, heights: np.ndarray, med: float,
                          p: dict, profile: str = "farfield",
                          discard_oversized: bool = False) -> list[Coda]:
    """Apply coda-level logic (split, floor, group) to raw peaks."""
    if times.size < 3:
        return []

    # No clip-global amplitude gate: an earlier version thresholded across the
    # whole clip and silently deleted a quiet coda sharing it with a loud one.
    # Level is judged per run instead, below.
    times, heights = _merge_pulses(times, heights, p["min_ici"])

    codas: list[Coda] = []
    for run_t, run_h in _runs(times, heights, p["max_ici"]):
        # Split loud from quiet *within this run*.  A clip-wide version of this
        # gate deleted a quiet coda sharing a clip with a loud one; dropping it
        # altogether floods the output with noise fragments (2,849 candidate
        # codas instead of ~1,800).  Per run is the honest middle.
        if run_h.size >= 6:
            cut = two_means_threshold(run_h)
            keep = run_h > cut
            run_t, run_h = run_t[keep], run_h[keep]
        if run_t.size < 3:
            continue
        # Echo floor, per run: measured against this run's own loudest click.
        floor = float(run_h.max()) * 10 ** (p["rel_floor_db"] / 20.0)
        keep = run_h >= floor
        run_t, run_h = run_t[keep], run_h[keep]
        if run_t.size < 3:
            continue
        # Removing peaks can open gaps wider than max_ici; regroup before use.
        for seg_t, seg_h in _runs(run_t, run_h, p["max_ici"]):
            if discard_oversized and seg_t.size > p["max_clicks"]:
                continue
            for coda_t, coda_h in _split_oversized(seg_t, seg_h, p["max_clicks"]):
                if coda_t.size < p["min_clicks"]:
                    continue
                t = [round(float(v), 5) for v in coda_t]
                icis = [round(t[i + 1] - t[i], 5) for i in range(len(t) - 1)]
                codas.append(
                    Coda(
                        t0=t[0],
                        clicks=t,
                        icis=icis,
                        duration=round(t[-1] - t[0], 5),
                        peak_snr=round(float(coda_h.max() / (med + 1e-12)), 2),
                        profile=profile,
                        train_like=is_train(icis),
                    )
                )

    # Strongest coda first: clips are cut to contain at least one, and ranking
    # by click count would actively select for merged codas and trains.
    codas.sort(key=lambda c: c.peak_snr, reverse=True)
    return codas


def resolve_profile(profile: str = "farfield", max_ici: float | None = None,
                    rel_floor_db: float | None = None, **overrides) -> dict:
    p = dict(PROFILES[profile])
    if max_ici is not None:
        p["max_ici"] = max_ici
    if rel_floor_db is not None:
        p["rel_floor_db"] = rel_floor_db
    p.update({k: v for k, v in overrides.items() if v is not None})
    return p


def detect_codas(
    x: np.ndarray,
    sr: int,
    profile: str = "farfield",
    max_ici: float | None = None,
    rel_floor_db: float | None = None,
    discard_oversized: bool = False,
    **overrides,
) -> list[Coda]:
    """Return candidate codas in a clip, strongest first."""
    p = resolve_profile(profile, max_ici, rel_floor_db, **overrides)
    times, heights, med = peak_candidates(x, sr, p)
    return codas_from_candidates(times, heights, med, p, profile, discard_oversized)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio_dir", type=Path)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="farfield")
    ap.add_argument("--out", type=Path, default=Path("out/clip_features.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-ici", type=float, default=None,
                    help="gap that ends a coda (default: profile value, 0.55 s)")
    ap.add_argument("--rel-floor-db", type=float, default=None,
                    help="drop peaks this far below their run's loudest click")
    ap.add_argument("--discard-oversized", action="store_true",
                    help="drop over-long runs instead of splitting them (for the "
                         "experiment in docs/FINDINGS.md; not recommended)")
    args = ap.parse_args(argv)

    files = sorted(args.audio_dir.glob("*.wav"),
                   key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"no wav files in {args.audio_dir}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_coda = 0
    with args.out.open("w") as fh:
        for path in files:
            try:
                x, sr = load_mono(path)
                codas = detect_codas(
                    x, sr, args.profile,
                    max_ici=args.max_ici,
                    rel_floor_db=args.rel_floor_db,
                    discard_oversized=args.discard_oversized,
                )
            except Exception as exc:  # keep going; log the failure
                fh.write(json.dumps({"clip": path.stem, "error": str(exc)}) + "\n")
                continue
            rec = {
                "clip": path.stem,
                "sr": sr,
                "dur": round(len(x) / sr, 4),
                "n_codas": len(codas),
                "codas": [asdict(c) for c in codas],
            }
            fh.write(json.dumps(rec) + "\n")
            n_ok += 1
            n_coda += len(codas)

    print(f"clips={n_ok} codas={n_coda} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
