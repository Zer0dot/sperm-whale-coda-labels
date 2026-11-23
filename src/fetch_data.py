#!/usr/bin/env python3
"""Fetch the public audio and the published measurements this repo compares to.

Both are public and unauthenticated; nothing is redistributed here, which is why
this script exists instead of a data folder.

    python src/fetch_data.py --audio-dir data/dswp --ref data/DominicaCodas.csv

The audio is ~562 MB. Skip it with --skip-audio if you only want the table.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import urllib.request
from pathlib import Path

AUDIO = "https://huggingface.co/datasets/orrp/DSWP/resolve/main/{n}.wav"
N_CLIPS = 1501
REF = (
    "https://raw.githubusercontent.com/pratyushasharma/sw-combinatoriality/"
    "main/data/DominicaCodas.csv"
)


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "coda-labels/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as fh:
        fh.write(r.read())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio-dir", type=Path, default=Path("data/dswp"))
    ap.add_argument("--ref", type=Path, default=Path("data/DominicaCodas.csv"))
    ap.add_argument("--skip-audio", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv)

    fetch(REF, args.ref)
    print(f"reference table -> {args.ref}")

    if args.skip_audio:
        return 0

    jobs = [(AUDIO.format(n=n), args.audio_dir / f"{n}.wav") for n in range(1, N_CLIPS + 1)]
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch, u, d): d for u, d in jobs}
        for f in cf.as_completed(futs):
            try:
                f.result()
            except Exception as exc:  # noqa: BLE001 - report and keep going
                print(f"failed: {futs[f]} ({exc})")
                continue
            done += 1
            if done % 250 == 0:
                print(f"  {done}/{len(jobs)} clips")

    got = len(list(args.audio_dir.glob("*.wav")))
    print(f"audio -> {args.audio_dir} ({got} clips)")
    return 0 if got else 1


if __name__ == "__main__":
    raise SystemExit(main())
