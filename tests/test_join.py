#!/usr/bin/env python3
"""Self-checks for the audio-to-label join, on synthetic durations.

    python tests/test_join.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import join as J  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main():
    # 40 rows whose Durations are mostly distinct ; clips are row+pad.
    rows = [{"Duration": f"{1.0 + i * 0.01:.3f}", "codaNUM2018": str(1000 + i)} for i in range(40)]
    durs = {str(i + 1): 1.0 + float(rows[i]["Duration"]) for i in range(10)}
    m = J.match(durs, rows)
    check("clean run is mapped", len(m) == 10, str(len(m)))

    # One-to-one: no published row may be claimed by two clips.
    used = [r["codaNUM2018"] for r in m.values()]
    check("no row assigned twice", len(used) == len(set(used)))

    # Crossing runs must not steal each other's rows.  Two interleaved runs
    # whose durations overlap: the old code extended without checking `used`.
    rows2 = [{"Duration": f"{1.0 + i * 0.01:.3f}", "codaNUM2018": str(2000 + i)} for i in range(20)]
    durs2 = {}
    for k in range(8):
        durs2[str(2 * k + 1)] = 1.0 + float(rows2[2 * k]["Duration"])
        durs2[str(2 * k + 2)] = 1.0 + float(rows2[2 * k + 1]["Duration"])
    m2 = J.match(durs2, rows2, min_run=3)
    used2 = [r["codaNUM2018"] for r in m2.values()]
    check("interleaved clips stay one-to-one", len(used2) == len(set(used2)),
          f"{len(used2)} clips, {len(set(used2))} rows")

    # A single isolated match is chance and must be refused.
    rows3 = [{"Duration": "2.500", "codaNUM2018": "1"}]
    m3 = J.match({"7": 3.5}, rows3, min_run=5)
    check("isolated single match refused", len(m3) == 0, str(len(m3)))

    print()
    if FAILS:
        print(f"{len(FAILS)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
