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
(0.5 s at each end). These teaching clips are re-trimmed tighter: 0.30 s before
the first click and 0.30 s after the last. That is why the manifest's onset
times are `0.30 + cumulative published intervals`, and why a clip's `fileDur`
(the original length, which is what leaks the label) is not the same as its
length on disk.

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
