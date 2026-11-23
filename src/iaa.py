#!/usr/bin/env python3
"""Inter-annotator agreement for click-level coda annotation.

Why this exists
---------------
A coda label is only worth as much as the agreement behind it.  Everyone who
publishes coda measurements should be able to say "two people labelled this the
same way, and here is how close they were".  Almost nobody does.  This module
makes that cheap.

What is measured
----------------
Onsets are times in seconds.  Two annotations are compared by matching onsets
one-to-one within a tolerance (default 30 ms -- about the width of a click
envelope at these frequencies), then:

  onset P / R / F1   did the two people find the same clicks?
  timing MAE         for matched clicks, how far apart in milliseconds?
  nClicks agreement  exact-match rate of click counts per coda
  ICI MAE            mean absolute error of inter-click intervals (ms)
  pattern agreement  agreement on a coarse ICI-pattern signature

"pattern agreement" is used instead of coda-type kappa because coda type names
are scheme-dependent (see docs/PROTOCOL.md); the pattern signature is objective
and can be mapped onto any naming scheme later.

Stability
---------
`stability()` answers a practical question: if a label is what you get from
noisy human clicks, would a slightly different human have produced the same
label?  It perturbs onsets by the observed disagreement and reports the
fraction of perturbations that leave the click count and rhythm pattern
unchanged.  A label that survives 98% of realistic perturbations is safe to
build on.  One that survives 55% is not, no matter how confident it looks.

Usage
-----
    python src/iaa.py a.json b.json          # two annotators
    python src/iaa.py a.json b.json c.json   # pairwise, all combinations
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

DEFAULT_TOL = 0.030  # seconds


def match_onsets(a: list[float], b: list[float], tol: float) -> list[tuple[int, int]]:
    """One-to-one greedy match of onsets within `tol`, earliest pair first.

    Greedy-earliest is fine here because onsets are ordered and well separated
    relative to the tolerance; it cannot produce a crossing match.
    """
    i = j = 0
    pairs: list[tuple[int, int]] = []
    while i < len(a) and j < len(b):
        d = a[i] - b[j]
        if abs(d) <= tol:
            pairs.append((i, j))
            i += 1
            j += 1
        elif d < 0:
            i += 1
        else:
            j += 1
    return pairs


def pattern_signature(icis: list[float], tol: float = 0.012) -> str:
    """Coarse, scheme-independent rhythm fingerprint.

    Each ICI is snapped to a multiple of the smallest ICI in the coda (the
    "beat"), which is how coda rhythm is described qualitatively: long-short,
    even, syncopated.  Two codas with the same beat structure share a
    signature even if their absolute tempo differs.
    """
    if not icis:
        return ""
    arr = np.asarray(icis, dtype=float)
    beat = float(np.min(arr))
    if beat <= 0:
        return ""
    return "".join(str(max(1, int(round(v / beat)))) for v in arr)


def compare_clip(
    a: dict, b: dict, tol: float = DEFAULT_TOL
) -> dict:
    """Compare one clip's annotation from two annotators.

    Each clip dict is {"clip": str, "codas": [{"clicks": [t, ...]}, ...]}.
    Only the first (primary) coda per annotator is compared unless counts
    differ, in which case the longest is used and the mismatch is recorded.
    """
    ca = a.get("codas") or []
    cb = b.get("codas") or []
    out: dict = {"clip": a.get("clip") or b.get("clip"), "n_codas_a": len(ca), "n_codas_b": len(cb)}

    if not ca or not cb:
        out.update(status="one_side_empty", f1=0.0, matching=0.0)
        return out

    # Match codas to each other by start time so multi-coda clips align.
    pairs = match_onsets([c["clicks"][0] for c in ca], [c["clicks"][0] for c in cb], toler=0.5)
    if not pairs:
        out.update(status="no_coda_match", f1=0.0)
        return out

    tp = n_a = n_b = 0
    timing_errors: list[float] = []
    ici_errors: list[float] = []
    counts_match = 0
    pattern_match = 0
    for ia, ib in pairs:
        ca_clicks = ca[ia]["clicks"]
        cb_clicks = cb[ib]["clicks"]
        m = match_onsets(ca_clicks, cb_clicks, tol)
        tp += len(m)
        n_a += len(ca_clicks)
        n_b += len(cb_clicks)
        timing_errors += [abs(ca_clicks[i] - cb_clicks[j]) for i, j in m]

        if len(ca_clicks) == len(cb_clicks):
            counts_match += 1
        if len(m) >= 2:
            ia_icis = np.diff([ca_clicks[i] for i, _ in m])
            ib_icis = np.diff([cb_clicks[j] for _, j in m])
            k = min(len(ia_icis), len(ib_icis))
            if k:
                ici_errors += list(np.abs(ia_icis[:k] - ib_icis[:k]))
            pa = pattern_signature(list(np.diff(ca_clicks)))
            pb = pattern_signature(list(np.diff(cb_clicks)))
            if pa and pa == pb:
                pattern_match += 1

    prec = tp / n_a if n_a else 0.0
    rec = tp / n_b if n_b else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    out.update(
        status="ok",
        matching=len(pairs),
        onset_precision=round(prec, 4),
        onset_recall=round(rec, 4),
        f1=round(f1, 4),
        timing_mae_ms=round(1000 * float(np.mean(timing_errors)), 2) if timing_errors else None,
        timing_p95_ms=round(1000 * float(np.percentile(timing_errors, 95)), 2) if timing_errors else None,
        n_clicks_a=n_a,
        n_clicks_b=n_b,
        counts_match=counts_match,
        icis_compared=len(ici_errors),
        ici_mae_ms=round(1000 * float(np.mean(ici_errors)), 2) if ici_errors else None,
        pattern_match=pattern_match,
    )
    return out


def summarise(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("status") == "ok"]
    n = len(rows)
    if not ok:
        return {"clips": n, "comparable": 0}
    counts = sum(r["counts_match"] for r in ok)
    pats = sum(r["pattern_match"] for r in ok)
    tm = [r["timing_mae_ms"] for r in ok if r.get("timing_mae_ms") is not None]
    im = [r["ici_mae_ms"] for r in ok if r.get("ici_mae_ms") is not None]
    return {
        "clips": n,
        "comparable": len(ok),
        "mean_onset_f1": round(float(np.mean([r["f1"] for r in ok])), 4),
        "onset_f1_10th_pct": round(float(np.percentile([r["f1"] for r in ok], 10)), 4),
        "clips_below_f1_0_9": sum(1 for r in ok if r["f1"] < 0.9),
        "click_count_agreement": round(counts / len(ok), 4),
        "pattern_agreement": round(pats / len(ok), 4),
        "median_timing_mae_ms": round(float(np.median(tm)), 2) if tm else None,
        "median_ici_mae_ms": round(float(np.median(im)), 2) if im else None,
    }


def stability(click_times: list[float], jitter_ms: float, trials: int = 200, seed: int = 0) -> dict:
    """Fraction of realistic perturbations that leave the label unchanged."""
    rng = np.random.default_rng(seed)
    t = np.asarray(click_times, dtype=float)
    base_n = len(t)
    base_pat = pattern_signature(list(np.diff(t)))
    keep_n = keep_pat = 0
    sigma = jitter_ms / 1000.0
    for _ in range(trials):
        pert = np.sort(t + rng.normal(0, sigma, size=t.shape))
        if np.any(np.diff(pert) <= 0):  # onsets swapped; degenerate
            continue
        keep_n += len(pert) == base_n
        keep_pat += pattern_signature(list(np.diff(pert))) == base_pat
    return {
        "trials": trials,
        "n_clicks": base_n,
        "pattern": base_pat,
        "survives_click_count": round(keep_n / trials, 3),
        "survives_pattern": round(keep_pat / trials, 3),
        "stable": (keep_pat / trials) >= 0.9,
    }


def _load(p: Path) -> dict[str, dict]:
    raw = json.loads(p.read_text())
    items = raw if isinstance(raw, list) else raw.get("clips", raw)
    return {str(c["clip"]): c for c in items}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("annotations", nargs="+", type=Path)
    ap.add_argument("--tol-ms", type=float, default=DEFAULT_TOL * 1000)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    docs = [(p.stem, _load(p)) for p in args.annotations]
    report: dict = {"tolerance_ms": args.tol_ms, "pairs": {}}
    for (na, da), (nb, db) in itertools.combinations(docs, 2):
        shared = sorted(set(da) & set(db))
        rows = [compare_clip(da[c], db[c], tol=args.tol_ms / 1000.0) for c in shared]
        report["pairs"][f"{na} vs {nb}"] = {
            "summary": summarise(rows),
            "per_clip": rows,
        }

    print(json.dumps({k: v["summary"] for k, v in report["pairs"].items()}, indent=2))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2))
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
