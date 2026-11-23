# How to mark clicks in sperm whale audio

This is the rulebook. Everyone marking audio follows it, so their marks can be
compared with everyone else's. It is deliberately short.

## In plain words

Sperm whales make loud clicks. They string them into short rhythmic bursts
called **codas** — a bit like a Morse code word. To study codas we need to know
exactly *when* each click happened. Timings are objective; the names people
give the resulting patterns are not. So we mark **click times only**, and let a
separate, clearly-labelled step turn those timings into pattern names.

That split matters. Whale researchers have published at least three
incompatible naming schemes for the same coda shapes. If we bake a name in at
the moment of marking, our data stops being comparable with anyone else's, and
we can never check our own work. If we mark times, every naming scheme is a
one-line conversion away.

## The three things being marked

- **Click onset** — the moment a click starts. Not its loudest point. Not where
  it ends. The first rise out of the background noise.
- **Coda** — a run of clicks separated by gaps of **less than 0.55 seconds**.
  This threshold is measured, not chosen: across 8,719 published Dominica codas
  the longest gap *inside* a coda is 0.80 s and the 99th percentile is 0.49 s.
  A more generous split chains separate codas into one and inflates the click
  count (we tested it: median 8 clicks instead of 5).
- **ICI** — inter-click interval, the gap between one onset and the next. This
  is the actual measurement of interest. Everything else is derived.

## Rules

1. **Mark the onset, at the resolution of the displayed spectrogram.** Round to
   the nearest 5 ms. Do not round to "the nearest obvious grid line".
2. **Mark every click you believe you can hear, including ones at the edge of
   the recording.** Do not stop at the clean middle.
3. **One mark per click.** A single sperm whale click contains several closely
   spaced pulses (its "multi-pulse" structure, roughly 2–5 ms apart). These are
   **one** click. Normally the tool's minimum spacing handles this; if you see
   two marks 2–5 ms apart, delete one.
4. **Do not mark echoes.** In shallow water a click bounces off the surface or
   seabed and returns 20–200 ms later. Echoes are quieter than the original and
   often repeat at a fixed delay. When in doubt, prefer the earlier, louder one.
5. **Do not mark echolocation trains.** Foraging sperm whales emit long, very
   regular streams of clicks — typically 8 or more clicks with near-identical
   spacing. Codas are short and rhythmically uneven. Mark the coda; leave the
   train alone.
6. **If two whales overlap, mark the louder stream and flag the clip.** Do not
   attempt to separate them. Flagging costs nothing; a wrong separation is
   invisible to everyone downstream.
7. **If you are not sure, mark it and flag it.** Never silently skip something
   ambiguous. The flag is what turns an uncertain mark into usable data; an
   omission just looks like agreement.

## Flags

Every clip carries two yes/no flags:

- `overlap` — more than one whale audible.
- `degraded` — clipping, strong flow noise, or an unclear coda.

Both are cheap to set and expensive to guess later.

## Turning timings into names

Not part of marking, and never merged into it. The conversion declares its
scheme in the output file, along with the version used. Current scheme:
Dominica convention, where the count of clicks per group is written out and
regular runs of equal spacing are written `nR`. So `1+1+3` is a click, a click,
then three; `5R1` is five evenly spaced clicks with a final longer gap.

Click counts above 10 are not renamed — they are rejected as merged codas or
trains, because the published Dominica repertoire spans 1 to 10 clicks.

## How we know the marks are any good

Two people independently mark a shared subset. Their marks are compared:

- **Did they find the same clicks?** Matching is one-to-one within 30 ms.
  Report precision, recall and F1.
- **How far off were the timings?** Mean and 95th-percentile error, in ms.
- **Did they get the same click count?** Exact-match rate.
- **Did they hear the same rhythm?** Agreement on the rhythm signature.

Then a stability check: jitter the marks by the disagreement we actually
observed, and see whether the derived pattern survives. A label that survives
98% of realistic jitter is safe to use. One that survives 55% is not, however
confident the marker felt.

Reported as a range, never as a single number. "F1 = 0.94, timing within 12 ms,
pattern stable in 97% of perturbations" tells a reader what they need.

## Known limits

- **The corpus is mixed, and that matters.** About 14% of it is animal-borne
  (DTag) audio; the rest is towed hydrophone. Clicks counted in towed recordings
  are wrong far more often, because shallow water sends each click back off the
  surface and the seabed and an unwary marker records the echoes as clicks.
  Expect disagreement to be much higher on towed clips, and say which rig a
  disagreement figure came from.
- **Shallow water is harder.** More echo, more overlap.
- **Small sample.** 1,501 clips is less than an hour of audio.
- **These are measurements of what is audible, not of what the whale emitted.**
  Every acoustic difference between whales shows up here as measurement noise
  unless it is controlled for.
