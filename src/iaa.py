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
  nClicks agreement  exact-match rate of click counts on matched codas
  ICI MAE            mean absolute error of inter-click intervals (ms)
  pattern agreement  agreement on a coarse long/short rhythm code

Precision and recall are computed over *every* coda either annotator marked, not
just the ones that paired up.  A coda one annotator marked and the other missed
is a recall failure, and scoring only matched pairs would report perfect
agreement for it.

Rhythm codes are reported but not used as the stability criterion; see
`stability()`.

Usage
-----
    python src/iaa.py a.json b.json          # two annotators
    python src/iaa.py a.json b.json c.json   # pairwise, all combinations

Inputs may be a JSON object with a "clips" list (what tools/marker.html exports)
or the JSONL that src/extract_clicks.py writes.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

DEFAULT_TOL = 0.030   # seconds, onset match
CODA_TOL = 0.60       # seconds, coda-pair match; must exceed the 0.55 s split gap
MAX_ICI = 0.55        # keep in step with extract_clicks / docs/PROTOCOL.md


def match_onsets(a: list[float], b: list[float], tol: float) -> list[tuple[int, int]]:
    """One-to-one greedy match of ordered onsets within `tol`."""
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


def pattern_signature(icis: list[float], ratio: float = 1.6) -> str:
    """Coarse rhythm fingerprint: long/short per interval.

    Each ICI is coded 1 if it is at least `ratio` times the shortest interval in
    the coda, else 0.  This is the shape coda names describe qualitatively --
    `1+1+3` is "long, long, short, short" -- without committing to a scheme.

    The ratio is 1.6 rather than 1.8 because at 1.8 two annotators 6 ms apart on
    the same coda disagreed: one interval sat just under the boundary and the
    other just over.  At 1.6 they agree and 1+1+3 is still distinguishable from
    an evenly spaced coda.

    Reported for context only.  Do not use it as an agreement gate: a discrete
    code has boundaries to land on, and landing on one says more about the code
    than about the annotators.
    """
    if not icis:
        return ""
    arr = np.asarray(icis, dtype=float)
    ref = float(np.min(arr))
    if ref <= 0:
        return ""
    return "".join("1" if v >= ratio * ref else "0" for v in arr)


def groups_from_marks(marks: list[float]) -> list[dict]:
    """Split a flat list of onsets into codas on gaps wider than MAX_ICI."""
    out: list[dict] = []
    cur: list[float] = []
    for t in sorted(marks):
        if cur and t - cur[-1] > MAX_ICI:
            out.append({"clicks": cur})
            cur = []
        cur.append(t)
    if cur:
        out.append({"clicks": cur})
    return out


def _codas(clip: dict) -> list[dict]:
    """Codas for a clip, tolerating either 'codas' or a bare 'marks' list."""
    raw = clip.get("codas")
    if raw:
        return [c for c in raw if c.get("clicks")]
    marks = clip.get("marks")
    if marks:
        return groups_from_marks(marks)
    return []


def compare_clip(a: dict, b: dict, tol: float = DEFAULT_TOL) -> dict:
    """Compare one clip's annotation from two annotators."""
    ca, cb = _codas(a), _codas(b)
    out: dict = {
        "clip": a.get("clip") or b.get("clip"),
        "n_codas_a": len(ca),
        "n_codas_b": len(cb),
        "unmatched_codas": 0,
        "counts_match": 0,
        "pattern_match": 0,
        "pairs": 0,
    }

    # Every click either annotator marked is in the denominator -- including
    # when one side marked nothing, so the summary click totals stay honest.
    n_a = sum(len(c["clicks"]) for c in ca)
    n_b = sum(len(c["clicks"]) for c in cb)

    if not ca or not cb:
        out.update(status="one_side_empty", f1=0.0, onset_precision=0.0,
                   onset_recall=0.0, n_clicks_a=n_a, n_clicks_b=n_b)
        return out

    pairs = match_onsets([c["clicks"][0] for c in ca], [c["clicks"][0] for c in cb], CODA_TOL)
    out["unmatched_codas"] = (len(ca) - len(pairs)) + (len(cb) - len(pairs))
    if not pairs:
        out.update(status="no_coda_match", f1=0.0, onset_precision=0.0, onset_recall=0.0,
                   n_clicks_a=n_a, n_clicks_b=n_b, n_clicks=n_a)
        return out

    tp = 0
    timing_errors: list[float] = []
    ici_errors: list[float] = []
    for ia, ib in pairs:
        ca_clicks, cb_clicks = ca[ia]["clicks"], cb[ib]["clicks"]
        m = match_onsets(ca_clicks, cb_clicks, tol)
        tp += len(m)
        timing_errors += [abs(ca_clicks[i] - cb_clicks[j]) for i, j in m]
        if len(ca_clicks) == len(cb_clicks):
            out["counts_match"] += 1
        if len(m) >= 2:
            ia_icis = np.diff([ca_clicks[i] for i, _ in m])
            ib_icis = np.diff([cb_clicks[j] for _, j in m])
            k = min(len(ia_icis), len(ib_icis))
            if k:
                ici_errors += list(np.abs(ia_icis[:k] - ib_icis[:k]))
            pa = pattern_signature(list(np.diff(ca_clicks)))
            pb = pattern_signature(list(np.diff(cb_clicks)))
            if pa and pa == pb:
                out["pattern_match"] += 1

    prec = tp / n_a if n_a else 0.0
    rec = tp / n_b if n_b else 0.0
    out.update(
        status="ok",
        pairs=len(pairs),
        n_clicks=n_a,
        onset_precision=round(prec, 4),
        onset_recall=round(rec, 4),
        f1=round(2 * prec * rec / (prec + rec), 4) if (prec + rec) else 0.0,
        timing_mae_ms=round(1000 * float(np.mean(timing_errors)), 2) if timing_errors else None,
        timing_p95_ms=round(1000 * float(np.percentile(timing_errors, 95)), 2) if timing_errors else None,
        n_clicks_a=n_a,
        n_clicks_b=n_b,
        icis_compared=len(ici_errors),
        ici_mae_ms=round(1000 * float(np.mean(ici_errors)), 2) if ici_errors else None,
    )
    return out


