#!/usr/bin/env python3
"""Self-checks for the agreement harness, on synthetic annotations.

The point is not coverage; it is that the scoring code cannot silently report
nonsense. Each case has a known right answer.

    python tests/test_iaa.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import iaa  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main():
    # Identical annotations must score perfectly.
    clip = {"clip": "1", "codas": [{"clicks": [0.10, 0.35, 0.52, 0.68, 0.80]}]}
    d = iaa.compare_clip(clip, clip)
    check("identical F1 == 1", d["f1"] == 1.0, str(d["f1"]))
    check("identical timing error == 0", d["timing_mae_ms"] == 0.0)

    # Small jitter should stay high; a dropped click must cost recall.
    rng = np.random.default_rng(0)
    base = [0.10, 0.35, 0.52, 0.68, 0.80]
    jit = [round(v + float(rng.normal(0, 0.008)), 4) for v in base]
    d = iaa.compare_clip({"clip": "1", "codas": [{"clicks": base}]},
                         {"clip": "1", "codas": [{"clicks": jit}]})
    check("8 ms jitter keeps F1 > 0.9", d["f1"] > 0.9, str(d["f1"]))
    check("8 ms jitter timing MAE < 15 ms", d["timing_mae_ms"] < 15, str(d["timing_mae_ms"]))

    dropped = {"clip": "1", "codas": [{"clicks": base[:-1]}]}
    d = iaa.compare_clip({"clip": "1", "codas": [{"clicks": base}]}, dropped)
    check("dropped click detected", d["f1"] < 0.95, str(d["f1"]))
    check("dropped click counted as count mismatch", d["counts_match"] == 0)

    # A click far outside tolerance must not match.
    far = {"clip": "1", "codas": [{"clicks": [v + 0.2 for v in base]}]}
    # The coda is still the same coda (coda starts within 0.5 s), but no click
    # agrees, so agreement must be zero rather than the clip being discarded.
    d = iaa.compare_clip({"clip": "1", "codas": [{"clicks": base}]}, far)
    check("200 ms offset scores zero agreement", d["f1"] == 0.0, str(d["f1"]))

    # Rhythm code: the published 1+1+3 shape must be distinguishable from even clicks.
    p113 = iaa.pattern_signature([0.288, 0.262, 0.17, 0.14])
    even = iaa.pattern_signature([0.08, 0.077, 0.076, 0.096])
    check("1+1+3 differs from even coda", p113 != even, f"{p113} vs {even}")

    # Two annotators about 6 ms apart on the same coda must agree on its shape.
    # Regression: at a 1.8x long/short threshold this pair disagreed, because
    # one interval sat just under the boundary and the other just over.
    a = [0.104, 0.352, 0.518, 0.681, 0.803]
    b = [0.110, 0.348, 0.526, 0.675, 0.810]
    d = iaa.compare_clip({"clip": "1", "codas": [{"clicks": a}]},
                         {"clip": "1", "codas": [{"clicks": b}]})
    check("6 ms jitter agrees on rhythm shape",
          d["counts_match"] == 1 and d["pattern_match"] == 1,
          f"pattern_match={d['pattern_match']}")

    # Stability must fall with jitter, and slow codas must be more stable than fast.
    slow = iaa.stability([0.0, 0.29, 0.58, 0.87], jitter_ms=10.0)
    fast = iaa.stability([0.0, 0.08, 0.16, 0.24], jitter_ms=10.0)
    check("slow coda stable at 10 ms", slow["stable"], str(slow["survives_ici"]))
    check("fast coda less stable than slow", fast["survives_ici"] < slow["survives_ici"],
          f"{fast['survives_ici']} < {slow['survives_ici']}")

    print()
    if FAILS:
        print(f"{len(FAILS)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
