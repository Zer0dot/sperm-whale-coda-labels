#!/usr/bin/env python3
"""Head-to-head against a published coda-click detector.

We do not have a benchmark, so the first useful measurement is: how does our
crude peak-picker compare with the best openly licensed detector, on the same
clips, against the same published labels?

The incumbent is `martin-rodriguez-munoz/sperm_whale_click_detection_pipeline`
(MIT, Gubnitsky & Diamant 2025). It is an external dependency with its own
checkpoints, so running it is a documented manual step — this script prepares
its inputs and scores its outputs.

    # 1. prepare inputs (22.05 kHz stereo: the incumbent rejects mono)
    python src/incumbent_bench.py prepare --out /tmp/mit_in

    # 2. run the incumbent (clone + download its checkpoints first)
    cd sperm_whale_click_detection_pipeline/inference_only
    python run_pipeline_on_folder.py --input_folder /tmp/mit_in \
        --output_folder /tmp/mit_out \
        --path_to_phase_1_soundnet_checkpoint ../ckpt/phase_1_checkpoints/phase_1_soundnet.pt \
        ... (one flag per checkpoint; see its README)

    # 3. score
    python src/incumbent_bench.py score --pred /tmp/mit_out \
        --labels /tmp/mit_in/labels.json
"""
from __future__ import annotations

import argparse
import csv
import json
from math import gcd
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wf
from scipy.signal import resample_poly

TARGET_SR = 22050   # the incumbent's hard-coded rate


def prepare(corpus: Path, join_csv: Path, features: Path, out: Path, n: int) -> dict:
    join = {r["clip"]: r for r in csv.DictReader(join_csv.open())}
    sr_of = {}
    for line in features.open():
        r = json.loads(line)
        sr_of[r["clip"]] = r["sr"]

    # Deterministic and stated: the first n clips by id within each rig.
    # NOTE this makes each rig a contiguous run of clips, which is one
    # recording session. It is a smoke test, not a representative sample.
    tag = sorted([c for c in join if sr_of.get(c, 0) > 96000], key=int)[:n]
    towed = sorted([c for c in join if 0 < sr_of.get(c, 0) <= 96000], key=int)[:n]

    out.mkdir(parents=True, exist_ok=True)
    labels = []
    for clip in tag + towed:
        sr, x = wf.read(str(corpus / f"{clip}.wav"))
        x = (x[:, 0] if x.ndim > 1 else x).astype(np.float64)
        if np.max(np.abs(x)) > 1.5:
            x = x / 32768.0
        g = gcd(TARGET_SR, sr)
        x = resample_poly(x, TARGET_SR // g, sr // g)
        # the incumbent errors on mono input, so duplicate the channel
        wf.write(str(out / f"{clip}.wav"), TARGET_SR,
                 (np.stack([x, x], axis=1) * 32767).astype(np.int16))
        labels.append({
            "clip": clip,
            "nClicks": int(join[clip]["nClicks"]),
            "codaType": join[clip]["CodaType"],
            "rig": "tag" if sr_of.get(clip, 0) > 96000 else "towed",
        })

    (out / "labels.json").write_text(json.dumps(labels, indent=1))
    print(f"prepared {len(labels)} clips -> {out} "
          f"({len(tag)} tag, {len(towed)} towed)")
    return {"labels": labels}


def _predicted_clicks(csv_path: Path) -> int:
    """Clicks in the strongest predicted coda (most clicks among rows)."""
    if not csv_path.exists():
        return 0
    rows = [r for r in csv.DictReader(csv_path.open()) if r.get("nClicks", "").strip()]
    counts = [int(float(r["nClicks"])) for r in rows]
    return max(counts) if counts else 0


def score(pred_dir: Path, labels: list[dict], ours: dict[str, int] | None = None) -> dict:
    by_rig: dict[str, list[tuple[int, int]]] = {}
    per_clip = []
    for item in labels:
        got = _predicted_clicks(pred_dir / f"{item['clip']}_annotations.csv")
        by_rig.setdefault(item["rig"], []).append((got, item["nClicks"]))
        per_clip.append({"clip": item["clip"], "rig": item["rig"],
                         "predicted": got, "published": item["nClicks"],
                         "ours": (ours or {}).get(item["clip"])})

    out = {"by_rig": {}, "per_clip": per_clip}
    for rig, pairs in by_rig.items():
        a = np.array(pairs, dtype=float)
        err = a[:, 0] - a[:, 1]
        ours_pairs = [(p["ours"], p["published"]) for p in per_clip
                      if p["rig"] == rig and p["ours"] is not None]
        entry = {
            "n": len(pairs),
            "incumbent_exact": round(float(np.mean(err == 0)), 3),
            "incumbent_within1": round(float(np.mean(np.abs(err) <= 1)), 3),
            "incumbent_bias": round(float(np.mean(err)), 2),
        }
        if ours_pairs:
            b = np.array(ours_pairs, dtype=float)
            oerr = b[:, 0] - b[:, 1]
            entry.update({
                "ours_exact": round(float(np.mean(oerr == 0)), 3),
                "ours_within1": round(float(np.mean(np.abs(oerr) <= 1)), 3),
                "ours_bias": round(float(np.mean(oerr)), 2),
            })
        out["by_rig"][rig] = entry

    for rig, e in out["by_rig"].items():
        print(f"{rig:6s} n={e['n']:3d}  incumbent exact {100*e['incumbent_exact']:5.0f}% "
              f"±1 {100*e['incumbent_within1']:5.0f}% bias {e['incumbent_bias']:+.2f}"
              + (f"   | ours exact {100*e['ours_exact']:5.0f}% "
                 f"±1 {100*e['ours_within1']:5.0f}% bias {e['ours_bias']:+.2f}"
                 if 'ours_exact' in e else ""))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--join", type=Path, required=True)
    p.add_argument("--features", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--n", type=int, default=12, help="clips per rig")

    s = sub.add_parser("score")
    s.add_argument("--pred", type=Path, required=True)
    s.add_argument("--labels", type=Path, required=True)
    s.add_argument("--ours", type=Path, default=None,
                   help="clip_features.jsonl from extract_clicks.py, for the side-by-side")
    s.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.cmd == "prepare":
        prepare(args.corpus, args.join, args.features, args.out, args.n)
        return 0

    labels = json.loads(args.labels.read_text())
    ours = {}
    if args.ours:
        for line in args.ours.open():
            r = json.loads(line)
            ours[r["clip"]] = len(r["codas"][0]["clicks"]) if r.get("codas") else 0
    out = score(args.pred, labels, ours)
    if args.out:
        args.out.write_text(json.dumps(out, indent=1))
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
