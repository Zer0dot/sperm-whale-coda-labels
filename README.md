# Sperm whale coda labels

Turning sperm whale audio into click times anyone can check, compare, and reuse.

## Why this exists

Sperm whales string clicks into short rhythmic bursts called **codas**. We know
the rhythms differ between whale clans and that codas carry identity cues. What
nobody has is a public, reusable set of *marked-up audio*: the 1,501 clips
available to everyone come with no labels, and the 8,719 published coda
measurements come with no audio.

So anyone wanting to work on codas starts by re-deriving the same measurements
by hand, differently, in private. This repo is an attempt to fix that one piece:
a small, honest, checkable way to go from a wav file to click timings, with the
disagreement between annotators measured rather than assumed.

## What's in the box

| path | what it is |
|---|---|
| `src/extract_clicks.py` | Finds click onsets in a clip; emits timings, never coda names |
| `src/iaa.py` | Compares two people's marks and reports how much they disagree |
| `tools/marker.html` | Browser tool: open a wav, see the spectrogram, correct the marks |
| `docs/PROTOCOL.md` | The rulebook annotators follow, including edge cases |
| `src/fetch_data.py` | Downloads the public audio and the published measurements |
| `src/compare_reference.py` | Reproduces every number in `docs/FINDINGS.md` |
| `docs/FINDINGS.md` | What the audio actually shows, and where the tool is biased |

## Quick start

```bash
pip install numpy scipy
python src/fetch_data.py                                          # 45 min of public audio + published table
python src/extract_clicks.py data/dswp --out out/clip_features.jsonl
python src/compare_reference.py out/clip_features.jsonl data/DominicaCodas.csv
```

Then open `tools/marker.html` in a browser, drop wav files on it, and correct
the marks by clicking. Download the result as JSON.

To compare two annotators:

```bash
python src/iaa.py alice.json bob.json
```

## What we measure, and why only that

Clicks happen at objective times. The *names* people give the resulting patterns
are not objective — the field has published at least three incompatible naming
schemes — so names are derived in a separate, declared step and never baked into
the marks.

## Current state

Run over the 1,501 public clips (45 minutes of audio, Dominica):

- a coda was found in 1,141 clips (76%)
- median 6 clicks per coda, median inter-click interval 116 ms
- median coda duration 0.86 s

Against the 8,719 published Dominica measurements: duration matches almost
exactly (0.85 s), but the tool finds about 22% more clicks per coda (median 6 vs
5) and correspondingly shorter gaps. It is finding the right events and
sometimes including extra closely-spaced clicks around them.

That bias is measured, not hidden. It is exactly what the correction step exists
for: the machine proposes, a person corrects, and `iaa.py` reports what is left.
No accuracy figure is claimed for the marks until real annotators have produced
them.

## Honest limits

- 45 minutes of audio is not much. Treat any claim about whale behaviour from
  this corpus as provisional.
- Far-field boat recordings only so far; animal-borne tag audio needs its own
  settings.
- Shallow-water recordings have echoes that look like extra clicks.
- Every acoustic difference between whales shows up as measurement noise here
  unless it is controlled for.

## Licence

Code MIT. The audio belongs to the Dominica Sperm Whale Project and is used
under CC-BY-4.0; it is not redistributed here. Marks produced with this tool are
yours to license as you choose.