def summarise(rows: list[dict]) -> dict:
    """Aggregate per-clip rows.

    Agreement rates are normalised by clicks and by matched coda pairs, not by
    clip count: a clip where one annotator marked nothing must not dilute an
    agreement figure, and a one-click coda has no rhythm to agree about.
    """
    n_clips = len(rows)
    ok = [r for r in rows if r.get("status") == "ok"]
    empty = [r for r in rows if r.get("status") == "one_side_empty"]
    unmatched = sum(r.get("unmatched_codas", 0) for r in rows)
    pairs = sum(r.get("pairs", 0) for r in rows)
    if not ok:
        return {
            "clips": n_clips,
            "comparable": 0,
            "clips_marked_by_one_side_only": len(empty),
            "unmatched_codas": unmatched,
            "note": "no clip had codas from both annotators",
        }

    tm = [r["timing_mae_ms"] for r in ok if r.get("timing_mae_ms") is not None]
    im = [r["ici_mae_ms"] for r in ok if r.get("ici_mae_ms") is not None]
    f1s = [r["f1"] for r in ok]
    return {
        "clips": n_clips,
        "comparable": len(ok),
        "clips_marked_by_one_side_only": len(empty),
        "matched_coda_pairs": pairs,
        "unmatched_codas": unmatched,
        "clicks_a": sum(r.get("n_clicks_a", 0) for r in rows),
        "clicks_b": sum(r.get("n_clicks_b", 0) for r in rows),
        "mean_onset_f1": round(float(np.mean(f1s)), 4),
        "onset_f1_10th_pct": round(float(np.percentile(f1s, 10)), 4),
        "clips_below_f1_0_9": sum(1 for f in f1s if f < 0.9),
        "click_count_agreement": round(sum(r["counts_match"] for r in ok) / pairs, 4) if pairs else None,
        "pattern_agreement": round(sum(r["pattern_match"] for r in ok) / pairs, 4) if pairs else None,
        "median_timing_mae_ms": round(float(np.median(tm)), 2) if tm else None,
        "median_ici_mae_ms": round(float(np.median(im)), 2) if im else None,
    }


def stability(
    click_times: list[float], jitter_ms: float, trials: int = 200,
    seed: int = 0, ici_tol: float = 0.15,
) -> dict:
    """Would a slightly different annotator have produced the same label?

    Perturbs the onsets by the disagreement actually observed between two
    annotators, then asks whether the *measurements* survive: same click count,
    mean interval error within `ici_tol` (relative), and no single interval
    moving further than twice that.  The last condition matters: a mean-only
    test passes when one interval moves 60% and the rest barely move.

    Judged on intervals rather than a discrete rhythm code, because a discrete
    code has boundaries to land on and reports instability that is an artefact
    of the coding rather than of the annotation.
    """
    t = np.asarray(click_times, dtype=float)
    out = {"trials": 0, "n_clicks": int(t.size), "survives_click_count": None,
           "survives_ici": None, "stable": False}
    if t.size < 3:
        out["note"] = "fewer than 3 clicks: no intervals to test"
        return out

    rng = np.random.default_rng(seed)
    base = np.diff(t)
    scale = float(np.mean(base)) or 1e-9
    sigma = jitter_ms / 1000.0
    keep_n = keep_ici = 0
    for _ in range(trials):
        pert = np.sort(t + rng.normal(0, sigma, size=t.shape))
        if np.any(np.diff(pert) <= 0):
            continue
        keep_n += 1
        if pert.size == t.size:
            d = np.abs(np.diff(pert) - base)
            keep_ici += bool(np.mean(d) <= ici_tol * scale and np.max(d) <= 2 * ici_tol * scale)
    out.update(
        survives_click_count=round(keep_n / trials, 3),
        survives_ici=round(keep_ici / trials, 3),
        stable=(keep_ici / trials) >= 0.9,
    )
    return out


def _load(path: Path) -> dict[str, dict]:
    """Read either a JSON object with a clips list, or JSONL from the extractor."""
    text = path.read_text().strip()
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(raw, list):
        items = raw
    elif "clips" in raw:            # tools/marker.html export
        items = raw["clips"]
    elif "clip" in raw:             # a single JSONL record
        items = [raw]
    else:
        items = list(raw.values())
    return {str(c["clip"]): c for c in items}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("annotations", nargs="+", type=Path)
    ap.add_argument("--tol-ms", type=float, default=DEFAULT_TOL * 1000)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    docs = [(p.stem, _load(p)) for p in args.annotations]
    report: dict = {"tolerance_ms": args.tol_ms, "coda_match_tolerance_s": CODA_TOL, "pairs": {}}
    for (na, da), (nb, db) in itertools.combinations(docs, 2):
        shared = sorted(set(da) & set(db))
        rows = [compare_clip(da[c], db[c], tol=args.tol_ms / 1000.0) for c in shared]
        report["pairs"][f"{na} vs {nb}"] = {"summary": summarise(rows), "per_clip": rows}

    print(json.dumps({k: v["summary"] for k, v in report["pairs"].items()}, indent=2))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2))
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
