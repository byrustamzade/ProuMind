const uploadStatus = document.querySelector("#upload-status");
const uploadForm = document.querySelector("#upload-form");
const urlForm = document.querySelector("#url-form");
const askForm = document.querySelector("#ask-form");
const chatLog = document.querySelector("#chat-log");
const toastHost = document.querySelector("#toast-host");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setLoading(button, loading) {
  const spinner = button.querySelector(".loading");
  const label = button.querySelector("span:not(.loading)");
  button.disabled = loading;
  spinner?.classList.toggle("hidden", !loading);
  label?.classList.toggle("hidden", loading);
}

function showToast(message, type = "info") {
  const alert = document.createElement("div");
  alert.className = `alert alert-${type} shadow-lg`;
  alert.innerHTML = `<span>${escapeHtml(message)}</span>`;
  toastHost.appendChild(alert);
  setTimeout(() => alert.remove(), 4200);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail : payload;
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return payload;
}

function appendMessage(role, html) {
  const isUser = role === "user";
  const sentAt = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
  const wrapper = document.createElement("div");
  wrapper.className = `chat ${isUser ? "chat-end" : "chat-start"}`;
  wrapper.innerHTML = `
    <div class="chat-image avatar placeholder">
      <div class="w-10 rounded-full ${isUser ? "bg-neutral text-neutral-content" : "bg-primary text-primary-content"}">
        <span>${isUser ? "Y" : "P"}</span>
      </div>
    </div>
    <div class="chat-header">
      <span class="font-semibold">${isUser ? "You" : "ProuMind"}</span>
      <time class="text-xs opacity-50">${sentAt}</time>
    </div>
    <div class="chat-bubble max-w-4xl ${isUser ? "chat-bubble-primary" : "chat-bubble-secondary"}">${html}</div>
    <div class="chat-footer opacity-50">${isUser ? "Sent" : "Answered"}</div>
  `;
  chatLog.appendChild(wrapper);
  chatLog.scrollTop = chatLog.scrollHeight;
  return wrapper;
}

function renderAnswer(payload) {
  const sources = payload.sources || [];
  const sourceHtml = sources.length
    ? `
      <div class="mt-4 grid gap-2">
        ${sources.map((source) => `
          <div class="source-card">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <strong class="mono-wrap text-sm">${escapeHtml(source.document_title)}</strong>
              <span class="badge badge-outline">chunk ${source.chunk_id}</span>
            </div>
            <p class="mt-2 text-sm text-slate-600">${escapeHtml(source.text_preview)}</p>
          </div>
        `).join("")}
      </div>
    `
    : "";

  return `
    <div class="whitespace-pre-wrap">${escapeHtml(payload.answer)}</div>
    ${sourceHtml}
  `;
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const input = document.querySelector("#pdf-input");
  const button = uploadForm.querySelector("button");

  if (!input.files.length) {
    showToast("Choose a PDF first.", "warning");
    return;
  }

  const formData = new FormData();
  formData.append("file", input.files[0]);

  setLoading(button, true);
  uploadStatus.textContent = "Uploading";

  try {
    const document = await requestJson("/documents/upload", {
      method: "POST",
      body: formData,
    });

    uploadStatus.textContent = "Queued";
    input.value = "";
    showToast(`Queued ${document.title}`, "success");
    showToast("Open Documents or Jobs to follow processing.", "info");
  } catch (error) {
    uploadStatus.textContent = "Failed";
    showToast(error.message, "error");
  } finally {
    setLoading(button, false);
  }
});

urlForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const input = document.querySelector("#url-input");
  const url = input.value.trim();
  const button = urlForm.querySelector("button");

  if (!url) {
    showToast("Enter a URL first.", "warning");
    return;
  }

  setLoading(button, true);

  try {
    const document = await requestJson("/documents/url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    input.value = "";
    showToast(`Queued ${document.title}`, "success");
    showToast("Open Documents or Jobs to follow processing.", "info");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setLoading(button, false);
  }
});

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const input = document.querySelector("#question-input");
  const button = document.querySelector("#ask-button");
  const question = input.value.trim();

  if (!question) {
    showToast("Write a question first.", "warning");
    return;
  }

  appendMessage("user", escapeHtml(question));
  input.value = "";
  setLoading(button, true);

  const loadingBubble = appendMessage("assistant", `<span class="loading loading-dots loading-md"></span>`);

  try {
    const payload = await requestJson("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        size: Number(document.querySelector("#result-size").value),
        debug: document.querySelector("#debug-toggle").checked,
      }),
    });

    loadingBubble.querySelector(".chat-bubble").innerHTML = renderAnswer(payload);
  } catch (error) {
    loadingBubble.querySelector(".chat-bubble").innerHTML = `<span class="text-error">${escapeHtml(error.message)}</span>`;
  } finally {
    setLoading(button, false);
  }
});

document.querySelector("#question-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    askForm.requestSubmit();
  }
});
