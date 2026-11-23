# Onboarding site

A short interactive course for someone who has to review work on this repo but
has no coda background. Seven lessons, flashcards, a quiz, and real audio.

```bash
cd site && python3 -m http.server 8000    # then open http://localhost:8000
```

No build step, no dependencies, no network beyond its own folder.

## What's in it

- `index.html` — lessons, flashcards and quiz markup
- `app.js` — spectrogram renderer, audio player, marking exercise, stability demo
- `style.css`
- `audio/` — seven clips plus `manifest.json`
- `make_clips.py` — regenerates `audio/` from the public corpus

## How the clips are cut

The original public files are one published coda with **1.000 s of padding**
(0.5 s at each end). The cutter drops 0.30 s from the start of the file and
keeps 0.30 s after the last click, so a teaching clip begins **0.20 s** before
the first click — and the manifest's onsets are `0.20 + cumulative published
intervals`.

Two different lengths appear in the manifest and they are easy to confuse:
`fileDur` is the length of the *original* public file (coda + 1.000 s), which is
the number that leaks the label; `clipLen` is what this page actually plays.

Regenerating:

```bash
python site/make_clips.py --corpus data/dswp --join out/join.csv \
    --table data/DominicaCodas.csv --features out/clip_features.jsonl \
    --out site/audio
```

It picks one clip per teaching purpose: three whale-borne exemplars the detector
gets right, one towed clip it gets badly wrong (the lesson depends on that being
a real failure), one towed clip it gets right, and a fast/slow pair chosen on
measured inter-click interval rather than on type name.

## Audio licence

The clips are Dominica Sperm Whale Project recordings, **CC-BY-4.0**, trimmed
and resampled to 44.1 kHz mono. They are redistributed here under that licence
with attribution. The full 1,501-clip corpus is not redistributed;
`src/fetch_data.py` downloads it from source.
