#!/usr/bin/env python3
"""Recover the mapping from public audio clip -> published coda row.

The public 1,501-clip dataset ships no metadata.  But each clip is exactly one
published coda plus 0.5 s of padding at each end, so

    wav_duration == table.Duration + 1.000 s

and the match is exact to about 20 microseconds -- one sample.  This script
rebuilds that mapping and reports how much of the corpus it covers.

    python src/join.py data/dswp data/DominicaCodas.csv --out out/join.csv

Two caveats worth stating plainly:

1. The 0.5 s pad was recovered empirically, not from documentation.  It is
   consistent to a sample across 1,391 clips, which is strong evidence, but it
   is inferred.
2. Because the mapping is recoverable from duration alone, the public dataset
   leaks the label of each clip to anyone who computes it.  Treat this dataset
   as *labelled* from now on, and never evaluate a model on it as if the audio
   were unlabelled.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

PAD = 1.000       # seconds of padding in each clip, before and after the coda
TOL = 0.002       # seconds; five times looser than the observed spread


def clip_durations(audio_dir: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in sorted(audio_dir.glob("*.wav")):
        try:
            sr, x = wavfile.read(str(p))
            out[p.stem] = len(x) / float(sr)
        except Exception as exc:  # noqa: BLE001
            print(f"skip {p.name}: {exc}", file=sys.stderr)
    return out


def load_table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("Duration", "").strip()]


def match(durations: dict[str, float], rows: list[dict], tol: float = TOL,
          min_run: int = 3) -> dict[str, dict]:
    """Map clip -> table row using contiguous runs, not isolated duration hits.

    Matching each clip on duration alone is hopeless: 1,491 of 1,501 clips match
    several rows, because codas share durations (dozens are exactly 0.86 s).
    What disambiguates them is order.  Both sides are sorted by session time, so
    within a session `row = clip + constant`; a constant that holds for many
    consecutive clips at once is the thread to pull.  Rows and clips are walked
    in order and a run is extended only when the next clip's duration matches
    the next row's.
    """
    clips = sorted(durations, key=lambda c: int(c) if c.isdigit() else 0)
    cands: list[list[int]] = []
    for clip in clips:
        dur = durations[clip]
        cands.append([j for j, r in enumerate(rows)
                      if abs(dur - (float(r["Duration"]) + PAD)) <= tol])

    mapping: dict[str, dict] = {}
    used: set[int] = set()
    i = 0
    while i < len(clips):
        best = None
        for start_row in cands[i]:
            if start_row in used:
                continue
            n = 0
            while (i + n < len(clips) and (start_row + n) < len(rows)
                   and (start_row + n) in cands[i + n]):
                n += 1
            if best is None or n > best[0]:
                best = (n, start_row)
        if best and best[0] >= min_run:
            n, start_row = best
            for k in range(n):
                mapping[clips[i + k]] = rows[start_row + k]
                used.add(start_row + k)
            i += n
        else:
            i += 1

    ambiguous = len(durations) - len(mapping)
    if ambiguous:
        print(f"{ambiguous} clips left unmapped (no run of {min_run}+ matches)", file=sys.stderr)
    return mapping


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio_dir", type=Path)
    ap.add_argument("table", type=Path)
    ap.add_argument("--out", type=Path, default=Path("out/join.csv"))
    ap.add_argument("--tol", type=float, default=TOL)
    args = ap.parse_args(argv)

    durations = clip_durations(args.audio_dir)
    rows = load_table(args.table)
    mapping = match(durations, rows, args.tol)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "codaNUM", "Date", "CodaType", "nClicks", "Clan", "Unit"])
        for clip in sorted(mapping, key=lambda c: int(c) if c.isdigit() else 0):
            r = mapping[clip]
            w.writerow([clip, r["codaNUM2018"], r["Date"], r["CodaType"],
                        r["nClicks"], r["Clan"], r["Unit"]])

    frac = len(mapping) / max(1, len(durations))
    print(f"clips={len(durations)} matched={len(mapping)} ({100 * frac:.1f}%) -> {args.out}")
    if mapping:
        clans = {}
        for r in mapping.values():
            clans[r["Clan"]] = clans.get(r["Clan"], 0) + 1
        print("clans:", dict(sorted(clans.items(), key=lambda kv: -kv[1])))
        pads = np.array([durations[c] - float(r["Duration"]) for c, r in mapping.items()])
        print(f"pad: mean {pads.mean():.6f} s  sd {pads.std():.6f}  "
              f"range {pads.min():.6f}..{pads.max():.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
