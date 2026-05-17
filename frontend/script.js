const API_BASE = "http://127.0.0.1:8000";
const HISTORY_KEY = "texto_inteligente_history";

const state = {
  tab: "file",
  file: null,
  recordingBlob: null,
  lastResult: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const errorEl = $("#error");
const progressSection = $("#progress-section");
const progressLabel = $("#progress-label");
const progressPct = $("#progress-pct");
const progressBar = $("#progress-bar");
const results = $("#results");
const historySection = $("#history");
const historyList = $("#history-list");

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.classList.remove("hidden");
}

function hideError() {
  errorEl.classList.add("hidden");
  errorEl.textContent = "";
}

let progressTimer = null;

function startProgress(stages) {
  progressSection.classList.remove("hidden");
  let i = 0;
  const tick = () => {
    const s = stages[Math.min(i, stages.length - 1)];
    progressLabel.textContent = s.label;
    progressPct.textContent = `${s.pct}%`;
    progressBar.style.width = `${s.pct}%`;
    if (i < stages.length - 1) i += 1;
  };
  tick();
  progressTimer = setInterval(tick, 2200);
}

function stopProgress() {
  if (progressTimer) clearInterval(progressTimer);
  progressTimer = null;
  progressSection.classList.add("hidden");
  progressBar.style.width = "0%";
}

async function parseJsonError(res) {
  const data = await res.json().catch(() => ({}));
  const detail = data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || d).join(" ");
  return "Não foi possível concluir. Tente novamente ou envie o arquivo manualmente.";
}

function setTab(name) {
  state.tab = name;
  $$(".tab").forEach((t) => {
    const on = t.dataset.tab === name;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  $$(".panel").forEach((p) => {
    const on = p.id === `panel-${name}`;
    p.classList.toggle("active", on);
    p.hidden = !on;
  });
}

$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => setTab(btn.dataset.tab));
});

const dropzone = $("#dropzone");
const fileInput = $("#file-input");

dropzone.addEventListener("click", () => fileInput.click());
["dragenter", "dragover"].forEach((ev) => {
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("dropzone-active");
  });
});
["dragleave", "drop"].forEach((ev) => {
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dropzone-active");
  });
});
dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer?.files?.[0];
  if (f) {
    state.file = f;
    dropzone.querySelector("p").textContent = f.name;
  }
});
fileInput.addEventListener("change", () => {
  const f = fileInput.files?.[0];
  if (f) {
    state.file = f;
    dropzone.querySelector("p").textContent = f.name;
  }
});

let mediaRecorder = null;
let recordChunks = [];
let recordStart = 0;
let recordInterval = null;

const recordBtn = $("#record-btn");
const recordTimer = $("#record-timer");
const recordStatus = $("#record-status");

recordBtn.addEventListener("click", async () => {
  if (mediaRecorder?.state === "recording") {
    mediaRecorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size) recordChunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      state.recordingBlob = new Blob(recordChunks, { type: "audio/webm" });
      recordStatus.textContent = "Gravação pronta. Toque em Transcrever.";
      recordBtn.textContent = "● Gravar de novo";
      clearInterval(recordInterval);
    };
    mediaRecorder.start();
    recordStart = Date.now();
    recordBtn.textContent = "■ Parar";
    recordStatus.textContent = "Gravando…";
    recordInterval = setInterval(() => {
      const s = Math.floor((Date.now() - recordStart) / 1000);
      const m = String(Math.floor(s / 60)).padStart(2, "0");
      const sec = String(s % 60).padStart(2, "0");
      recordTimer.textContent = `${m}:${sec}`;
    }, 500);
  } catch {
    showError("Não foi possível acessar o microfone. Verifique as permissões do navegador.");
  }
});

function renderResult(data) {
  state.lastResult = data;
  $("#texto").value = data.texto || "";
  $("#resumo-text").textContent = data.resumo || "";
  const ul = $("#topicos-list");
  ul.innerHTML = "";
  (data.topicos || []).forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    ul.appendChild(li);
  });
  const kw = $("#keywords");
  kw.innerHTML = "";
  (data.palavras_chave || []).forEach((w) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = w;
    kw.appendChild(span);
  });
  $("#estudo-text").textContent = data.estudo || "";
  results.classList.remove("hidden");
  showResultTab("texto");
  saveHistory(data);
}

function showResultTab(name) {
  $$(".rtab").forEach((b) => b.classList.toggle("active", b.dataset.rtab === name));
  $("#view-texto").classList.toggle("hidden", name !== "texto");
  $("#view-resumo").classList.toggle("hidden", name !== "resumo");
  $("#view-estudo").classList.toggle("hidden", name !== "estudo");
}

