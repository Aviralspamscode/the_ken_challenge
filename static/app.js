const logEl = document.getElementById("log");
const curtainEl = document.getElementById("curtain");
const curtainWho = document.getElementById("curtainWho");
const curtainReq = document.getElementById("curtainReq");
const curtainText = document.getElementById("curtainText");
let currentCurtain = null;
let currentSample = null;

function pretty(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function addEntry(kind, title, body, cls) {
  const el = document.createElement("div");
  el.className = `entry ${cls || kind}`;
  const time = new Date().toLocaleTimeString("en-IN", { hour12: false });
  el.innerHTML = `<span class="t">${time}</span><div class="k">${title}</div>`;
  if (body) {
    const pre = document.createElement("pre");
    pre.textContent = typeof body === "string" ? body : pretty(body);
    el.appendChild(pre);
  }
  logEl.appendChild(el);
  logEl.scrollTop = logEl.scrollHeight;
}

function bubble(alias, text, dir, meta, audioB64) {
  const thread = document.getElementById(`thread-${alias}`);
  if (!thread || !text) return;
  const b = document.createElement("div");
  b.className = `bubble ${dir}`;
  b.innerHTML = `${escapeHtml(text)}${meta ? `<small>${escapeHtml(meta)}</small>` : ""}`;
  if (audioB64) {
    const play = document.createElement("button");
    play.type = "button";
    play.className = "spk";
    play.textContent = "▶";
    play.onclick = () => enqueueAudio(audioB64);
    b.appendChild(play);
    enqueueAudio(audioB64);
  }
  thread.appendChild(b);
  thread.scrollTop = thread.scrollHeight;
}

const audioQueue = [];
let audioBusy = false;
function enqueueAudio(b64) {
  if (!b64) return;
  audioQueue.push(b64);
  pumpAudio();
}
function pumpAudio() {
  if (audioBusy || !audioQueue.length) return;
  audioBusy = true;
  const a = new Audio(`data:audio/wav;base64,${audioQueue.shift()}`);
  a.onended = () => {
    audioBusy = false;
    pumpAudio();
  };
  a.onerror = () => {
    audioBusy = false;
    pumpAudio();
  };
  a.play().catch(() => {
    audioBusy = false;
    pumpAudio();
  });
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function aliasFromPhoneOrName(payload) {
  const a = (payload.alias || "").toLowerCase();
  if (["ritika", "sunita", "ramesh"].includes(a)) return a;
  const blob = `${payload.name || ""} ${payload.to || ""} ${payload.from || ""}`.toLowerCase();
  if (blob.includes("ritika") || blob.includes("buyer")) return "ritika";
  if (blob.includes("sunita") || blob.includes("maa")) return "sunita";
  if (blob.includes("ramesh")) return "ramesh";
  return payload.alias || "ritika";
}

function onEvent(ev) {
  const { kind, payload } = ev;
  if (kind === "clock") {
    document.getElementById("clockChip").textContent = payload.clock || "";
  }
  if (kind === "event_in") {
    document.getElementById("clockChip").textContent = payload.clock || "";
    addEntry(kind, `IN · ${payload.title}`, { source: payload.source, payload: payload.payload }, "http");
    document.getElementById("busyChip").textContent = "thinking";
    document.getElementById("busyChip").className = "busy";
  }
  if (kind === "model_start") {
    return;
  }
  if (kind === "model_text") {
    addEntry(kind, "MODEL", payload.text);
  }
  if (kind === "decision") {
    addEntry(kind, payload.raw || "DECISION", "", "decision");
  }
  if (kind === "tool_call") {
    addEntry(kind, `TOOL → ${payload.name}`, payload.args, "tool");
  }
  if (kind === "tool_result") {
    addEntry(kind, `TOOL ← ${payload.name}`, payload.result, "tool");
  }
  if (kind === "http_request") {
    addEntry(kind, `${payload.partner} ${payload.method} ${payload.url || payload.endpoint || ""}`, payload.body || payload, "http");
  }
  if (kind === "http_response") {
    addEntry(kind, `${payload.partner} ${payload.status}`, payload.body, "http");
  }
  if (kind === "call_booth") {
    openCall(payload);
    addEntry(kind, `CALL · ${payload.name}`, payload.reason, "decision");
  }
  if (kind === "call_turn") {
    addEntry(kind, "CALL turn", payload, "http");
  }
  if (kind === "call_ended") {
    closeCall();
    addEntry(kind, "CALL ended", payload.result, "http");
  }
  if (kind === "curtain_request") {
    openCurtain(payload);
    addEntry(kind, `CURTAIN · ${payload.partner} ${payload.method} ${payload.endpoint}`, payload.request, "err");
  }
  if (kind === "curtain_response") {
    closeCurtain();
    addEntry(kind, "CURTAIN pasted", payload.response, "http");
  }
  if (kind === "whatsapp_out") {
    const meta = payload.tts ? `Gnani ${payload.tts.voice}` : payload.channel;
    bubble(aliasFromPhoneOrName(payload), payload.text, "out", meta, payload.audio_b64);
  }
  if (kind === "whatsapp_in") {
    const text = payload.text || payload.transcript || "(voice note)";
    const meta = payload.tts ? `Gnani ${payload.tts.voice}` : payload.type;
    bubble(aliasFromPhoneOrName(payload), text, "in", meta, payload.audio_b64);
  }
  if (kind === "agent_note") {
    addEntry(kind, "NOTE", payload.text);
  }
  if (kind === "agent_error") {
    addEntry(kind, "ERROR", payload.message, "err");
  }
  if (kind === "model_end") {
    document.getElementById("busyChip").textContent = "idle";
    document.getElementById("busyChip").className = "idle";
  }
  if (kind === "reset") {
    logEl.innerHTML = "";
    ["ritika", "sunita"].forEach((a) => {
      document.getElementById(`thread-${a}`).innerHTML = "";
    });
    addEntry("reset", "Day reset", payload.clock);
    closeCall();
  }
}

let currentCall = null;
let wavCtx = null;
let wavProc = null;
let wavStream = null;
let wavChunks = [];

function callLine(role, text) {
  const el = document.createElement("p");
  el.className = `call-line ${role}`;
  el.textContent = `${role === "assistant" ? "Ghar Pass" : "Sunita"}: ${text}`;
  document.getElementById("callThread").appendChild(el);
}

function playB64(b64) {
  const src = `data:audio/wav;base64,${b64}`;
  const audio = new Audio(src);
  audio.play().catch(() => {});
}

async function openCall(payload) {
  currentCall = payload.id;
  document.getElementById("callWho").textContent = `${payload.name}  ${payload.phone}  ·  ${payload.reason}`;
  document.getElementById("callThread").innerHTML = "";
  document.getElementById("callBooth").classList.remove("hidden");
  document.getElementById("callHint").textContent = "Connecting Gnani TTS…";
  const res = await fetch(`/api/call/${currentCall}/open`);
  const data = await res.json();
  if (!res.ok) {
    document.getElementById("callHint").textContent = data.detail || "TTS failed";
    return;
  }
  callLine("assistant", data.text);
  playB64(data.audio_b64);
  document.getElementById("callHint").textContent = "Hold to talk when she finishes.";
}

function closeCall() {
  currentCall = null;
  document.getElementById("callBooth").classList.add("hidden");
}

const talkBtn = document.getElementById("talkBtn");
talkBtn.onmousedown = startTalk;
talkBtn.ontouchstart = (e) => {
  e.preventDefault();
  startTalk();
};
talkBtn.onmouseup = stopTalk;
talkBtn.ontouchend = stopTalk;

function encodeWav(chunks, sampleRate) {
  let total = 0;
  chunks.forEach((c) => {
    total += c.length;
  });
  const pcm = new Float32Array(total);
  let offset = 0;
  chunks.forEach((c) => {
    pcm.set(c, offset);
    offset += c.length;
  });
  const buffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buffer);
  const ascii = (at, s) => {
    for (let i = 0; i < s.length; i += 1) view.setUint8(at + i, s.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + pcm.length * 2, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  ascii(36, "data");
  view.setUint32(40, pcm.length * 2, true);
  let p = 44;
  for (let i = 0; i < pcm.length; i += 1, p += 2) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    view.setInt16(p, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function startTalk() {
  if (!currentCall || wavProc) return;
  wavStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  wavCtx = new AudioContext({ sampleRate: 16000 });
  const src = wavCtx.createMediaStreamSource(wavStream);
  wavProc = wavCtx.createScriptProcessor(4096, 1, 1);
  wavChunks = [];
  wavProc.onaudioprocess = (e) => {
    wavChunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  };
  if (wavCtx.state === "suspended") await wavCtx.resume();
  src.connect(wavProc);
  const mute = wavCtx.createGain();
  mute.gain.value = 0;
  wavProc.connect(mute);
  mute.connect(wavCtx.destination);
  talkBtn.classList.add("hot");
  document.getElementById("callHint").textContent = "Listening… release to send.";
}

async function stopTalk() {
  if (!wavProc) return;
  wavProc.disconnect();
  wavProc = null;
  const rate = wavCtx ? wavCtx.sampleRate : 16000;
  if (wavStream) wavStream.getTracks().forEach((t) => t.stop());
  if (wavCtx) await wavCtx.close();
  wavCtx = null;
  wavStream = null;
  talkBtn.classList.remove("hot");
  if (!wavChunks.length) {
    document.getElementById("callHint").textContent = "Hold a bit longer, then release.";
    return;
  }
  const blob = encodeWav(wavChunks, rate);
  const fd = new FormData();
  fd.append("audio", blob, "turn.wav");
  document.getElementById("callHint").textContent = "Gnani STT…";
  const res = await fetch(`/api/call/${currentCall}/hear`, { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) {
    document.getElementById("callHint").textContent = data.detail || "turn failed";
    return;
  }
  callLine("user", data.transcript);
  callLine("assistant", data.reply);
  playB64(data.audio_b64);
  document.getElementById("callHint").textContent = data.done
    ? `Disposition ${data.disposition} — hang up when ready.`
    : "Hold to talk again, or hang up.";
}

document.getElementById("hangupBtn").onclick = async () => {
  if (!currentCall) return;
  await fetch(`/api/call/${currentCall}/hangup`, { method: "POST" });
};

function openCurtain(payload) {
  currentCurtain = payload.id;
  currentSample = payload.sample || null;
  curtainWho.textContent = `${payload.partner}  ${payload.method}  ${payload.endpoint}`;
  curtainReq.textContent = pretty(payload.request);
  curtainText.value = "";
  curtainEl.classList.remove("hidden");
}

function closeCurtain() {
  currentCurtain = null;
  curtainEl.classList.add("hidden");
}

document.getElementById("useSample").onclick = () => {
  if (currentSample) curtainText.value = pretty(currentSample);
};

document.getElementById("submitCurtain").onclick = async () => {
  if (!currentCurtain) return;
  let response;
  try {
    response = JSON.parse(curtainText.value);
  } catch {
    alert("Response must be valid JSON — no extra instructions.");
    return;
  }
  if (typeof response !== "object" || Array.isArray(response) || !response) {
    alert("Paste a JSON object only.");
    return;
  }
  await fetch(`/api/curtain/${currentCurtain}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ response }),
  });
};

document.getElementById("resetBtn").onclick = () => fetch("/api/reset", { method: "POST" });

document.querySelectorAll(".clock-row button").forEach((btn) => {
  btn.onclick = () =>
    fetch("/api/clock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutes: Number(btn.dataset.min) }),
    });
});

document.querySelectorAll(".composer").forEach((form) => {
  form.onsubmit = async (e) => {
    e.preventDefault();
    const text = form.text.value.trim();
    if (!text) return;
    form.text.value = "";
    await fetch("/api/stage/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from: form.dataset.alias, text }),
    });
  };
});

async function boot() {
  const setup = await fetch("/api/setup").then((r) => r.json());
  document.getElementById("clockChip").textContent = setup.clock;
  const missing = Object.entries(setup.keys)
    .filter(([, ok]) => !ok)
    .map(([k]) => k);
  document.getElementById("keysChip").textContent = missing.length
    ? `missing: ${missing.join(", ")}`
    : "all recording keys present";

  const sc = await fetch("/api/scenarios").then((r) => r.json());
  const box = document.getElementById("scenarioBtns");
  sc.scenarios.forEach((s) => {
    const b = document.createElement("button");
    b.textContent = s.label;
    b.onclick = () => fetch(`/api/inject/${s.id}`, { method: "POST" });
    box.appendChild(b);
  });

  const src = new EventSource("/api/events");
  src.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data));
    } catch (err) {
      console.error(err);
    }
  };
}

boot();
