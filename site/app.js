"use strict";
/* Onboarding site engine. No dependencies, no storage, no network beyond
   audio/manifest.json and the wav files beside it. */

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

/* ───────────────────────── FFT + spectrogram ───────────────────────── */
function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const ur = re[i + k], ui = im[i + k];
        const vr = re[i + k + len / 2] * cr - im[i + k + len / 2] * ci;
        const vi = re[i + k + len / 2] * ci + im[i + k + len / 2] * cr;
        re[i + k] = ur + vr; im[i + k] = ui + vi;
        re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi;
        const ncr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = ncr;
      }
    }
  }
}

function spectrogram(buf, maxHz = 10000) {
  const x = buf.getChannelData(0), sr = buf.sampleRate;
  const N = 1024, hop = 256;                       // ~23 ms window, 5.8 ms hop
  const frames = Math.max(1, Math.floor((x.length - N) / hop) + 1);
  const maxBin = Math.min(N / 2, Math.round(maxHz / (sr / N)));
  const hann = new Float32Array(N);
  for (let i = 0; i < N; i++) hann[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1));
  const mags = [], re = new Float64Array(N), im = new Float64Array(N);
  let peak = 1e-12;
  for (let f = 0; f < frames; f++) {
    const off = f * hop;
    for (let i = 0; i < N; i++) { re[i] = (x[off + i] || 0) * hann[i]; im[i] = 0; }
    fft(re, im);
    const m = new Float32Array(maxBin);
    for (let b = 0; b < maxBin; b++) { m[b] = Math.hypot(re[b], im[b]); if (m[b] > peak) peak = m[b]; }
    mags.push(m);
  }
  return { mags, frames, maxBin, peak, dur: buf.duration, sr, maxHz };
}

function paint(canvas, spec, marks, truth) {
  const W = canvas.width, H = canvas.height, ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);
  const { mags, frames, maxBin, peak, dur } = spec;
  const LO = -72, HI = 0;
  const off = document.createElement("canvas");
  off.width = frames; off.height = maxBin;
  const octx = off.getContext("2d"), img = octx.createImageData(frames, maxBin), d = img.data;
  for (let f = 0; f < frames; f++) {
    const col = mags[f];
    for (let b = 0; b < maxBin; b++) {
      const db = 20 * Math.log10(Math.max(col[b], 1e-12) / peak);
      const t = Math.min(1, Math.max(0, (db - LO) / (HI - LO)));
      const p = ((maxBin - 1 - b) * frames + f) * 4;
      d[p]     = Math.round(255 * Math.pow(t, 1.8));
      d[p + 1] = Math.round(255 * Math.pow(t, 1.15) * 0.94);
      d[p + 2] = Math.round(255 * (t < 0.55 ? t * 1.45 : 0.79 + 0.21 * t));
      d[p + 3] = 255;
    }
  }
  octx.putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(off, 0, 0, W, H);

  // time axis
  ctx.strokeStyle = "rgba(255,255,255,.10)"; ctx.fillStyle = "#7c879c";
  ctx.font = "11px ui-monospace,monospace"; ctx.lineWidth = 1;
  const step = dur > 2 ? 0.5 : 0.25;
  for (let t = 0; t <= dur + 1e-9; t += step) {
    const px = (t / dur) * W;
    ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, H); ctx.stroke();
    ctx.fillText(t.toFixed(step < 0.5 ? 2 : 1) + "s", px + 3, H - 5);
  }
  // freq axis
  ctx.fillStyle = "#7c879c";
  ctx.fillText((spec.maxHz / 1000).toFixed(0) + " kHz", 4, 13);

  const line = (t, colour, dashed) => {
    const px = (t / dur) * W;
    ctx.save(); ctx.strokeStyle = colour; ctx.lineWidth = 2;
    ctx.setLineDash(dashed ? [5, 4] : []);
    ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, H); ctx.stroke(); ctx.restore();
  };
  (truth || []).forEach(t => line(t, "#ffffff88", true));
  (marks || []).forEach(t => line(t, "#ffc861", false));
}

/* ───────────────────────── audio ───────────────────────── */
let AC = null;
const buffers = {};
const specs = {};
function ctx() { return AC || (AC = new (window.AudioContext || window.webkitAudioContext)()); }

