# Sperm whale coda labels

Turning sperm whale audio into click times anyone can check, compare, and reuse.

## Why this exists

Sperm whales string clicks into short rhythmic bursts called **codas**. We know
the rhythms differ between whale clans and that codas carry identity cues. What
nobody had is a public, reusable set of *marked-up audio*: the 1,501 clips
available to everyone came with no labels, and the 8,719 published coda
measurements came with no audio.

Two things came out of building this, and the first one matters more than the
tool:

**The public clips are labelled after all.** Each clip is one published coda
padded by half a second at each end, so the label is recoverable from file
duration alone. `src/join.py` maps 1,382 of 1,501 clips to published rows. That
means the corpus is a ready-made benchmark — and that it leaks its own labels.
Read `docs/FINDINGS.md` before using it for anything.

**Counting clicks automatically is hard.** With true labels in hand, the
detector counts only about one coda in five exactly right. A person correcting
it is not a nicety; it is the method.

## What's in the box

| path | what it is |
|---|---|
| `src/fetch_data.py` | Downloads the public audio and the published measurements |
| `src/join.py` | Recovers which published coda each audio clip is |
| `src/extract_clicks.py` | Finds click onsets in a clip; emits timings, never coda names |
| `src/calibrate.py` | Scores the detector against known labels, train/validation split |
| `src/iaa.py` | Compares two people's marks and reports how much they disagree |
| `src/compare_reference.py` | Reproduces the comparison numbers in `docs/FINDINGS.md` |
| `tools/marker.html` | Browser tool: open a wav, see the spectrogram, correct the marks |
| `docs/PROTOCOL.md` | The rulebook annotators follow, including edge cases |
| `docs/FINDINGS.md` | What the audio actually shows, including the label leak |
| `site/` | Interactive onboarding course — 7 lessons with real audio, flashcards, quiz |
| `tests/` | Synthetic regression tests for the extractor, the join, and agreement |

## Quick start

```bash
pip install numpy scipy
python src/fetch_data.py                                        # 45 min of audio + published table
python src/join.py data/dswp data/DominicaCodas.csv --out out/join.csv
python src/extract_clicks.py data/dswp --out out/clip_features.jsonl
python src/calibrate.py data/dswp data/DominicaCodas.csv
python tests/test_iaa.py
```

Then open `tools/marker.html` in a browser, drop wav files on it, and correct the
marks by clicking. Download the result as JSON. To compare two annotators:

```bash
python src/iaa.py alice.json bob.json
```

## What we measure, and why only that

Clicks happen at objective times. The *names* people give the resulting patterns
are not objective — the field has published at least three incompatible naming
schemes — so names are derived in a separate, declared step and never baked into
the marks.

## Where it stands

- 1,501 clips, 45 minutes of audio, of which 1,382 are matched to published
  labels.
- Detector against those labels: 18.9% exact click count overall — but 58.8% on
  the 199 whale-borne clips and 12.2% on the 1,183 towed ones. Near-field audio
  is a different problem from far-field audio, and averaging them hides that.
- 28 self-checks across three suites (extractor, join, agreement), but no
  human annotator has marked anything yet — so there is no real IAA figure, and
  none is claimed.

## Honest limits

- 45 minutes of audio is not much. Treat any claim about whale behaviour from
  this corpus as provisional.
- The 0.5 s padding rule is inferred, not documented.
- Roughly 14% of the corpus is animal-borne; the rest is towed hydrophone, where
  multipath wrecks naive click counting.
- Every acoustic difference between whales shows up as measurement noise here
  unless it is controlled for.

## Licence

Code MIT. The audio belongs to the Dominica Sperm Whale Project, CC-BY-4.0.
The full 1,501-clip corpus is not redistributed here — `src/fetch_data.py`
downloads it from source. The seven short clips in `site/audio/` are
redistributed under CC-BY-4.0 with attribution, as that licence allows. Marks produced with this tool are
yours to license as you choose.
