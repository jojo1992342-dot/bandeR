const api = {
  async get(path) {
    const res = await fetch(`/api${path}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  async post(path, body) {
    const res = await fetch(`/api${path}`, {
      method: "POST",
      headers: body instanceof FormData ? undefined : { "Content-Type": "application/json" },
      body: body instanceof FormData ? body : JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  async patch(path, body) {
    const res = await fetch(`/api${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};

const state = {
  projects: [],
  project: null,
  media: [],
  transcript: { segments: [] },
  rythmo: { items: [], settings: {} },
  selectedWord: null,
  jobId: null,
  zoom: 180,
};

const els = {
  projectList: document.querySelector("#projectList"),
  refreshBtn: document.querySelector("#refreshBtn"),
  newProjectBtn: document.querySelector("#newProjectBtn"),
  projectDialog: document.querySelector("#projectDialog"),
  projectForm: document.querySelector("#projectForm"),
  projectName: document.querySelector("#projectName"),
  projectLanguage: document.querySelector("#projectLanguage"),
  uploadForm: document.querySelector("#uploadForm"),
  videoInput: document.querySelector("#videoInput"),
  autorunInput: document.querySelector("#autorunInput"),
  video: document.querySelector("#videoPlayer"),
  runPipelineBtn: document.querySelector("#runPipelineBtn"),
  exportBtn: document.querySelector("#exportBtn"),
  restartServerBtn: document.querySelector("#restartServerBtn"),
  exportFormat: document.querySelector("#exportFormat"),
  jobStatus: document.querySelector("#jobStatus"),
  jobProgress: document.querySelector("#jobProgress"),
  canvas: document.querySelector("#rythmoCanvas"),
  transcriptList: document.querySelector("#transcriptList"),
  segmentCount: document.querySelector("#segmentCount"),
  wordText: document.querySelector("#wordText"),
  wordStart: document.querySelector("#wordStart"),
  wordEnd: document.querySelector("#wordEnd"),
  saveWordBtn: document.querySelector("#saveWordBtn"),
  playBtn: document.querySelector("#playBtn"),
  backBtn: document.querySelector("#backBtn"),
  forwardBtn: document.querySelector("#forwardBtn"),
  timecode: document.querySelector("#timecode"),
  zoomInput: document.querySelector("#zoomInput"),
};

const ctx = els.canvas.getContext("2d");

function formatTime(value) {
  const total = Math.max(0, Number(value) || 0);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  const ms = Math.floor((total - Math.floor(total)) * 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

async function refreshProjects() {
  state.projects = await api.get("/projects");
  renderProjects();
  if (!state.project && state.projects.length) {
    await selectProject(state.projects[0].id);
  }
}

function renderProjects() {
  els.projectList.innerHTML = "";
  for (const project of state.projects) {
    const item = document.createElement("div");
    item.className = `project-item ${state.project?.id === project.id ? "active" : ""}`;
    item.innerHTML = `<strong>${project.name}</strong><span>${project.status} - ${project.language}</span>`;
    item.addEventListener("click", () => selectProject(project.id));
    els.projectList.append(item);
  }
}

async function selectProject(projectId) {
  state.project = await api.get(`/projects/${projectId}`);
  state.media = state.project.media || [];
  const source = state.media.find((m) => m.kind === "source");
  els.video.src = source ? `/api/media/${source.id}/file` : "";
  await loadTranscriptAndRythmo();
  renderProjects();
}

async function loadTranscriptAndRythmo() {
  if (!state.project) return;
  state.transcript = await api.get(`/projects/${state.project.id}/transcript`);
  state.rythmo = await api.get(`/projects/${state.project.id}/rythmo`);
  state.rythmo.settings.pixels_per_second = state.zoom;
  renderTranscript();
  drawRythmo();
}

function renderTranscript() {
  const segments = state.transcript.segments || [];
  els.segmentCount.textContent = `${segments.length} segment${segments.length > 1 ? "s" : ""}`;
  els.transcriptList.innerHTML = "";
  for (const segment of segments) {
    const row = document.createElement("div");
    row.className = "segment";
    const words = (segment.words || [])
      .map((word) => `<span class="word ${state.selectedWord?.id === word.id ? "active" : ""}" data-word="${word.id}">${word.text}</span>`)
      .join("");
    row.innerHTML = `<div class="segment-time">${formatTime(segment.start_time)}<br>${formatTime(segment.end_time)}</div><div>${words}</div>`;
    row.querySelectorAll(".word").forEach((node) => {
      node.addEventListener("click", () => selectWord(node.dataset.word));
    });
    els.transcriptList.append(row);
  }
}

function selectWord(wordId) {
  for (const segment of state.transcript.segments || []) {
    const word = (segment.words || []).find((item) => item.id === wordId);
    if (word) {
      state.selectedWord = word;
      els.wordText.value = word.text;
      els.wordStart.value = word.start_time;
      els.wordEnd.value = word.end_time;
      els.video.currentTime = word.start_time;
      renderTranscript();
      drawRythmo();
      return;
    }
  }
}

async function saveSelectedWord() {
  if (!state.project || !state.selectedWord) return;
  await api.patch(`/projects/${state.project.id}/words/${state.selectedWord.id}`, {
    text: els.wordText.value,
    start_time: Number(els.wordStart.value),
    end_time: Number(els.wordEnd.value),
  });
  await loadTranscriptAndRythmo();
}

function drawRythmo() {
  const canvas = els.canvas;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const width = rect.width;
  const height = rect.height;
  const now = els.video.currentTime || 0;
  const pps = state.zoom;
  const originX = width * 0.34;
  const viewportStart = now - originX / pps;

  ctx.fillStyle = "#0b0e12";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "#252d37";
  ctx.lineWidth = 1;
  for (let i = 0; i < 8; i += 1) {
    const x = originX + (Math.ceil(viewportStart) + i - now) * pps;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }

  ctx.fillStyle = "rgba(217,164,65,0.18)";
  ctx.fillRect(originX - 2, 0, 4, height);
  ctx.fillStyle = "#d9a441";
  ctx.fillRect(originX - 1, 0, 2, height);

  ctx.font = "600 24px Inter, sans-serif";
  ctx.textBaseline = "middle";
  const items = state.rythmo.items || [];
  for (const item of items) {
    const x = originX + (item.start_time - now) * pps;
    const w = Math.max(34, (item.end_time - item.start_time) * pps);
    const y = item.y || 96;
    if (x + w < -80 || x > width + 80) continue;
    const selected = state.selectedWord?.id === item.id;
    const playing = now >= item.start_time && now <= item.end_time;
    const active = selected || playing;
    ctx.fillStyle = playing ? "#d9a441" : selected ? "#4fb38a" : item.color || "#2f80ed";
    roundRect(ctx, x, y - 22, w, 38, 7);
    ctx.fill();
    ctx.fillStyle = active ? "#06120d" : "#f1f4f8";
    ctx.fillText(item.text, x + 9, y - 3, Math.max(20, w - 18));
  }

  els.timecode.textContent = formatTime(now);
  requestAnimationFrame(drawRythmo);
}

function roundRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}

async function pollJob(jobId) {
  state.jobId = jobId;
  const timer = setInterval(async () => {
    const job = await api.get(`/jobs/${jobId}`);
    els.jobStatus.textContent = `${job.stage} - ${job.message || job.status}`;
    els.jobProgress.style.width = `${Math.round((job.progress || 0) * 100)}%`;
    if (job.status === "completed" || job.status === "failed") {
      clearInterval(timer);
      await refreshProjects();
      if (state.project) await selectProject(state.project.id);
      if (job.status === "failed") alert(job.error || "Job echoue");
      if (job.result?.export_id) {
        window.location.href = `/api/exports/${job.result.export_id}/download`;
      }
    }
  }, 900);
}

els.refreshBtn.addEventListener("click", refreshProjects);
els.newProjectBtn.addEventListener("click", () => els.projectDialog.showModal());
els.projectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const project = await api.post("/projects", {
    name: els.projectName.value,
    language: els.projectLanguage.value || "fr",
  });
  els.projectDialog.close();
  await refreshProjects();
  await selectProject(project.id);
});

els.uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.project) {
    alert("Creez ou selectionnez un projet.");
    return;
  }
  if (!els.videoInput.files.length) {
    alert("Selectionnez une video.");
    return;
  }
  const form = new FormData();
  form.append("file", els.videoInput.files[0]);
  form.append("autorun", els.autorunInput.checked ? "true" : "false");
  const response = await api.post(`/projects/${state.project.id}/media`, form);
  await selectProject(state.project.id);
  if (response.job) pollJob(response.job.id);
});

