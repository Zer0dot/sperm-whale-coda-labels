# What already exists

Survey run 26 Nov 2026. Three parallel sweeps — software, data, literature — each
required to fetch and read what it cited rather than trust abstracts. Claims we
could not verify are marked **unverified**. Every DOI here resolved against
CrossRef or Europe PMC on the day of the survey.

**The short version.** Coda *naming* is essentially solved and we should not
rebuild it. Coda *click timing* is not, nobody publishes a click-count metric,
and no benchmark exists. The one asset we hold that nobody else has is the
audio↔label join. So the defensible contribution is a benchmark and a far-field
detector, not a better classifier.

---

## 1. What exists, by layer

| Layer | State | Who |
|---|---|---|
| Click detection (audio → click times) | **Open.** Two implementations, neither reports click-count accuracy | Gubnitsky 2025 (`10.1038/s41598-025-97009-z`, MIT code); CETI `Coda-detector` (MATLAB, **no licence file**) |
| Coda presence (clip → coda / no coda) | **Effectively solved at clip level** — 93–97% with frozen embeddings | AVES/BirdNET linear probes; Bermant 2019 reports 99.5% on 650 spectrograms |
| Coda type (measurements → label) | **Solved. Do not rebuild.** 97.5% Dominica, 93.6% ETP — from inter-click intervals, not audio | Bermant 2019; `earthspecies/sperm-whale-clan-and-coda-detection` (Apache-2.0) |
| Coda structure (rhythm, rubato, ornamentation) | Active frontier | Sharma 2024 Nat Commun; Cordivari 2026 preprint (`10.32942/x2f100`) |
| Meaning / semantics | **No evidence.** Now contested in print | PNAS 2026-11-18 critique (`10.1073/pnas.2609992123`) |

Two things worth reading twice:

- **Bermant's 97.5% is not an audio result.** It is an LSTM classifying
  already-measured ICIs. The audio-side number is 99.5% click *presence* on 650
  spectrograms. Type naming from good measurements is nearly free.
- **The language framing took a direct hit on 18 November 2026.** Rendell,
  Sayigh, Janik, Jensen, King, Madsen and Tyack, *PNAS*: "Anthropocentric
  comparisons with human language impede our understanding of whale
  communication." Any sentence of ours containing "language", "grammar" or
  "meaning" is now contradicted by the sources we would cite.

---

## 2. Build / build on / borrow / skip

**BUILD — nobody has it**
- A click-level detector evaluated on the 1,382 joined clips with a
  **recording-held-out split**, reporting *exact click-count match* and ICI
  error. No published detector reports either.
- A **44.1 kHz front end.** Everything open runs at 16–22.05 kHz. The MIT
  pipeline resamples to 22.05 kHz (Nyquist 11 kHz), discarding the top third of
  a click that carries energy to ~15 kHz.
- The **join itself** and a frozen split file. See §3.

**BUILD ON**
- `martin-rodriguez-munoz/sperm_whale_click_detection_pipeline` (**MIT**,
  verified by clone: candidate CNN → transformer re-scoring → clustering;
  checkpoints in releases; ~1.6 GB VRAM inference). Its architecture matches the
  problem exactly and its training file IDs look like DSWP recordings. Retrain
  phase 1 at 44.1 kHz.
- `earthspecies/sperm-whale-clan-and-coda-detection` (Apache-2.0) for the
  measurements → type step.

**BORROW — read, do not link**
- CETI `Coda-detector`'s *method* (TKEO, multipulse counting, resonant-frequency
  constraints, graph clustering) is the strongest classical design. It has **no
  licence file**, so we may read it and must not copy it.
- Its published protocol — Pd/FAR per minute, CDF of click recovery — so our
  numbers are legible to the only group that has published coda detection.
- PAMGuard (GPL-3.0) as an independent classical baseline, run as a separate
  process; its output can be used, its code cannot enter our product.

