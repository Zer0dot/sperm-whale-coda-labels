# Onboarding site

A short interactive course for someone who has to review work on this repo but
has no coda background. Seven lessons, flashcards, a quiz, and real audio.

```bash
cd site && python3 -m http.server 8000    # then open http://localhost:8000
```

No build step, no dependencies, no network beyond its own folder.

## What's in it

- `index.html` — the lessons, flashcards and quiz markup
- `app.js` — spectrogram renderer, audio player, marking exercise, stability demo
- `style.css`
- `audio/` — seven clips cut from the public dataset, plus `manifest.json`

`manifest.json` carries the published answer for each clip: coda type, click
count, inter-click intervals, onset times, clan, unit and date. The onset times
are `0.30 + cumulative intervals`, because each clip is trimmed to start 0.30 s
before the first click.

The audio is Dominica Sperm Whale Project material, CC-BY-4.0, trimmed to
44.1 kHz mono for teaching. If you reuse these clips, keep the attribution.

## Regenerating the clips

The script that produced `audio/` is not checked in — it depended on the local
layout of the downloaded corpus. The selection rule was: for each teaching
purpose, pick a clip where the published answer is known and the machine
behaviour illustrates the point (for the failure case, a towed clip where the
detector over-counts by 5; for the speed comparison, a `5R1` around 80 ms and a
`1+1+3` averaging about 350 ms).