els.runPipelineBtn.addEventListener("click", async () => {
  if (!state.project) return;
  const job = await api.post(`/projects/${state.project.id}/jobs/pipeline`);
  pollJob(job.id);
});

els.exportBtn.addEventListener("click", async () => {
  if (!state.project) return;
  const job = await api.post(`/projects/${state.project.id}/exports`, {
    format: els.exportFormat.value,
    options: { layout: { pixels_per_second: state.zoom } },
  });
  pollJob(job.id);
});

els.saveWordBtn.addEventListener("click", saveSelectedWord);
els.playBtn.addEventListener("click", () => (els.video.paused ? els.video.play() : els.video.pause()));
els.backBtn.addEventListener("click", () => (els.video.currentTime = Math.max(0, els.video.currentTime - 1)));
els.forwardBtn.addEventListener("click", () => (els.video.currentTime += 1));
els.zoomInput.addEventListener("input", () => {
  state.zoom = Number(els.zoomInput.value);
});

els.canvas.addEventListener("click", (event) => {
  const rect = els.canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const now = els.video.currentTime || 0;
  const originX = rect.width * 0.34;
  for (const item of state.rythmo.items || []) {
    const drawX = originX + (item.start_time - now) * state.zoom;
    const drawW = Math.max(34, (item.end_time - item.start_time) * state.zoom);
    const drawY = item.y || 96;
    if (x >= drawX && x <= drawX + drawW && y >= drawY - 22 && y <= drawY + 16) {
      selectWord(item.id);
      break;
    }
  }
});

refreshProjects().catch((error) => {
  console.error(error);
  els.jobStatus.textContent = "Erreur de chargement API";
});
drawRythmo();





if (els.restartServerBtn) {
  els.restartServerBtn.addEventListener("click", async () => {
    const confirmed = confirm("Redemarrer completement le serveur local ? La page se reconnectera automatiquement.");
    if (!confirmed) return;
    els.jobStatus.textContent = "Redemarrage du serveur...";
    els.jobProgress.style.width = "100%";
    try {
      await api.post("/system/restart", {});
    } catch (error) {
      console.warn(error);
    }
    setTimeout(() => {
      window.location.reload();
    }, 2500);
  });
}


