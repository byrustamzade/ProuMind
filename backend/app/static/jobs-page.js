const jobsTable = document.querySelector("#jobs-table");
const jobStats = document.querySelector("#job-stats");

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

function renderStats(jobs) {
  const total = jobs.length;
  const completed = jobs.filter((job) => job.status === "completed").length;
  const failed = jobs.filter((job) => job.status === "failed").length;

  jobStats.innerHTML = `
    <div class="stat">
      <div class="stat-title">Jobs</div>
      <div class="stat-value">${total}</div>
    </div>
    <div class="stat">
      <div class="stat-title">Completed</div>
      <div class="stat-value text-success">${completed}</div>
    </div>
    <div class="stat">
      <div class="stat-title">Failed</div>
      <div class="stat-value text-error">${failed}</div>
    </div>
  `;
}

async function loadJobsPage() {
  jobsTable.innerHTML = `<tr><td colspan="7"><div class="skeleton h-10 w-full"></div></td></tr>`;

  try {
    const jobs = await requestJson("/documents/ingestion-jobs");
    renderStats(jobs);

    if (!jobs.length) {
      jobsTable.innerHTML = `<tr><td colspan="7" class="text-slate-500">No jobs yet.</td></tr>`;
      return;
    }

    jobsTable.innerHTML = jobs.map((job) => `
      <tr>
        <th>${job.id}</th>
        <td>${job.document_id ?? ""}</td>
        <td>${badge(job.status)}</td>
        <td>${formatDate(job.started_at)}</td>
        <td>${formatDate(job.finished_at)}</td>
        <td>${formatDate(job.created_at)}</td>
        <td class="mono-wrap max-w-md text-xs text-error">${escapeHtml(job.error_message || "")}</td>
      </tr>
    `).join("");
  } catch (error) {
    jobsTable.innerHTML = `<tr><td colspan="7"><div class="alert alert-error"><span>${escapeHtml(error.message)}</span></div></td></tr>`;
  }
}

document.querySelector("#refresh-jobs-page").addEventListener("click", loadJobsPage);
loadJobsPage();
