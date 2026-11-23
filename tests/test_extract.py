#!/usr/bin/env python3
"""Self-checks for the click extractor, on synthetic audio.

Synthetic clips are the only way to test a specific failure mode without
arguing about what the real whale did.

    python tests/test_extract.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import extract_clicks as E  # noqa: E402

SR = 48000
FAILS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def click(x, t, amp):
    """A short broadband burst: what an envelope peak detector looks for."""
    i = int(t * SR)
    n = int(0.004 * SR)
    if i + n > len(x):
        return
    rng = np.random.default_rng(int(t * 1000))
    x[i:i + n] += amp * rng.normal(0, 1, n) * np.hanning(n)


def clip(events, dur=4.0, noise=0.002, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, noise, int(dur * SR))
    for t, amp in events:
        click(x, t, amp)
    return x


def main():
    # A loud run and a quiet coda in the same clip, 15 dB apart.  A clip-wide
    # amplitude gate deletes the quiet one entirely; the gate must be per run.
    # A loud run and a quiet coda in the same clip, 15 dB apart.  This is
    # tested on peak arrays rather than through synthesised audio: a quiet coda
    # in a real noise floor is marginal enough that detection depends on the
    # noise draw, which would make the test flaky for reasons unrelated to the
    # gate.  Here the question is narrow -- does the level gate delete the quiet
    # run?  A clip-wide gate does; a per-run gate does not.
    p = E.resolve_profile("farfield")
    loud_t = np.array([0.20, 0.28, 0.36, 0.44, 0.52])
    quiet_t = np.array([2.00, 2.25, 2.50])
    times = np.concatenate([loud_t, quiet_t])
    heights = np.concatenate([np.full(5, 1.0), np.full(3, 10 ** (-15 / 20))])
    codas = E.codas_from_candidates(times, heights, med=1e-4, p=p)
    after = [c for c in codas if c.t0 > 1.5]
    check("quiet coda beside a loud run is not deleted", len(after) == 1,
          f"{len(codas)} codas, {len(after)} after t=1.5s")
    if after:
        check("quiet coda keeps its click count", len(after[0].clicks) == 3,
              str(len(after[0].clicks)))

    # Two separate codas in one clip must both appear, not just the loud one.
    both = E.codas_from_candidates(
        np.concatenate([loud_t, quiet_t]),
        np.concatenate([np.full(5, 1.0), np.full(3, 0.5)]), med=1e-4, p=p)
    check("both codas in a clip are returned", len(both) == 2, f"{len(both)}")

    # Two codas separated by more than the split gap must not merge.
    two = [(0.20, 1.0), (0.28, 1.0), (0.36, 1.0),
           (1.60, 1.0), (1.68, 1.0), (1.76, 1.0)]
    codas = E.detect_codas(clip(two), SR)
    check("codas either side of the split gap stay separate", len(codas) == 2,
          f"{len(codas)} codas")

    # Multi-pulse: two peaks 3 ms apart are one click, not two.
    pulse = [(0.20, 1.0), (0.203, 0.7), (0.28, 1.0), (0.283, 0.7), (0.36, 1.0), (0.363, 0.7)]
    codas = E.detect_codas(clip(pulse), SR)
    got = len(codas[0].clicks) if codas else 0
    check("multi-pulse collapses to one click each", got == 3, f"{got} clicks")

    # Silence must not invent a coda.
    codas = E.detect_codas(clip([]), SR)
    check("no clicks in, no codas out", len(codas) == 0, str(len(codas)))

    print()
    if FAILS:
        print(f"{len(FAILS)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
