# What the audio shows

Every number here is reproduced by the scripts beside it. If the output stops
matching this document, this document is wrong.

```bash
python src/fetch_data.py
python src/join.py            data/dswp data/DominicaCodas.csv --out out/join.csv
python src/extract_clicks.py  data/dswp --out out/clip_features.jsonl
python src/calibrate.py       data/dswp data/DominicaCodas.csv
python src/compare_reference.py out/clip_features.jsonl data/DominicaCodas.csv
```

## 1. The public clips are not unlabelled. They are labelled, and the label leaks

The 1,501-clip public dataset ships no metadata — only `fmt ` and `data` chunks,
no identifying text of any kind. But each clip is exactly one published coda
plus half a second of padding at each end, so:

```
wav_duration == table.Duration + 1.000 s
```

This holds with a mean of 1.000000 s and a standard deviation of 9 microseconds
across 1,391 clips — one sample at 44.1 kHz. That is not a statistical tendency,
it is a file-level identity.

`src/join.py` recovers the mapping for **1,391 of 1,501 clips (92.7%)**, all from
clan EC1, spanning 2005–2015.

The remaining 110 (7.3%) do not form a long enough run to resolve. 82 of them are
clip 1400 or later; 106 do match at least one published row on duration, but not
uniquely — dozens of codas share a duration, so a lone match is not evidence.
Leaving them out is the conservative choice, and it costs 7% of the corpus.

Two consequences, and the second is the important one:

- The corpus is a **ready-made benchmark**: 1,391 clips with published coda
  type, click count, clan, unit and individual identity.
- The corpus **leaks its own labels**. Anyone can derive them from audio
  duration plus the public table, with no audio analysis at all. Any result that
  treats these clips as unlabelled audio is invalid. Splitting by file index
  also leaks, because the mapping is piecewise-contiguous rather than a single
  offset.

The 0.5 s pad is inferred rather than documented. It is consistent to a sample
across 1,391 clips, which is strong, but it is an inference.

## 2. Given the true labels, the detector is mediocre — and that is the finding

With 1,391 known click counts, accuracy becomes measurable per clip instead of
inferred from a histogram. Using the default profile:

| | result |
|---|---|
| exact click count | **19.7%** |
| within ±1 click | 36.7% |
| bias | +0.58 clicks |
| mean absolute error | 2.49 clicks |

Roughly one coda in five is counted correctly. This is not a tuning failure:
sweeping 60 parameter combinations (`src/calibrate.py`, 30% train / 70%
validation) tops out around 22–26% exact, and the settings that score highest
are not acceptable.

**The trap worth recording.** The best-scoring settings merge any two peaks
closer than 60 ms. That improves click-count agreement — and destroys real
structure, because the published table contains genuine inter-click intervals
down to 30 ms. Optimising for "does my count match" therefore selects a
parameter that merges true clicks. Anyone working on this corpus should judge
themselves on intervals, not on counts, or they will be rewarded for exactly
this mistake.

The honest conclusion: counting clicks in far-field recordings automatically is
hard, and a detector is not a substitute for a person. That is an argument for
the annotation protocol, not against it.

## 3. Fast codas are much harder to pin down than slow ones

Jitter the click times by 10 ms — roughly what two careful annotators differ by
— and ask whether the intervals survive (`src/iaa.py`):

| codas | count | intervals survive | pass a 0.9 stability bar |
|---|---|---|---|
| fast (intervals under 120 ms) | 479 | 45% | 4% |
| slow (intervals 120 ms or more) | 837 | 99% | 99% |

A third of the corpus is in the fast regime, and those are the `5R1` and `4R2`
shapes that make up much of the Dominica repertoire. So "did we agree on this
coda?" depends on how fast the whale was clicking, and an agreement figure that
does not say which codas it covers is close to meaningless.

## 4. What was tried on the detector, and what each attempt changed

- **Splitting codas on gaps.** The published table answers "how long a gap still
  counts as inside a coda": the largest is 0.80 s, the 99th percentile 0.49 s. A
  generous 1.0 s chains codas together and gives a median of 8 clicks against 5
  in the reference; 0.55 s fixes that.
- **Discarding over-long runs.** Wrong. Echolocation clicks trail codas
  constantly, so discarding such runs threw away the coda in 734 of 1,501 clips.
  Splitting them at their widest gap is better.
- **An amplitude floor for echoes.** Modest. Two thirds of peaks sit more than
  6 dB below their run's loudest click, but a floor moves the median count from
  7 to 6 and stops there. Echoes are not separable by level alone.
- **Applying that floor per clip rather than per run.** A bug, caught in review:
  it silently deleted a quiet coda sitting next to a loud one.
- **Ranking codas by click count.** Actively wrong: it selects for merged codas.
  Ranking by strength is correct.

## 5. Not established here

- **Two annotators have not produced marks yet.** Everything above is the
  detector against published labels. The agreement machinery is built and
  self-tested, but no human IAA figure exists for this corpus.
- **No claim about whale behaviour.** 45 minutes, one site, one clan in the
  joined subset.
- **The published labels are assumed correct.** They were not re-verified here,
  and the 110 unmapped clips remain unexplained.
