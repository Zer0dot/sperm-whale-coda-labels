# What the audio shows

Measured on the 1,501 public clips (45 minutes, Dominica, 44.1–120 kHz).
Every number below is reproduced by:

```bash
python src/fetch_data.py          # public audio + published table
python src/extract_clicks.py data/dswp --out out/clip_features.jsonl
python src/compare_reference.py out/clip_features.jsonl data/DominicaCodas.csv
```

If the output stops matching this document, this document is wrong.

## The headline numbers

| | this pipeline | published Dominica table |
|---|---|---|
| codas measured | 1,141 of 1,501 clips (76%) | 8,719 |
| median clicks per coda | 6 | 5 |
| mean clicks per coda | 6.41 | 5.26 |
| median inter-click interval | 116 ms | 171 ms |
| median coda duration | 0.86 s | 0.85 s |

Duration agrees. Click count does not: the tool finds roughly one extra click
per coda. The likely reason is echoes and reverberation from the shallow
recording site, which arrive 20–200 ms after a click and sit above the noise
floor.

## What was tried, and what it did

**Splitting codas on gaps.** The published table gives the answer to "how long a
gap still counts as inside a coda": across 8,719 codas the largest is 0.80 s and
the 99th percentile is 0.49 s. Using a generous 1.0 s chains separate codas
together and produces a median of 8 clicks. Using 0.55 s fixes that. This one
number accounts for most of the naive error.

**Discarding over-long runs.** Wrong. Echolocation clicks trail codas constantly,
so most clips contain one long run; discarding those runs threw away the coda in
734 of 1,501 clips. Splitting them at their widest gap instead is both more
accurate and far less wasteful.

**An amplitude floor to kill echoes.** Barely helps. Two thirds of detected peaks
sit more than 6 dB below the loudest click in their run, which looked like a
decaying echo tail; but a −12 dB floor moves the median click count from 7 to 6
and no further. Echoes are not cleanly separated by level alone.

**Choosing the loudest coda rather than the longest.** Necessary. Ranking by
click count actively selects for merged codas, since merging is what produces
high counts.

## A finding worth keeping

Fast codas are measurably harder to characterise than slow ones, by a wide
margin. Jitter the click times by 10 ms — roughly what two careful annotators
differ by — and ask whether the inter-click intervals survive:

| codas | count | survive the jitter | pass a 0.9 stability bar |
|---|---|---|---|
| fast (intervals under 120 ms) | 401 | 50% | 6% |
| slow (intervals 120 ms or more) | 740 | 99% | 99% |

A fast coda's intervals move by more than 15% under half the time; a slow coda's
essentially never do. So "did we agree on this coda?" depends on how fast the
whale was clicking, and any published agreement figure that does not say which
codas it covers is close to meaningless. A third of this corpus is in the fast
regime — and fast codas are not a nuisance subset, they are the `5R1` and `4R2`
shapes that make up a large share of the Dominica repertoire.

The practical consequence: fast codas need finer timing precision than 10 ms
before their rhythm can be trusted, which means higher sampling rates in the
annotation tool and more careful onset definition in the protocol.

## What is not established here

- **No ground-truth labels yet.** The comparison above is against a published
  distribution, not against per-clip truth. It bounds the bias; it does not
  correct it.
- **No claim about whale behaviour is made from this corpus.** 45 minutes, one
  site, two clans.
- **The 24% of clips with no detected coda are unexplained.** They may contain
  only echolocation, may be quiet, or may be detector failures. Distinguishing
  those needs a human to look.
