#!/usr/bin/env python3
"""Reproduce the comparison in docs/FINDINGS.md.

    python src/compare_reference.py out/clip_features.jsonl data/DominicaCodas.csv

Everything claimed in FINDINGS.md comes out of this script. If the numbers here
stop matching that document, the document is wrong.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import iaa  # noqa: E402


def load_features(path: Path):
    """All records, including clips where no coda was found.

    Keeping those matters: they carry the audio duration and the failure rate,
    which are both reported here.
    """
    recs = []
    with path.open() as fh:
        for line in fh:
            recs.append(json.loads(line))
    return recs


def load_reference(path: Path):
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    clicks = [int(float(r["nClicks"])) for r in rows if r.get("nClicks", "").strip()]
    icis = []
    for r in rows:
        for i in range(1, 10):
            v = r.get(f"ICI{i}", "").strip()
            if v and float(v) > 0:
                icis.append(float(v))
    durs = [float(r["Duration"]) for r in rows if r.get("Duration", "").strip()]
    return clicks, icis, durs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("features", type=Path)
    ap.add_argument("reference", type=Path)
    ap.add_argument("--jitter-ms", type=float, default=10.0,
                    help="onset disagreement to test stability against")
    args = ap.parse_args(argv)

    recs = load_features(args.features)
    prim = [r["codas"][0] for r in recs if r.get("codas")]
    clicks = [len(c["clicks"]) for c in prim]
    icis = [i for c in prim for i in c["icis"]]
    durs = [c["duration"] for c in prim]
    ref_clicks, ref_icis, ref_durs = load_reference(args.reference)

    total_audio = sum(r["dur"] for r in recs if "dur" in r)
    print(f"clips with a detected coda: {len(prim)} / {len(recs)}"
          f" ({100 * len(prim) / max(1, len(recs)):.0f}%)")
    print(f"total audio: {total_audio / 60:.0f} min\n")

    def row(label, ours, theirs, fmt="{:.2f}"):
        print(f"  {label:28s} {fmt.format(ours):>9s} {fmt.format(theirs):>12s}")

    print(f"  {'':28s} {'this pipeline':>9s} {'published':>12s}")
    row("median clicks per coda", float(np.median(clicks)), float(np.median(ref_clicks)), "{:.0f}")
    row("mean clicks per coda", float(np.mean(clicks)), float(np.mean(ref_clicks)))
    row("median ICI (ms)", 1000 * float(np.median(icis)), 1000 * float(np.median(ref_icis)), "{:.0f}")
    row("median duration (s)", float(np.median(durs)), float(np.median(ref_durs)))

    over = np.mean(clicks) / np.mean(ref_clicks) - 1
    print(f"\n  click count bias: {100 * over:+.0f}% against the published distribution")
    print("  This compares distributions, not clips, so it is a weak check: two")
    print("  detectors can match a median and disagree on every clip.  For per-clip")
    print("  accuracy against known labels use src/calibrate.py.\n")

    # Stability depends on coda speed; report both regimes.
    fast = [c for c in prim if np.mean(c["icis"]) < 0.12]
    slow = [c for c in prim if np.mean(c["icis"]) >= 0.12]
    for name, group in (("fast (<120 ms ICI)", fast), ("slow (>=120 ms ICI)", slow)):
        if not group:
            continue
        vals = [iaa.stability(c["clicks"], args.jitter_ms)["survives_ici"] for c in group]
        stable = sum(iaa.stability(c["clicks"], args.jitter_ms)["stable"] for c in group)
        print(f"  {name:22s} n={len(group):5d}  survives ICI in {np.mean(vals):.2f} "
              f"of perturbations, {100 * stable / len(group):.0f}% pass the 0.9 bar")
    print(f"\n  jitter tested: {args.jitter_ms:.0f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
