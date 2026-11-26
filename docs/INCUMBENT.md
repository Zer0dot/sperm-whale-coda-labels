# Head-to-head against the published detector

We had no benchmark, so the first thing worth measuring is embarrassingly
basic: **how does our crude peak-picker compare with the best openly licensed
detector, on the same clips, against the same published labels?**

Incumbent: `martin-rodriguez-munoz/sperm_whale_click_detection_pipeline`
(Gubnitsky & Diamant 2025), MIT licence, public checkpoints. Verified by
cloning, reading the licence and running it — not from the paper.

Reproduce with `src/incumbent_bench.py` (it prepares the incumbent's inputs and
scores its outputs; running the incumbent itself is a documented manual step
because it is an external dependency).

## Result

24 clips, first 12 by clip id within each rig, scored against published click
counts. Default thresholds (0.5 / 0.7). CPU.

| rig | n | | exact | within ±1 | bias |
|---|---|---|---|---|---|
| whale-borne | 12 | **incumbent** | 67% | 83% | +0.50 |
| whale-borne | 12 | **ours** | 67% | 67% | +1.33 |
| towed | 12 | **incumbent** | **0%** | **0%** | **−4.50** |
| towed | 12 | **ours** | 17% | 33% | +2.67 |

The incumbent predicts **zero clicks on 7 of the 12 towed clips**.

## That is not a threshold artefact

Retested four towed clips with thresholds dropped from 0.5/0.7 to 0.2/0.3 —
far more permissive than anything sensible. Predicted clicks: 0, 0, 1, 2,
against a published 5 for every one of them.

## Why this matters

The failure mode is **silent**. A pipeline that returns an empty annotation file
does not look wrong; it looks like there were no codas. Anyone running this on
towed recordings would conclude the whales were quiet.

This is exactly what the landscape survey predicted from the absence of any
published far-field metric — and it is now measured rather than assumed.

## Caveats, all of which cut the same way

- **n = 12 per rig**, one run, one threshold setting.
- The subset is the **first 12 consecutive clips** in each rig, i.e. one
  recording session. Not a representative sample, and not stratified by coda
  type.
- The incumbent requires 22.05 kHz, so every clip was downsampled first; DSWP
  clicks carry energy to ~15 kHz, so the model is being fed a band-limited
  version of the signal. That is inherent to using it, but it is a real handicap.
- Aggregation is "clicks in the strongest predicted coda". Clips with several
  predicted codas could be scored differently.
- Published labels are one team's measurements, not ground truth.

These caveats limit how strongly the *tag* parity can be read. They do not
rescue the towed result: 0 of 12, and zero again under permissive thresholds.

## What follows

1. Run the full 1,382 clips for a definitive baseline. ~23 h on this CPU;
   ~1–2 h on one rented GPU.
2. Stratify that run by coda type and recording session, not by clip order.
3. Report the incumbent's own protocol (Pd/FAR) alongside exact click count, so
   the numbers are legible to the group that publishes coda detection.