async function decode(entry) {
  if (buffers[entry.id]) return buffers[entry.id];
  const res = await fetch(entry.file);
  if (!res.ok) throw new Error(`could not load ${entry.file}`);
  const buf = await ctx().decodeAudioData(await res.arrayBuffer());
  buffers[entry.id] = buf;
  specs[entry.id] = spectrogram(buf);
  return buf;
}

let playing = null;   // { src, startedAt, dur }

function stopAll() {
  if (playing && playing.src) { try { playing.src.stop(); } catch (e) {} }
  playing = null;
}

function play(entry, onProgress) {
  stopAll();
  const src = ctx().createBufferSource();
  src.buffer = buffers[entry.id];
  src.connect(ctx().destination);
  const start = ctx().currentTime;
  src.start();
  playing = { src, startedAt: start, dur: src.buffer.duration };
  src.onended = () => { playing = null; onProgress && onProgress(null); };
  return { start, dur: src.buffer.duration };
}

function progressTime() {
  if (!playing) return null;
  return Math.min(playing.dur, ctx().currentTime - playing.startedAt);
}

/* ───────────────────────── player card ───────────────────────── */
function playerCard(el, entry) {
  const mode = el.dataset.mode || "plain";
  const marks = [];
  let truthShown = false;
  let scoring = false;

  el.innerHTML = `
    <div class="row">
      <button class="primary play">▶ play</button>
      <span class="pill ${entry.rig.includes("tag") ? "tag" : "towed"}">${entry.rig}</span>
      <span class="pill">${entry.codaType}</span>
      <span class="small dim time">—</span>
    </div>
    <canvas class="spec" width="1400" height="${mode === "mark" ? 220 : 180}"></canvas>
    ${mode === "mark" ? `
      <div class="row" style="margin-top:10px">
        <button class="score">score my marks</button>
        <button class="clear">clear</button>
        <span class="score-readout score"></span>
      </div>` : ""}
    <details style="margin-bottom:0">
      <summary>Show the answer</summary>
      <div class="small"></div>
    </details>`;

  const canvas = el.querySelector("canvas");
  const timeEl = el.querySelector(".time");
  const btn = el.querySelector(".play");
  const detail = el.querySelector("details div");
  const readout = el.querySelector(".score-readout");

  const redraw = () => {
    if (!specs[entry.id]) return;   // nothing decoded yet: nothing to paint
    paint(canvas, specs[entry.id], marks, truthShown ? entry.onsets : null);
  };

  const reveal = () => {
    detail.innerHTML =
      `<b>${entry.nClicks} clicks</b> · published type <code>${entry.codaType}</code><br>` +
      `Gaps (ms): ${entry.icis.map(v => Math.round(v * 1000)).join(", ")}<br>` +
      `Clan ${entry.clan}, unit ${entry.unit}, ${entry.date}.` +
      (entry.detected == null ? "" :
        `<br><span class="dim">Our detector found ${entry.detected} click` +
        `${entry.detected === 1 ? "" : "s"} on this clip` +
        `${entry.detected === entry.nClicks ? " — right." : "."}</span>`);
  };

  // A blank dark rectangle reads as broken; say what to do.
  (function placeholder() {
    const c = canvas.getContext("2d");
    c.fillStyle = "#06080c"; c.fillRect(0, 0, canvas.width, canvas.height);
    c.fillStyle = "#4b5568";
    c.font = "15px ui-sans-serif,system-ui,sans-serif";
    c.fillText("press play to see the spectrogram", 18, canvas.height / 2);
  })();

  el.querySelector("details").addEventListener("toggle", e => {
    if (e.target.open) { truthShown = true; reveal(); redraw(); }
    else { truthShown = false; redraw(); }
  });

  btn.onclick = async () => {
    btn.disabled = true;
    try { await decode(entry); } catch (err) { timeEl.textContent = String(err); btn.disabled = false; return; }
    redraw();
    btn.disabled = false;
    if (playing) { stopAll(); btn.textContent = "▶ play"; timeEl.textContent = "—"; return; }
    btn.textContent = "■ stop";
    const { dur } = play(entry, () => { btn.textContent = "▶ play"; timeEl.textContent = "—"; });
    timeEl.textContent = dur.toFixed(2) + " s";
    const tick = () => {
      const t = progressTime();
      if (t === null) { btn.textContent = "▶ play"; timeEl.textContent = "—"; return; }
      timeEl.textContent = t.toFixed(2) + " s";
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  if (mode === "mark") {
    canvas.style.cursor = "crosshair";
    canvas.addEventListener("click", ev => {
      if (!specs[entry.id]) return;
      // Editing after a score resets the comparison, so a second attempt is
      // scored on its own merits rather than against the previous verdict.
      if (scoring) { scoring = false; readout.textContent = ""; }
      const r = canvas.getBoundingClientRect();
      const t = ((ev.clientX - r.left) / r.width) * specs[entry.id].dur;
      const snapped = Math.round(t / 0.005) * 0.005;
      const near = marks.findIndex(m => Math.abs(m - snapped) < 0.012);
      if (near >= 0) marks.splice(near, 1); else marks.push(snapped);
      marks.sort((a, b) => a - b);
      redraw();
    });
    el.querySelector(".clear").onclick = () => {
      marks.length = 0; scoring = false; readout.textContent = ""; redraw();
    };
    el.querySelector(".score").onclick = () => {
      if (!marks.length) { readout.innerHTML = `<span class="dim">click the spectrogram first</span>`; return; }
      scoring = true; truthShown = true; reveal();
      el.querySelector("details").open = true;   // reveal() writes into a closed panel otherwise
      redraw();
      const TOL = 0.030;
      const used = new Set();
      let hit = 0;
      for (const m of marks) {
        for (let i = 0; i < entry.onsets.length; i++) {
          if (!used.has(i) && Math.abs(entry.onsets[i] - m) <= TOL) { used.add(i); hit++; break; }
        }
      }
      const prec = hit / marks.length, rec = hit / entry.onsets.length;
      const f1 = (prec + rec) ? 2 * prec * rec / (prec + rec) : 0;
      const cls = f1 >= 0.9 ? "ok" : f1 >= 0.6 ? "" : "no";
      readout.innerHTML =
        `you found <b>${hit}</b> of ${entry.onsets.length} · precision ${prec.toFixed(2)} · ` +
        `recall ${rec.toFixed(2)} · <span class="${cls}"><b>F1 ${f1.toFixed(2)}</b></span>` +
        `<br><span class="dim">within 30 ms counts as a match. Dashed white = published; amber = yours.</span>`;
    };
  }

  return { redraw, entry };
}

/* ───────────────────── free browsing of the repertoire ───────────────────── */
function exploreGrid(manifest) {
  const grid = document.getElementById("exploreGrid");
  if (!grid) return;
  manifest.filter(e => e.id.startsWith("x-")).forEach(e => {
    const div = document.createElement("div");
    div.className = "player";
    grid.appendChild(div);
    playerCard(div, e);
  });
}

/* ─────────────────── lesson 3: naming table from the audio ─────────────────── */
function shapeTable(manifest) {
  const body = document.getElementById("shapeTable");
  if (!body) return;
  const rows = ["tag113", "tag5r1", "tag4r2"].map(id => manifest.find(e => e.id === id)).filter(Boolean);
  if (!rows.length) { body.innerHTML = ""; return; }
  body.innerHTML = rows.map(e =>
    `<tr><td style="padding:6px 0"><code>${e.codaType}</code></td><td>${e.nClicks}</td>` +
    `<td>${e.icis.map(v => Math.round(v * 1000)).join(", ")}</td></tr>`).join("");
}

/* ───────────────────────── lesson 4: the leak ───────────────────────── */
function leakDemo(manifest) {
  const box = $("#leakBtns"), out = $("#leakOut");
  if (!box) return;
  manifest.slice(0, 5).forEach(e => {
    const b = document.createElement("button");
    b.textContent = `clip ${e.clip} · ${e.rig.includes("tag") ? "tag" : "towed"} · ${e.fileDur.toFixed(2)} s`;
    b.onclick = () => {
      out.innerHTML =
        `<code>original file was ${e.fileDur.toFixed(3)} s</code> → minus 1.000 s of padding → ` +
        `the coda lasted <b>${(e.fileDur - 1).toFixed(3)} s</b>.<br>` +
        `<span class="dim">(The clip playing on this page is a ${e.clipLen.toFixed(3)} s excerpt of ` +
        `it — same coda, trimmed tighter for teaching.)</span><br>` +
        `Duration alone is ambiguous — dozens of codas share a length — but the clips are stored in ` +
        `recording order, so a <em>run</em> of consecutive matches pins each one down. That resolves ` +
        `to:<br><br>` +
        `<b>${e.codaType}</b> · ${e.nClicks} clicks · clan ${e.clan} · unit ${e.unit} · ${e.date}.<br>` +
        `<span class="dim">No audio analysis. That's the leak.</span>`;
    };
    box.appendChild(b);
  });
}

/* ───────────────────────── lesson 6: stability ───────────────────────── */
function stabilityDemo(manifest) {
  const fast = manifest.find(e => e.id === "fast");
  const slow = manifest.find(e => e.id === "slow");
  const slider = $("#jit"), label = $("#jitv");
  const outF = $("#stabFast"), outS = $("#stabSlow");
  if (!fast || !slow || !slider) return;

  const gauss = () => {
    let u = 0, v = 0;
    while (!u) u = Math.random();
    while (!v) v = Math.random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };

  function survives(onsets, jitterMs, trials = 250) {
    const base = onsets.slice(1).map((t, i) => t - onsets[i]);
    const scale = base.reduce((a, b) => a + b, 0) / base.length;
    let ok = 0;
    for (let k = 0; k < trials; k++) {
      const p = onsets.map(t => t + (jitterMs / 1000) * gauss()).sort((a, b) => a - b);
      let good = true;
      const d = p.slice(1).map((t, i) => Math.abs((t - p[i]) - base[i]));
      const mean = d.reduce((a, b) => a + b, 0) / d.length;
      const max = Math.max(...d);
      if (!(mean <= 0.15 * scale && max <= 0.30 * scale)) good = false;
      if (good) ok++;
    }
    return ok / trials;
  }

  function update() {
    const j = Number(slider.value);
    label.textContent = j + " ms";
    const f = survives(fast.onsets, j), s = survives(slow.onsets, j);
    outF.textContent = Math.round(f * 100) + "%";
    outF.style.color = f >= 0.9 ? "var(--good)" : f >= 0.6 ? "var(--warm)" : "var(--bad)";
    outS.textContent = Math.round(s * 100) + "%";
    outS.style.color = s >= 0.9 ? "var(--good)" : s >= 0.6 ? "var(--warm)" : "var(--bad)";
  }
  slider.addEventListener("input", update);
  update();
}

/* ───────────────────────── flashcards ───────────────────────── */
const CARDS = [
  ["Coda", "A short rhythmic burst of clicks, used socially. The unit everyone studies."],
  ["Click", "One pulse inside a coda. Sperm whale clicks are among the loudest sounds made by any animal."],
  ["ICI", "Inter-click interval — the gap between consecutive clicks. The actual measurement of a coda."],
  ["Clan", "A group of whales sharing a coda repertoire. Learned, not genetic — this is culture."],
  ["Unit", "A smaller social group within a clan; the whales that actually swim together."],
  ["Why we mark clicks, not coda names", "At least three incompatible naming schemes exist. Times are objective; names are conventions."],
  ["1+1+3", "Groups of 1, 1 and 3 clicks — five in total, with the longest gaps between the groups. Dominica's most common shape at 42% of codas."],
  ["5R1", "Five regular clicks in quick succession, gaps around 60–100 ms. 5R1, 5R2 and 5R3 all have five clicks and differ only in spacing — the label is compressed description, not a name from a rulebook."],
  ["DSWP", "Dominica Sperm Whale Project — the long-running fieldwork that produced the public audio and the coda table."],
  ["DTag", "A suction-cupped tag that records from the whale itself. Near-field audio: few echoes."],
  ["Towed hydrophone", "A microphone dragged behind a boat. Far-field: shallow water sends every click back as echoes."],
  ["Multipath", "One click arriving several times — direct, then off the surface and seabed. Looks like extra clicks."],
  ["Why 59% vs 12%", "Exact click-count accuracy on whale-borne vs towed clips. Same code; multipath is the difference."],
  ["The leak", "Public clips are one coda plus exactly 1.000 s of padding, so file length reveals the label."],
  ["Why the leak matters", "Any evaluation treating those clips as unlabelled is invalid — and random splits don't fix it."],
  ["IAA", "Inter-annotator agreement: give the same audio to two people and measure how far apart they land."],
  ["F1", "One number combining precision (of the clicks you marked, how many were real) and recall (of the real ones, how many you found)."],
  ["Stability", "Jitter the clicks by the observed disagreement, then ask whether the derived label survives. A label that survives 99% is safe. Run over the corpus's own published timings, a fast coda keeps its rhythm only about half the time — but that is a simulation, not a human agreement study."],
  ["Why fast codas are harder", "A fixed timing error is a bigger fraction of a 90 ms gap than a 300 ms gap, so the rhythm flips more easily."],
  ["Why we don't use coda names in code", "Names bake in a controversy. The pipeline emits times; a declared step derives names."],
  ["Why 3–40 clicks and 1–10 both appear", "Codas range widely across populations (up to 40 clicks); the published Dominica table records 1 to 10. Always say which population a range describes."],
  ["Does any of this prove meaning?", "No. Structure is evidenced; meaning is not. Nobody has shown a coda stands for anything."]
];

(function flashcards() {
  const box = $("#flash"), text = $("#flashText"), meta = $("#flashMeta");
  if (!box) return;
  let i = 0, back = false;
  const show = () => {
    const [q, a] = CARDS[i];
    text.textContent = back ? a : q;
    box.classList.toggle("back", back);
    meta.textContent = `${i + 1} / ${CARDS.length}` + (back ? "" : " · click to flip");
  };
  box.onclick = () => { back = !back; show(); };
  $("#fFlip").onclick = e => { e.stopPropagation(); back = !back; show(); };
  $("#fNext").onclick = e => { e.stopPropagation(); i = (i + 1) % CARDS.length; back = false; show(); };
  $("#fPrev").onclick = e => { e.stopPropagation(); i = (i - 1 + CARDS.length) % CARDS.length; back = false; show(); };
  window.addEventListener("keydown", e => {
    if (e.target.tagName === "INPUT") return;
    if (e.key === "ArrowRight") { i = (i + 1) % CARDS.length; back = false; show(); }
    if (e.key === "ArrowLeft") { i = (i - 1 + CARDS.length) % CARDS.length; back = false; show(); }
    if (e.key === " ") {
      const r = box.getBoundingClientRect();
      const visible = r.top < window.innerHeight * 0.8 && r.bottom > window.innerHeight * 0.2;
      if (visible) { e.preventDefault(); back = !back; show(); }
    }
  });
  show();
})();

/* ───────────────────────── quiz ───────────────────────── */
const QUIZ = [
  {
    q: "A colleague reports \u201cour detector is 94% accurate on sperm whale codas.\u201d What's the first thing you ask?",
    a: ["Which recording rig, and what does 'accurate' mean per clip?", "How big is the training set?", "Which coda types does it cover?", "Is the code open source?"],
    correct: 0,
    why: "A pooled accuracy figure across towed and whale-borne audio describes neither. And 'accurate' usually hides whether it's a classification score or a per-clip click count."
  },
  {
    q: "Why does the pipeline output click times instead of coda names like 5R1?",
    a: ["Names are copyrighted", "Because names are longer to store", "Because several incompatible naming schemes exist, so names are derived later under a declared scheme", "Because whales don't have names"],
    correct: 2,
    why: "Times are objective; names are conventions. Baking a name in makes the data incomparable with other labs."
  },
  {
    q: "You find a public dataset of whale audio with no metadata. Why might it still be labelled?",
    a: ["The file duration can encode the label if the clips were cut from a published table", "It can't be", "Whale songs are recognisable by ear", "The sample rate gives it away"],
    correct: 0,
    why: "Exactly what happened here: each clip is one coda plus 1.000 s of padding, so duration minus 1.000 recovers the published label."
  },
  {
    q: "Two annotators agree on a coda 99% of the time. What's still missing before you trust it?",
    a: ["Nothing, that's excellent", "Whether they used the same software", "Whether they're both researchers", "Whether that figure covers fast codas too \u2014 they're far more fragile"],
    correct: 3,
    why: "On the corpus's own published timings, the same jitter test leaves a slow coda's rhythm intact about 99% of the time and a fast coda's about 46%. That is a simulation, not an annotator study — and it is still enough to show why one agreement number hides the hard third of the corpus."
  },
  {
    q: "A detector reports a confident coda in a clip of pure background noise. What does that tell you?",
    a: ["The noise is actually a coda", "The clip is too short", "There's no minimum signal-to-noise floor, so chance peaks can assemble into a 'coda'", "The sample rate is wrong"],
    correct: 2,
    why: "Chance peaks clear a simple threshold often enough to assemble three 'clicks' out of noise. A minimum signal-to-noise floor stops it — that floor is in the pipeline, and it costs a little accuracy."
  },
  {
    q: "Which claim would you reject outright?",
    a: ["\u201cWe've decoded the meaning of several codas.\u201d", "\u201cWhale-borne clips are counted more accurately than towed ones.\u201d", "\u201cFast codas are harder to annotate consistently.\u201d", "\u201cThe public corpus leaks its own labels.\u201d"],
    correct: 0,
    why: "Structure is evidenced; meaning is not. No coda has been shown to stand for anything. Everything else on that list is measured."
  }
];

(function quiz() {
  const box = $("#quizBox");
  if (!box) return;
  let answered = 0, right = 0;
  QUIZ.forEach((item, qi) => {
    const el = document.createElement("div");
    el.className = "q";
    el.innerHTML = `<div class="stem">${qi + 1}. ${item.q}</div>`;
    const why = document.createElement("div");
    why.className = "why";
    why.textContent = item.why;
    item.a.forEach((optText, oi) => {
      const b = document.createElement("button");
      b.className = "opt";
      b.textContent = optText;
      b.onclick = () => {
        if (el.dataset.done) return;
        el.dataset.done = "1";
        answered++;
        if (oi === item.correct) { b.classList.add("correct"); right++; }
        else {
          b.classList.add("wrong");
          el.querySelectorAll(".opt")[item.correct].classList.add("correct");
        }
        why.classList.add("show");
        if (answered === QUIZ.length) {
          const s = $("#quizScore");
          s.style.display = "block";
          s.innerHTML = `<b>${right} / ${QUIZ.length}</b> — ` +
            (right === QUIZ.length ? "you can review my work."
              : right >= 4 ? "solid. Re-read lesson 5 and the review checklist."
                : "worth another pass through lessons 1–5.");
        }
      };
      el.appendChild(b);
    });
    el.appendChild(why);
    box.appendChild(el);
  });
})();

/* ───────────────────────── nav ───────────────────────── */
// Fragment navigation is blocked in the sandboxed preview, so #anchors do
// nothing. Scroll the target into view by script instead; keep href for the
// case where this page is ever served plainly.
(function nav() {
  const links = [...document.querySelectorAll('nav a[href^="#"]')];
  // The sticky bar changes height when the chips wrap; keep scroll targets
  // clear of it.
  const navEl = document.querySelector("nav");
  const syncNavHeight = () => {
    if (navEl) document.documentElement.style.setProperty("--navh", navEl.offsetHeight + "px");
  };
  syncNavHeight();
  window.addEventListener("resize", syncNavHeight);

  links.forEach(a => {
    a.addEventListener("click", e => {
      const target = document.getElementById(a.getAttribute("href").slice(1));
      if (!target) return;
      e.preventDefault();
      // Instant, not smooth.  In the preview the page is embedded in an iframe
      // that does not scroll itself -- the PARENT document does -- and a smooth
      // scroll across that boundary animates to the wrong offset or gets reset.
      // Behavior "auto" propagates to the parent correctly; measured landing
      // was within a few pixels of the sticky bar.
      target.scrollIntoView({ behavior: "auto", block: "start" });
      // Drop focus so the chip does not stay outlined after the jump.
      if (a.blur) a.blur();
    });
  });
  // Highlight whichever lesson is currently on screen.
  const sections = links.map(a => document.getElementById(a.getAttribute("href").slice(1))).filter(Boolean);
  if (!("IntersectionObserver" in window) || !sections.length) return;
  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      links.forEach(a => a.classList.toggle("active", a.getAttribute("href") === "#" + en.target.id));
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  sections.forEach(sec => io.observe(sec));
})();

/* ───────────────────────── boot ───────────────────────── */
(async function boot() {
  let manifest = [];
  try {
    manifest = await (await fetch("audio/manifest.json")).json();
  } catch (e) {
    console.error("manifest missing", e);
  }
  const byId = Object.fromEntries(manifest.map(m => [m.id, m]));
  $$(".player").forEach(el => {
    const entry = byId[el.dataset.clip];
    if (entry) playerCard(el, entry);
    else el.textContent = "audio unavailable";
  });
  shapeTable(manifest);
  exploreGrid(manifest);
  leakDemo(manifest);
  stabilityDemo(manifest);
})();
