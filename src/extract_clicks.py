#!/usr/bin/env python3
"""Click-level extraction for sperm whale coda clips.

Design principle: emit *measurements*, never type names.  Coda "types" are
derived downstream under an explicitly declared naming scheme (see
docs/PROTOCOL.md), because the field uses several incompatible schemes.

Output per detected coda: click onset times -> nClicks, ICIs, duration.
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
        # Peaks more than this far below the loudest click in the run are
        # echoes and reverberation, not clicks.  Measured: without a floor, 64%
        # of surviving peaks sit below -6 dB and 53% below -10 dB, and runs
        # reach a median of 26 peaks -- a decaying echo tail, not a coda.
        rel_floor_db=-12.0,
        min_gap=0.020,      # merges the ~2-5 ms multi-pulse train of one click
        # Calibrated, not guessed: in the published Dominica table the largest
        # observed inter-click interval inside a coda is 0.80 s and the 99th
        # percentile is 0.49 s.  A looser split gap chains separate codas
        # together and inflates click counts (verified: 1.0 s gave median 8
        # clicks vs 5 in the reference table).
        max_ici=0.55,
        min_clicks=3,
        max_clicks=10,      # Dominica scheme documents 1-10 clicks per coda
        min_ici=0.025,
    ),
    "tag": dict(
        band=(1000.0, 20000.0),
        env_lp=1200.0,
        thr_k=3.0,
        rel_floor_db=-12.0,
        min_gap=0.018,
        max_ici=0.55,
        min_clicks=3,
        max_clicks=10,
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
    if np.issubdtype(np.asarray(x).dtype, np.floating) and np.max(np.abs(x)) > 1.5:
        x = x / 32768.0
    elif np.max(np.abs(x)) > 1.5:
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


def detect_codas(x: np.ndarray, sr: int, profile: str = "farfield") -> list[Coda]:
    p = PROFILES[profile]
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
    if idx.size < 3:
        return []

    heights = props["peak_heights"]
    if idx.size >= 6:
        cut = two_means_threshold(heights)
        keep = heights > cut
        idx, heights = idx[keep], heights[keep]
    if idx.size < 3:
        return []

    floor = float(heights.max()) * 10 ** (p["rel_floor_db"] / 20.0)
    keep = heights >= floor
    idx, heights = idx[keep], heights[keep]
    if idx.size < 3:
        return []

    times = idx / float(sr)

    # Group into candidate runs on inter-click gaps, then break runs that are
    # longer than a coda can be.  Cutting at the widest gap keeps the
    # rhythmically natural boundaries.  Discarding oversized runs instead is
    # tempting and wrong: echolocation clicks trail codas constantly, so most
    # clips contain one long run and would yield nothing (measured: 734 of 1501
    # clips lost their coda that way).
    runs: list[list[int]] = [[0]]
    for i in range(1, len(times)):
        if times[i] - times[i - 1] <= p["max_ici"]:
            runs[-1].append(i)
        else:
            runs.append([i])

    def split_oversized(run: list[int]) -> list[list[int]]:
        if len(run) <= p["max_clicks"]:
            return [run]
        gaps = [times[b] - times[a] for a, b in zip(run, run[1:])]
        cut = int(np.argmax(gaps))
        left, right = run[: cut + 1], run[cut + 1 :]
        if not left or not right:
            return [run]
        return split_oversized(left) + split_oversized(right)

    groups: list[list[int]] = []
    for run in runs:
        groups.extend(split_oversized(run))

    codas: list[Coda] = []
    for g in groups:
        if len(g) < p["min_clicks"]:
            continue
        t = [float(times[i]) for i in g]
        icis = [round(t[i + 1] - t[i], 5) for i in range(len(t) - 1)]
        if icis and min(icis) < p["min_ici"]:
            continue
        codas.append(
            Coda(
                t0=round(t[0], 5),
                clicks=[round(v, 5) for v in t],
                icis=icis,
                duration=round(t[-1] - t[0], 5),
                peak_snr=round(float(heights[g].max() / (med + 1e-12)), 2),
                profile=profile,
                train_like=is_train(icis),
            )
        )
    # Keep the strongest coda; clips are cut to contain at least one.
    codas.sort(key=lambda c: c.peak_snr, reverse=True)
    return codas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio_dir", type=Path)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="farfield")
    ap.add_argument("--out", type=Path, default=Path("out/clip_features.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    files = sorted(args.audio_dir.glob("*.wav"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
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
                codas = detect_codas(x, sr, args.profile)
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
