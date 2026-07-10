const documentsTable = document.querySelector("#documents-table");
const documentStats = document.querySelector("#document-stats");

const statusClass = {
  pending: "badge-warning",
  processing: "badge-info",
  completed: "badge-success",
  processed: "badge-success",
  failed: "badge-error",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function badge(status) {
  return `<span class="badge ${statusClass[status] || "badge-ghost"}">${escapeHtml(status)}</span>`;
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

async function requestJson(url) {
  const response = await fetch(url);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || `Request failed with ${response.status}`);
  }

  return payload;
}

function renderStats(documents) {
  const total = documents.length;
  const ready = documents.filter((document) => ["processed", "completed"].includes(document.status)).length;
  const chunks = documents.reduce((sum, document) => sum + Number(document.chunks_count || 0), 0);

  documentStats.innerHTML = `
    <div class="stat">
      <div class="stat-title">Documents</div>
      <div class="stat-value">${total}</div>
    </div>
    <div class="stat">
      <div class="stat-title">Ready</div>
      <div class="stat-value text-success">${ready}</div>
    </div>
    <div class="stat">
      <div class="stat-title">Chunks</div>
      <div class="stat-value text-primary">${chunks}</div>
    </div>
  `;
}

async function loadDocumentsPage() {
  documentsTable.innerHTML = `<tr><td colspan="6"><div class="skeleton h-10 w-full"></div></td></tr>`;

  try {
    const documents = await requestJson("/documents");
    renderStats(documents);

    if (!documents.length) {
      documentsTable.innerHTML = `<tr><td colspan="6" class="text-slate-500">No documents yet.</td></tr>`;
      return;
    }

    documentsTable.innerHTML = documents.map((document) => `
      <tr>
        <th>${document.id}</th>
        <td class="mono-wrap font-medium">${escapeHtml(document.title)}</td>
        <td>${escapeHtml(document.source_type)}</td>
        <td>${badge(document.status)}</td>
        <td>${document.chunks_count}</td>
        <td>${formatDate(document.created_at)}</td>
      </tr>
    `).join("");
  } catch (error) {
    documentsTable.innerHTML = `<tr><td colspan="6"><div class="alert alert-error"><span>${escapeHtml(error.message)}</span></div></td></tr>`;
  }
}

document.querySelector("#refresh-documents-page").addEventListener("click", loadDocumentsPage);
loadDocumentsPage();
