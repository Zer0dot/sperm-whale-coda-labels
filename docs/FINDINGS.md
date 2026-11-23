# What the audio shows

Every number here is reproduced by the scripts beside it. If the output stops
matching this document, this document is wrong.

```bash
python src/fetch_data.py
python src/join.py            data/dswp data/DominicaCodas.csv --out out/join.csv
python src/extract_clicks.py  data/dswp --out out/clip_features.jsonl
python src/calibrate.py       data/dswp data/DominicaCodas.csv   # prints the §2 table
python src/compare_reference.py out/clip_features.jsonl data/DominicaCodas.csv   # §3
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

`src/join.py` recovers the mapping for **1,382 of 1,501 clips (92.1%)**, all from
clan EC1, spanning 2005–2015, across four units and a mix of towed and
whale-borne rigs — 199 of the joined clips are 120 kHz animal-borne DTag audio.

The 119 clips left out do not form a long enough consecutive run to resolve.
Requiring 5 consecutive matches rather than 3 is deliberate: permuting clip
durations (same values, no correspondence) still produces about one 3-clip run
per permutation, so a lone 3-clip run is not evidence. The stricter rule costs
9 clips. Of those left out, most match at least one published row on duration,
but not uniquely — dozens of codas share a duration, so an isolated match
proves nothing.

Two consequences, and the second is the important one:

- The corpus is a **ready-made benchmark**: 1,391 clips with published coda
  type, click count, clan, unit and individual identity.
- The corpus **leaks its own labels**. Anyone can derive them from audio
  duration plus the public table, with no audio analysis at all. Any result that
  treats these clips as unlabelled audio is invalid — and random train/test
  splits do not help, because the leak is per clip, not per file order. Only
  holding out whole recording sessions would, and sessions are not identified in
  the public files.

The 0.5 s pad is inferred rather than documented. It is consistent to a sample
across 1,391 clips, which is strong, but it is an inference.

## 2. Given the true labels, the detector is mediocre — and that is the finding

With 1,382 known click counts, accuracy becomes measurable per clip instead of
inferred from a histogram. On the default profile, over all 1,382:

| | result |
|---|---|
| exact click count | **19.6%** |
| within ±1 click | 36.9% |
| bias | +0.53 clicks |
| mean absolute error | 2.48 clicks |

That single figure is close to useless on its own, because the corpus is two
different recording setups in a trench coat:

| clips | n | exact click count | within ±1 | mean abs error |
|---|---|---|---|---|
| towed hydrophone (≤96 kHz) | 1,183 | **13.0%** | 30.4% | 2.72 |
| whale-borne DTag (120 kHz) | 199 | **58.8%** | 75.4% | 1.08 |

The same code, the same settings, five times the accuracy on whale-borne
recordings. The reason is almost certainly multipath: a click recorded from a
boat in shallow water arrives once directly and then again off the surface and
seabed, so a naive envelope finds the echoes as extra clicks. A hydrophone
suction-cupped to the whale's head hears the direct path and little else.

**This is the most actionable result in the repository.** A project that can
obtain tag audio rather than towed audio is not making an incremental gain; it
is working on a different problem.

A separate `tag` profile was built on the assumption that tag clicks need their
own settings. It does not earn its place: 57.3% against 58.8% for the far-field
profile. Simplicity wins, and the parameter that does matter is the echo floor —
turning it off drops tag accuracy from 58.8% to 28.1%.

**The trap worth recording.** Sweeping 20 combinations of echo floor and
minimum interval (`src/calibrate.py`, 30% train / 70% validation) tops out near
22% exact, and the best-scoring settings merge any two peaks closer than 60 ms.
That improves click-count agreement while destroying real structure, because
the published table contains genuine inter-click intervals down to 30 ms.
Optimising for "does my count match" therefore selects a parameter that merges
true clicks. Anyone working on this corpus should judge themselves on intervals,
not on counts, or they will be rewarded for exactly this mistake.

## 3. Fast codas are much harder to pin down than slow ones

Jitter the click times by 10 ms — roughly what two careful annotators differ by
— and ask whether the intervals survive (`src/iaa.py`):

| codas | count | intervals survive | pass a 0.9 stability bar |
|---|---|---|---|
| fast (intervals under 120 ms) | 467 | 46% | 4% |
| slow (intervals 120 ms or more) | 845 | 99% | 99% |

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
  constantly, so discarding such runs throws away the coda in 339 of 1,501 clips.
  Splitting them at their widest gap is better.
- **An amplitude floor for echoes.** Modest. Two thirds of peaks sit more than
  6 dB below their run's loudest click, but a floor moves the median count from
  7 to 6 and stops there. Echoes are not separable by level alone.
- **Where the amplitude gate is applied.** A bug, caught in review: the gate
  that splits loud peaks from quiet ones was computed across the whole clip, so
  it silently deleted a quiet coda sharing a clip with a loud one. Applied per
  run instead it does the same job without the cross-contamination, and the
  numbers above are unchanged — the fix cost nothing once it was placed
  correctly.
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