$$(".rtab").forEach((b) => b.addEventListener("click", () => showResultTab(b.dataset.rtab)));

function saveHistory(data) {
  const items = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
  const title = (data.resumo || data.texto || "").slice(0, 60).trim() || "Transcrição";
  items.unshift({ title, at: new Date().toISOString(), data });
  sessionStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 8)));
  renderHistory();
}

function renderHistory() {
  const items = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
  if (!items.length) {
    historySection.classList.add("hidden");
    return;
  }
  historySection.classList.remove("hidden");
  historyList.innerHTML = "";
  items.forEach((item, idx) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = item.title;
    btn.addEventListener("click", () => renderResult(item.data));
    const del = document.createElement("button");
    del.type = "button";
    del.className = "history-del";
    del.textContent = "×";
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      items.splice(idx, 1);
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(items));
      renderHistory();
    });
    li.append(btn, del);
    historyList.appendChild(li);
  });
}

async function transcribeFile(file) {
  const form = new FormData();
  form.append("file", file, file.name || "gravacao.webm");
  const res = await fetch(`${API_BASE}/transcribe/file`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseJsonError(res));
  return res.json();
}

async function transcribeUrl(url) {
  const res = await fetch(`${API_BASE}/transcribe/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(await parseJsonError(res));
  return res.json();
}

$("#btn-transcribe").addEventListener("click", async () => {
  hideError();
  results.classList.add("hidden");

  const stages = [
    { label: "Enviando conteúdo…", pct: 12 },
    { label: "Extraindo áudio…", pct: 35 },
    { label: "Transcrevendo com IA…", pct: 62 },
    { label: "Organizando texto e resumo…", pct: 88 },
    { label: "Quase pronto…", pct: 96 },
  ];
  startProgress(stages);
  $("#btn-transcribe").disabled = true;

  try {
    let data;
    if (state.tab === "file") {
      if (!state.file) {
        throw new Error("Escolha um arquivo ou arraste-o na área indicada.");
      }
      data = await transcribeFile(state.file);
    } else if (state.tab === "link") {
      const url = $("#media-url").value.trim();
      if (!url) throw new Error("Cole o link do vídeo ou áudio público.");
      data = await transcribeUrl(url);
    } else {
      if (!state.recordingBlob) {
        throw new Error("Grave um áudio antes de transcrever.");
      }
      const file = new File([state.recordingBlob], "gravacao.webm", { type: "audio/webm" });
      data = await transcribeFile(file);
    }
    progressBar.style.width = "100%";
    progressPct.textContent = "100%";
    progressLabel.textContent = "Concluído!";
    renderResult(data);
  } catch (e) {
    showError(e.message || "Falha na conexão com o servidor.");
  } finally {
    stopProgress();
    $("#btn-transcribe").disabled = false;
  }
});

async function exportFormat(fmt) {
  const d = state.lastResult;
  if (!d) return;
  if (fmt === "copy") {
    const block = `TRANSCRIÇÃO\n\n${d.texto}\n\nRESUMO\n\n${d.resumo}\n\n${d.estudo}`;
    try {
      await navigator.clipboard.writeText(block);
    } catch {
      showError("Não foi possível copiar. Selecione o texto manualmente.");
    }
    return;
  }
  const res = await fetch(`${API_BASE}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      formato: fmt,
      texto: d.texto,
      resumo: d.resumo,
      estudo: d.estudo,
      titulo: "Transcrição inteligente",
    }),
  });
  if (!res.ok) throw new Error(await parseJsonError(res));
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `conteudo.${fmt}`;
  a.click();
  URL.revokeObjectURL(a.href);
}

$$(".btn-export").forEach((btn) => {
  btn.addEventListener("click", async () => {
    try {
      await exportFormat(btn.dataset.export);
    } catch (e) {
      showError(e.message);
    }
  });
});

async function runDownload(action) {
  const url = $("#download-url").value.trim();
  if (!url) {
    showError("Cole o link do YouTube na seção de downloads.");
    return;
  }
  hideError();
  startProgress([
    { label: "Preparando download…", pct: 20 },
    { label: "Baixando do YouTube…", pct: 55 },
    { label: "Finalizando arquivo…", pct: 85 },
  ]);
  try {
    const res = await fetch(`${API_BASE}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, action }),
    });
    if (!res.ok) throw new Error(await parseJsonError(res));
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition");
    let name = action === "video" ? "video.mp4" : "audio.mp3";
    const m = /filename="([^"]+)"/i.exec(cd || "");
    if (m) name = m[1];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    showError(e.message);
  } finally {
    stopProgress();
  }
}

$("#dl-video").addEventListener("click", () => runDownload("video"));
$("#dl-audio").addEventListener("click", () => runDownload("audio"));

renderHistory();
