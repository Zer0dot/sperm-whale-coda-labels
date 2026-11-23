#!/usr/bin/env python3
"""Measure the detector against known labels, and choose its settings.

This exists because the public audio turns out to be labelled: every clip is one
published coda padded by 0.5 s at each end (see src/join.py).  That gives 1,391
clips with a published click count, which is the only honest way to calibrate --
matching a marginal distribution says nothing about per-clip accuracy.

    python src/calibrate.py data/dswp data/DominicaCodas.csv --train-frac 0.3

Splits the clips into train and validation, sweeps the coda-level parameters on
train, and reports the chosen setting on validation.  Peak detection is computed
once per clip, so the sweep is cheap.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_clicks as E  # noqa: E402
import join as J  # noqa: E402


def evaluate(clips, cache, truth, window: bool) -> dict:
    """Click-count accuracy of the primary coda over a set of clips."""
    exact = within1 = 0
    errs: list[float] = []
    for c in clips:
        times, heights, med = cache[c]
        p = cache["_p"]
        codas = E.codas_from_candidates(times, heights, med, p)
        if window:
            dur = cache[c + ":dur"]
            lo, hi = 0.5 - 0.02, 0.5 + (dur - 1.0) + 0.02
            clicks = sorted({t for k in codas for t in k.clicks if lo <= t <= hi})
            k = len(clicks)
        else:
            k = len(codas[0].clicks) if codas else 0
        t = truth[c]
        exact += k == t
        within1 += abs(k - t) <= 1
        errs.append(k - t)
    n = max(1, len(clips))
    return {
        "n": len(clips),
        "exact": round(exact / n, 4),
        "within1": round(within1 / n, 4),
        "bias": round(float(np.mean(errs)), 3),
        "mae": round(float(np.mean(np.abs(errs))), 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio_dir", type=Path)
    ap.add_argument("table", type=Path)
    ap.add_argument("--train-frac", type=float, default=0.3)
    ap.add_argument("--limit", type=int, default=0, help="cap clips (0 = all)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    rows = J.load_table(args.table)
    durations = J.clip_durations(args.audio_dir)
    mapping = J.match(durations, rows)
    truth = {c: int(r["nClicks"]) for c, r in mapping.items()}
    clips = sorted(truth, key=lambda c: int(c) if c.isdigit() else 0)
    if args.limit:
        clips = clips[: args.limit]
    print(f"labelled clips available: {len(clips)}")

    cache = {}
    for c in clips:
        x, sr = E.load_mono(args.audio_dir / f"{c}.wav")
        p0 = E.resolve_profile("farfield")
        times, heights, med = E.peak_candidates(x, sr, p0)
        cache[c] = (times, heights, med)
        cache[c + ":dur"] = durations[c]
    print(f"precomputed peaks for {len(clips)} clips")

    rng = np.random.default_rng(args.seed)
    order = rng.permutation(len(clips))
    n_train = max(1, int(args.train_frac * len(clips)))
    train = [clips[i] for i in order[:n_train]]
    val = [clips[i] for i in order[n_train:]]

    results = []
    for floor in (-99, -24, -18, -12, -6):
        for min_ici in (0.015, 0.025, 0.040, 0.060):
            for thr_k in (2.5, 3.0, 3.5):
                p = E.resolve_profile("farfield", rel_floor_db=float(floor),
                                      min_ici=min_ici, thr_k=thr_k)
                cache["_p"] = p
                m = evaluate(train, cache, truth, window=True)
                results.append((m["exact"], m["within1"], floor, min_ici, thr_k, m))
    results.sort(key=lambda r: (r[0], r[1]), reverse=True)

    print("\ntop settings on train (windowed click count):")
    for exact, w1, floor, mi, tk, m in results[:5]:
        print(f"  exact {100 * exact:5.1f}%  within1 {100 * w1:5.1f}%  "
              f"floor={floor:4d} min_ici={mi:.3f} thr_k={tk:.1f}  bias {m['bias']:+.2f}")

    best = results[0]
    p = E.resolve_profile("farfield", rel_floor_db=float(best[2]),
                          min_ici=best[3], thr_k=best[4])
    cache["_p"] = p
    print(f"\nvalidation on {len(val)} held-out clips, whole-clip primary coda:")
    print("  ", evaluate(val, cache, truth, window=False))
    print("\nvalidation, clicks inside the padded coda window:")
    print("  ", evaluate(val, cache, truth, window=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