**SKIP**
- Rebuilding coda-type classification (97.5%, two permissive implementations).
- Rebuilding clip-level coda/no-coda (93–97% with frozen embeddings).
- Re-deriving vowel classification — code and data are already on OSF/GitHub.
- `Project-CETI/click-detector` (MATLAB, dead since 2023, needs a third-party
  toolbox) and WhAM as a detector (it is a generator).
- animal2vec fine-tuning (pinned fairseq, Python ≤3.9 — a maintenance trap).

---

## 3. What is genuinely open

1. **No published click-count accuracy anywhere.** Our 58.8% / 12.2% has no
   counterpart. We would define the metric — an advantage, if we define it well.
2. **No benchmark for coda audio.** No DCLDE year ran a coda task (there was no
   2014/2016/2020/2026 workshop; next is Ithaca 2027). WhAM publishes no split
   file and its 96.8% headline is a random-split number with model selection on
   the test set — do not benchmark against it.
3. **No public weights for the far-field regime.** Our 12.2% on towed audio is
   the exposed flank, and the honest headline.
4. **No cetacean click encoder.** Bioacoustic self-supervision is tuned for
   16–32 kHz tonal signals; clicks are 2–15 kHz broadband transients with a
   multipulse structure nothing in that literature models.

**The highest-value artefact we can ship** is not a model. It is: the clip→row
join as a versioned CSV (with the 119 unmatched clips listed), a frozen
type-and-unit-stratified split, and a metric definition — so anyone can
reproduce the pairing. Without the join nobody can rebuild it.

---

## 4. Where to cooperate

- **Shane Gero / DSWP is the gatekeeper** for the Dominica audio and the join
  key. The right approach is to offer co-authorship and publish the join openly,
  not to guess mappings. The ~10k-coda corpus behind WhAM is private; the
  README says so explicitly.
- **Gubnitsky & Diamant's detector** is MIT and public — cite it as the baseline
  rather than re-deriving it.
- **Coda-detector's protocol** is public and citable even though its code is not
  licensed.
- **Bermant 2019 supplementary tables** are CC-BY and are the cheapest new
  science available: 16,995 Eastern Tropical Pacific codas, seven clans,
  1985–2014, barely touched by modern ML.

**Licence traps:** WhAM weights are CC-BY-NC-ND (do not redistribute); most CETI
repos have no licence at all (readable, not reusable); Watkins is "all rights
reserved" and its WHOI site currently serves a 2,371-byte maintenance page;
Orcasound is CC-BY-NC-SA.

---

## 5. Consequences for our plan

The plan we agreed — harness, then echo suppression, then a learned front end —
survives, with three amendments:

1. **The join and the split ship first**, as their own citable artefact.
2. **The baseline to beat is the MIT pipeline, not our peak-picker** — and it
   must be beaten on the far-field subset, where it has published nothing.
3. **Report agreement, not just accuracy.** Observers disagree on coda types
   (Rendell & Whitehead 2003, `10.1080/09524622.2003.9753513`), so "accuracy
   against inherited labels" needs an uncertainty statement next to it.

One option worth putting on the table: the most credible open scientific
problem we could actually move is **not** a better classifier. It is what an
"exchange" is and whether exchange-level structure survives control for
segmentation — the load-bearing joint of the 2024 flagship, currently supported
by one unrefereed preprint, and answerable with the agreement and
threshold-sensitivity machinery we have already built.

---

## 6. Verified / unverified

Verified by fetch: all DOIs above; the MIT pipeline (cloned, licence read,
22.05 kHz assumption confirmed in code); the PNAS critique's title, venue and
date; Bermant's abstract text; `orrp/DSWP` download (585,491,783 bytes);
Bermant S6/S7 tables (867,711 and 1,753,245 bytes); Watkins' maintenance page.

**Unverified:** the Zenodo audit alleging the public release is ordered by
acoustic label (preprint, not reproduced) — though splitting by recording is
correct regardless; whether WhAM's corpus overlaps DSWP; WhAM's arXiv IDs;
the exact article type of the PNAS piece.
