#!/usr/bin/env python3
"""Cut the teaching clips in site/audio/ from the public corpus.

The clips are checked in, so you only need this if you want to change the
selection. It picks one clip per teaching purpose from the joined corpus and
writes the manifest the site reads.

    python site/make_clips.py --corpus data/dswp --join out/join.csv \
        --table data/DominicaCodas.csv --out site/audio

Every clip is trimmed to 0.30 s before the first click and 0.30 s after the
last, so the onsets in the manifest are `0.30 + cumulative published intervals`.
The ORIGINAL public files carry 1.000 s of padding total (0.5 s each end);
these teaching clips are re-trimmed to sit tighter.
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

LEAD = 0.30      # seconds kept before the first click
TAIL = 0.30      # seconds kept after the last click
TARGET_SR = 44100


def intervals(row: dict) -> list[float]:
    out = []
    for i in range(1, 10):
        v = row.get(f"ICI{i}", "").strip()
        if v and float(v) > 0:
            out.append(float(v))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True, help="directory of public .wav clips")
    ap.add_argument("--join", type=Path, required=True, help="clip -> published row (src/join.py)")
    ap.add_argument("--table", type=Path, required=True, help="published coda table")
    ap.add_argument("--out", type=Path, default=Path("site/audio"))
    ap.add_argument("--features", type=Path, default=None,
                    help="out/clip_features.jsonl, so the failure example is a real "
                         "over-count and the manifest can record what the detector said")
    args = ap.parse_args(argv)

    joined = {r["clip"]: r for r in csv.DictReader(args.join.open())}
    table = {r["codaNUM2018"]: r for r in
             csv.DictReader(args.table.open(encoding="utf-8-sig"))}
    args.out.mkdir(parents=True, exist_ok=True)

    feats: dict[str, int] = {}
    if args.features and args.features.exists():
        for line in args.features.open():
            r = json.loads(line)
            feats[r["clip"]] = len(r["codas"][0]["clicks"]) if r.get("codas") else 0

    # rig is read back off the sample rate: the corpus mixes towed and tag audio
    def rig_of(clip: str) -> str:
        sr, _ = wf.read(str(args.corpus / f"{clip}.wav"))
        return "whale-borne tag" if sr > 96000 else "towed hydrophone"

    def mean_ici(clip: str) -> float:
        v = intervals(table[joined[clip]["codaNUM"]])
        return float(np.mean(v)) if v else 9.9

    def clean(clip: str) -> bool:
        """True when the shipped detector matches the published click count."""
        return (not feats) or feats.get(clip) == int(joined[clip]["nClicks"])

    wanted = [
        # The exemplars should be ones the detector gets right, so lesson 3 is
        # about naming and not about detection error.
        ("tag113", lambda c: rig_of(c).startswith("whale") and joined[c]["CodaType"] == "1+1+3" and clean(c)),
        ("tag5r1", lambda c: rig_of(c).startswith("whale") and joined[c]["CodaType"] == "5R1" and clean(c)),
        ("tag4r2", lambda c: rig_of(c).startswith("whale") and joined[c]["CodaType"] == "4R2" and clean(c)),
        # The failure case must genuinely fail: a towed clip the detector
        # over-counts by at least three clicks, or the lesson demonstrates
        # nothing.
        ("towed-echoes", lambda c: rig_of(c).startswith("towed")
                                   and feats.get(c, 0) - int(joined[c]["nClicks"]) >= 3),
        ("towed-clean", lambda c: rig_of(c).startswith("towed") and joined[c]["CodaType"] == "5R1" and clean(c)),
        ("fast", lambda c: rig_of(c).startswith("whale") and joined[c]["CodaType"] == "5R1"
                           and 0.075 < mean_ici(c) < 0.12 and clean(c)),
        ("slow", lambda c: rig_of(c).startswith("whale") and joined[c]["CodaType"] == "1+1+3"
                           and 0.30 < mean_ici(c) < 0.45 and clean(c)),
    ]

    manifest = []
    used: set[str] = set()
    for slug, pred in wanted:
        pick = None
        for clip in sorted(joined, key=lambda c: int(c) if c.isdigit() else 0):
            if clip in used or not pred(clip):
                continue
            pick = clip
            break
        if pick is None:
            print(f"no clip found for {slug} — skipped")
            continue
        used.add(pick)

        row = table[joined[pick]["codaNUM"]]
        sr, x = wf.read(str(args.corpus / f"{pick}.wav"))
        x = (x[:, 0] if x.ndim > 1 else x).astype(np.float64) / 32768.0
        coda_dur = float(row["Duration"])
        a = int(LEAD * sr)
        b = a + int((coda_dur + LEAD + TAIL) * sr)
        x = x[a:b]
        g = gcd(TARGET_SR, sr)
        x = resample_poly(x, TARGET_SR // g, sr // g)
        x = x / (np.max(np.abs(x)) or 1.0) * 0.7
        wf.write(str(args.out / f"{slug}.wav"), TARGET_SR, (x * 32767).astype(np.int16))

        icis = intervals(row)
        manifest.append({
            "id": slug, "file": f"audio/{slug}.wav", "clip": pick,
            "codaType": row["CodaType"], "nClicks": int(row["nClicks"]),
            "icis": [round(v, 3) for v in icis],
            "onsets": [round(LEAD + sum(icis[:i]), 3) for i in range(int(row["nClicks"]))],
            "rig": rig_of(pick), "clan": row["Clan"], "unit": row["Unit"], "date": row["Date"],
            "fileDur": round(coda_dur + 1.000, 3),
            "detected": feats.get(pick),
        })
        print(f"{slug:14s} clip {pick:5s} {row['CodaType']:8s} {row['nClicks']} clicks")

    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"wrote {len(manifest)} clips -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
