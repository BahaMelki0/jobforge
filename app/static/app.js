const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s = "") =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const posted = (s) => {
  if (!s) return "Posting date unknown";
  const d = new Date(s.endsWith("Z") || /[+-]\d\d:\d\d$/.test(s) ? s : s + "Z");
  const days = Math.max(0, Math.floor((Date.now() - d.getTime()) / 86400000));
  return (
    "Posted " +
    d.toLocaleDateString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
    }) +
    " (" +
    (days === 0 ? "today" : days + " days ago") +
    ")"
  );
};
const safeUrl = (s) => (/^https?:\/\//i.test(s || "") ? s : "#");
const date = (s) =>
  s
    ? new Date(
        s.endsWith("Z") || /[+-]\d\d:\d\d$/.test(s) ? s : s + "Z",
      ).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Not yet";
async function api(url, opts = {}) {
  const r = await fetch(url, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  const body = await r.json();
  if (!r.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail || body),
    );
  return body;
}
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").style.display = "block";
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(
    () => ($("#toast").style.display = "none"),
    7000,
  );
}
window.addEventListener("unhandledrejection", (e) => {
  toast(e.reason?.message || "Request failed");
  e.preventDefault();
});
let currentPage = 1;
let allJobs = [],
  sources = [],
  scanState = {},
  activeJob = null,
  draft = null,
  busyDraft = false,
  editingSourceId = null;
function tab(name) {
  $$(".tab").forEach((e) =>
    e.classList.toggle("active", e.dataset.tab === name),
  );
  $$(".panel").forEach((e) =>
    e.classList.toggle("active", e.id === "tab-" + name),
  );
  $("#page-name").textContent = {
    jobs: "Discover jobs",
    sources: "Live sources",
    profile: "My profile",
    applications: "Applications",
    ai: "Local AI workspace",
  }[name];
  if (name === "ai") {
    health();
    refreshTasks();
  }
  if (name === "sources") loadSources();
  if (name === "profile") loadProfile();
  if (name === "applications") loadApps();
}
$$(".tab").forEach((e) => (e.onclick = () => tab(e.dataset.tab)));
$$("dialog .close").forEach(
  (e) => (e.onclick = () => e.closest("dialog").close()),
);
async function loadJobs() {
  const status = $("#job-application-status")?.value || "";
  allJobs = await api(
    `/api/jobs?limit=1000${status ? "&application_status=" + encodeURIComponent(status) : ""}`,
  );
  renderJobs();
}
function options(id, values, label) {
  const el = $(id),
    old = el.value;
  el.innerHTML =
    `<option value="">${label}</option>` +
    values
      .map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`)
      .join("");
  el.value = old;
}
function renderJobs() {
  const q = $("#job-search").value.toLowerCase(),
    cat = $("#job-category").value,
    src = $("#job-source").value,
    min = Number($("#min-score").value);
  options(
    "#job-category",
    [...new Set(allJobs.map((j) => j.score?.category).filter(Boolean))]
      .sort()
      .map((c) => [c, c]),
    "All specialties",
  );
  options(
    "#job-source",
    sources
      .filter((s) => allJobs.some((j) => j.source_id === s.id))
      .map((s) => [s.id, s.name]),
    "All sources",
  );
  const jobs = allJobs.filter(
    (j) =>
      (!q ||
        `${j.title} ${j.company} ${j.location} ${j.description}`
          .toLowerCase()
          .includes(q)) &&
      (!cat || j.score?.category === cat) &&
      (!src || j.source_id === Number(src)) &&
      (j.score?.total || 0) >= min &&
      (!$("#job-focus").value || j.focus?.status === $("#job-focus").value) &&
      (!$("#job-readiness").value ||
        j.detail_status === $("#job-readiness").value),
  );
  jobs.sort((a, b) =>
    $("#job-sort").value === "newest"
      ? (Date.parse(b.published_at || "") || 0) -
        (Date.parse(a.published_at || "") || 0)
      : (b.score?.total || 0) - (a.score?.total || 0),
  );
  const pages = Math.max(1, Math.ceil(jobs.length / 24));
  currentPage = Math.min(currentPage, pages);
  $("#pagination").innerHTML =
    `<button class=secondary onclick=changePage(-1) ${currentPage === 1 ? "disabled" : ""}>Previous</button><span>Page ${currentPage} of ${pages} &middot; ${jobs.length} results</span><button class=secondary onclick=changePage(1) ${currentPage === pages ? "disabled" : ""}>Next</button>`;
  const latest = scanState.runs?.[0],
    newCount = (latest?.results || []).reduce(
      (n, r) => n + (r.created || 0),
      0,
    );
  $("#job-stats").innerHTML = [
    [
      "FRANCE / JUNIOR",
      allJobs.filter((j) => j.focus?.status === "junior_france").length,
      "Confirmed location and junior evidence",
    ],
    [
      "STRONG MATCHES",
      allJobs.filter((j) => (j.score?.total || 0) >= 75).length,
      "Scored 75 or above",
    ],
    ["NEW THIS SCAN", newCount, "Duplicates merged automatically"],
    [
      "CONNECTED SOURCES",
      sources.filter((s) => s.enabled && s.kind !== "demo").length,
      "Public feeds & career boards",
    ],
    [
      "NEEDS CHECK",
      allJobs.filter((j) => j.application_status === "unknown").length,
      "No reliable open/closed signal",
    ],
  ]
    .map(
      ([l, v, n], i) =>
        `<div class="stat"><div class="stat-label">${l}</div><div class="stat-value ${i === 1 ? "green" : ""}">${v}</div><div class="stat-note">${n}</div></div>`,
    )
    .join("");
  $("#result-count").textContent = jobs.length;
  $("#jobs").innerHTML =
    jobs
      .slice((currentPage - 1) * 24, currentPage * 24)
      .map((j) => {
        const s = j.score,
          source = sources.find((x) => x.id === j.source_id);
        const appState = j.application_status || "unknown";
        const appLabels = {
          open: "Application open",
          unknown: "Check status",
          closed: "Closed",
          expired: "Deadline passed",
        };
        return `<article class="job-card"><div class="job-top"><div class="company-lockup"><div class="company-icon">${esc(j.company.slice(0, 2).toUpperCase())}</div><div><div class="company-name">${esc(j.company)}</div><div class="source-name">${esc(source?.kind || "Imported listing")}</div></div></div><span class="match ${(s?.total || 0) < 60 ? "low" : ""}">${s ? Math.round(s.total) + "% match" : "Unscored"}</span></div><h3>${esc(j.title)}</h3><div class="job-meta"><span>⌖ ${esc(j.location || "Location unspecified")}</span><span>${esc(j.remote || j.employment_type || "See listing")}</span></div><div class="chips"><span class="chip">${esc({ junior_france: "France / Junior", review: "Needs verification", training: "Internship / apprenticeship", excluded: "Outside focus" }[j.focus?.status] || "Review level")}</span><span class="chip">${esc(s?.category || "Security")}</span><span class="chip application-state ${appState}">${esc(appLabels[appState])}${j.application_deadline ? ` · until ${esc(new Date(j.application_deadline).toLocaleDateString())}` : ""}</span>${j.detail_status !== "full" ? `<span class="chip">${j.detail_status === "summary" ? "Summary only" : "Unverified link"}</span>` : ""}${j.employment_type ? `<span class="chip">${esc(j.employment_type)}</span>` : ""}</div><p class="job-insight">${esc(j.detail_status === "link_only" ? "Discovered automatically. Description and location need verification; this link is not scored." : s?.strengths?.slice(0, 2).join(" · ") || "Review this role against your profile.")}</p><div class="job-bottom"><span title="First discovered ${date(j.first_seen_at)}">${esc(posted(j.published_at))}</span><div class="actions"><a class="secondary listing-link" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener noreferrer">Verify on site ↗</a><button class="secondary" onclick="viewJob(${j.id})">View role</button><button class="primary" onclick="${j.detail_status === "link_only" ? "enrichJob" : "viewJob"}(${j.id},true)">${j.detail_status === "link_only" ? "Add description" : "Draft outreach ↗"}</button></div></div></article>`;
      })
      .join("") ||
    '<div class="empty"><h3>No opportunities here yet.</h3><p>Connect a live source or adjust your filters to broaden the search.</p><button class="primary" onclick="tab(\'sources\')">Explore sources</button></div>';
}
[
  "#job-search",
  "#job-category",
  "#job-source",
  "#min-score",
  "#job-readiness",
  "#job-sort",
  "#job-focus",
  "#job-application-status",
].forEach((s) =>
  $(s).addEventListener(s === "#job-search" ? "input" : "change", () => {
    currentPage = 1;
    if (s === "#job-application-status") {
      loadJobs();
      return;
    }
    renderJobs();
  }),
);
async function scan() {
  const r = await api("/api/scans", { method: "POST" });
  toast(
    r.started
      ? "Live scan started. New jobs appear as each source completes."
      : "A scan is already running.",
  );
  await poll();
}
$("#refresh-all").onclick = scan;
$("#scan-sources").onclick = scan;
$("#rank-all").onclick = async () => {
  await api("/api/jobs/rank-all?use_llm=false", { method: "POST" });
  await loadJobs();
  toast("Ranking updated");
};
let previousScan = "";
async function poll() {
  scanState = await api("/api/scans");
  const r = scanState.runs[0],
    running = scanState.running;
  $("#scan-icon").classList.toggle("running", running);
  $("#refresh-all").disabled = running;
  $("#scan-sources").disabled = running;
  $("#scan-title").textContent = running
    ? `Collecting live offers${r?.current_source ? " · " + r.current_source : ""}`
    : r
      ? `Last scan ${r.status} · ${date(r.finished_at)}`
      : "Ready for your first live scan";
  const results = r?.results || [];
  $("#scan-subtitle").textContent = running
    ? `${results.length} sources completed · you can keep browsing while discovery runs.`
    : results.length
      ? results
          .map(
            (x) =>
              `${x.source}: ${x.error ? "failed" : `${x.created || 0} new, ${x.updated || 0} refreshed`}`,
          )
          .join(" · ")
      : "Connect sources to start discovering real opportunities.";
  $("#scan-timing").textContent = scanState.next_run_at
    ? "Next scan " + date(scanState.next_run_at)
    : running
      ? "Live collection"
      : "Startup + every 2 hours";
  $("#scan-history").innerHTML =
    scanState.runs
      .map(
        (x) =>
          `<div class="scan-row"><strong>${esc(x.status)} · ${esc(x.trigger)}</strong><small> &nbsp; ${date(x.started_at)}</small><div>${x.results.map((r) => `${esc(r.source)}: ${r.error ? '<span class="bad">' + esc(r.error) + "</span>" : `${r.created || 0} new / ${r.updated || 0} refreshed <small>${r.removed_expired ? " &middot; " + r.removed_expired + " expired offers removed" : ""}${r.archived_tracked ? " &middot; " + r.archived_tracked + " tracked offers archived" : ""}${r.expired_filtered ? " &middot; " + r.expired_filtered + " older offers excluded" : ""} &middot; ${r.fetched ?? 0} fetched &middot; ${(r.filtered || 0) + (r.filtered_after_fetch || 0)} filtered &middot; ${r.pages ?? "?"} pages ${r.capped ? " &middot; LIMIT REACHED" : ""}${r.summaries ? " &middot; " + r.summaries + " summaries" : ""}${r.link_only ? " &middot; " + r.link_only + " unverified links" : ""}</small>${(r.warnings || []).map((w) => '<div class="source-error">' + esc(w) + "</div>").join("")}`}`).join("<br>")}</div>${x.error ? `<div class="bad">${esc(x.error)}</div>` : ""}</div>`,
      )
      .join("") || '<p class="muted">Scan history will appear here.</p>';
  const key = JSON.stringify([r?.id, r?.status, r?.results]);
  if (key !== previousScan) {
    previousScan = key;
    sources = await api("/api/sources");
    await loadJobs();
    if ($("#tab-sources").classList.contains("active")) await loadSources();
  }
}
async function loadSources() {
  sources = await api("/api/sources");
  const catalog = await api("/api/source-catalog");
  $("#source-catalog").innerHTML = catalog
    .map((c) => {
      const connected = sources.some((s) => s.name === c.name && s.enabled);
      return `<div class="card"><span class="tag">${esc(c.kind.toUpperCase())}</span><h3>${esc(c.name)}</h3><p>${esc(c.description)}</p><button class="${connected ? "secondary" : "primary"}" ${connected ? "disabled" : ""} onclick="connectSource('${c.key}')">${connected ? "✓ Connected" : "Connect source +"}</button></div>`;
    })
    .join("");
  $("#sources").innerHTML = sources
    .map(
      (s) =>
        `<div class="source-row"><div class="source-head"><strong>${esc(s.name)}</strong><span class="tag">${s.enabled ? "Enabled" : "Paused"}</span></div><small>${esc(s.kind)} · ${s.jobs_seen} listings · checked ${date(s.last_run_at)}${s.config.max_jobs ? " · limit " + s.config.max_jobs + "/scan" : ""}</small>${s.last_error ? `<div class="source-error">${esc(s.last_error)}</div>` : ""}<div class="actions">${s.kind !== "manual" ? `<button class="secondary" onclick="toggleSource(${s.id},${!s.enabled})">${s.enabled ? "Pause" : "Enable"}</button>` : ""}${s.kind !== "manual" && s.kind !== "demo" ? `<button class="text-button" onclick="editSource(${s.id})">Edit search & limits</button>` : ""}<button class="text-button" onclick="deleteSource(${s.id})">Remove</button></div></div>`,
    )
    .join("");
  renderJobs();
}
async function enrichJob(id) {
  const j = await api("/api/jobs/" + id);
  $("#job-dialog").close();
  openImport();
  const f = $("#import-form");
  for (const k of ["title", "company", "url"]) f.elements[k].value = j[k];
  f.elements.location.value =
    j.location === "Location unverified" ? "" : j.location;
  f.elements.description.value = "";
  f.elements.published_at.value = j.published_at
    ? j.published_at.slice(0, 10)
    : "";
}
async function connectSource(key) {
  await api(`/api/source-catalog/${key}/enable`, { method: "POST" });
  await loadSources();
  await scan();
}
async function toggleSource(id, enabled) {
  await api(`/api/sources/${id}/enabled?enabled=${enabled}`, {
    method: "PATCH",
  });
  await loadSources();
}
function editSource(id) {
  const source = sources.find((s) => s.id === id),
    form = $("#source-form");
  editingSourceId = id;
  form.elements.name.value = source.name;
  form.elements.kind.value = source.kind;
  form.elements.config.value = JSON.stringify(source.config, null, 2);
  form.querySelector("button[type=submit]").textContent = "Save source changes";
  form.scrollIntoView({ behavior: "smooth", block: "center" });
}
async function deleteSource(id) {
  if (
    !confirm("Remove this source? Its collected jobs remain in your database.")
  )
    return;
  await api("/api/sources/" + id, { method: "DELETE" });
  await loadSources();
}
$("#source-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  let config;
  try {
    config = JSON.parse(f.get("config"));
  } catch {
    return toast("Configuration must be valid JSON");
  }
  await api(
    editingSourceId ? "/api/sources/" + editingSourceId : "/api/sources",
    {
      method: editingSourceId ? "PUT" : "POST",
      body: JSON.stringify({
        name: f.get("name"),
        kind: f.get("kind"),
        config,
        enabled: editingSourceId
          ? sources.find((s) => s.id === editingSourceId).enabled
          : true,
      }),
    },
  );
  editingSourceId = null;
  e.target.querySelector("button[type=submit]").textContent = "Connect source";
  e.target.reset();
  await loadSources();
  toast("Source saved. Click Scan now to collect listings.");
};
function openImport() {
  $("#import-dialog").showModal();
}
$("#open-import").onclick = openImport;
$("#source-import").onclick = openImport;
$("#import-form").onsubmit = async (e) => {
  e.preventDefault();
  await api("/api/import-job", {
    method: "POST",
    body: JSON.stringify({
      ...Object.fromEntries(new FormData(e.target)),
      published_at: e.target.elements.published_at.value
        ? e.target.elements.published_at.value + "T00:00:00Z"
        : null,
    }),
  });
  $("#import-dialog").close();
  e.target.reset();
  sources = await api("/api/sources");
  await loadJobs();
  toast("Listing imported and ranked");
};
const draftFields = [
  ["connection_note", "Connection note", 3],
  ["recruiter_message", "Recruiter message", 6],
  ["email_subject", "Email subject", 2],
  ["email_body", "Application email", 8],
];
async function copyDraft(k) {
  try {
    await navigator.clipboard.writeText($("#draft-" + k).value);
    toast("Copied to clipboard");
  } catch {
    $("#draft-" + k).select();
    toast("Select and copy the highlighted text");
  }
}
const plainListFields = [
  "preferred_locations",
  "skills",
  "must_have_keywords",
  "nice_to_have_keywords",
  "exclude_keywords",
  "target_seniority",
  "preferred_employment",
  "languages",
];
const jsonFields = [
  "preferred_locations",
  "categories",
  "skills",
  "must_have_keywords",
  "nice_to_have_keywords",
  "exclude_keywords",
  "target_seniority",
  "preferred_employment",
  "languages",
  "education",
  "experience",
  "projects",
  "certifications",
];
$("#profile-form").onsubmit = async (e) => {
  e.preventDefault();
  const data = {};
  for (const [k, v] of new FormData(e.target)) {
    try {
      data[k] = plainListFields.includes(k)
        ? v
            .split("\n")
            .map((x) => x.trim())
            .filter(Boolean)
        : jsonFields.includes(k)
          ? JSON.parse(v)
          : v;
    } catch {
      return toast(`${k}: invalid JSON`);
    }
  }
  await api("/api/profile", { method: "PUT", body: JSON.stringify(data) });
  toast("Profile saved. Re-rank jobs to apply your changes.");
};
async function loadApps() {
  const rows = await api("/api/applications");
  $("#applications").innerHTML =
    rows
      .map((a) => {
        const j = allJobs.find((j) => j.id === a.job_id);
        return `<div class="app-row"><div class="source-head"><div><strong>${esc(j?.title || "Application #" + a.id)}</strong><div class="muted">${esc(j?.company || "")} · ${date(a.created_at)}</div></div><select style="width:140px" onchange="setStatus(${a.id},this.value)">${["generated", "reviewed", "applied", "hr", "technical", "final", "offer", "rejected", "archived"].map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select></div><div class="actions" style="margin:14px 0"><a class="button" href="/api/applications/${a.id}/download">Download package</a><button class="secondary" onclick="viewJob(${a.job_id},true)">Recruiter studio</button></div><button class="secondary" onclick="editFollowup(${a.id})">Follow-up / Interview notes</button><button class="secondary" onclick="showProvenance(${a.job_id})">Source provenance</button><details><summary>Preview cover letter</summary><div class="app-content">${esc(a.cover_letter)}</div></details></div>`;
      })
      .join("") ||
    '<div class="empty"><h3>Your next chapter starts with one application.</h3><p>Open a role and generate its application package.</p></div>';
}
async function setStatus(id, status) {
  await api(`/api/applications/${id}/status?status=${status}`, {
    method: "PATCH",
  });
  toast("Application status updated");
}
(async () => {
  sources = await api("/api/sources");
  await loadJobs();
  await poll();
  health().catch(() => {});
  setInterval(() => poll().catch(() => {}), 3000);
  setInterval(() => health().catch(() => {}), 30000);
})();

function changePage(delta) {
  currentPage += delta;
  renderJobs();
  $("#jobs").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function makeApp(id) {
  await queueTask(id, { kind: "application", quality: "quality" });
}
async function rankJob(id) {
  await queueTask(id, { kind: "analysis", quality: "quality" });
}
const watchedTasks = new Map();
async function queueTask(id, body) {
  const response = await api(`/api/jobs/${id}/ai-tasks`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  watchedTasks.set(response.task.id, response.task);
  toast(
    response.cached
      ? "Loaded saved result."
      : "Queued locally. You can keep browsing.",
  );
  await refreshTasks();
}
async function cancelTask(id) {
  await api(`/api/ai-tasks/${id}/cancel`, { method: "POST" });
  await refreshTasks();
}
let taskPolling = false;
async function refreshTasks() {
  if (taskPolling || document.hidden) return;
  taskPolling = true;
  try {
    const tasks = await api("/api/ai-tasks");
    renderAIHistory(tasks);
    for (const task of tasks) {
      const previous = watchedTasks.get(task.id);
      if (["queued", "running"].includes(task.status))
        watchedTasks.set(task.id, task);
      if (previous && task.status === "succeeded") {
        watchedTasks.delete(task.id);
        if (task.kind === "message" && activeJob?.id === task.job_id) {
          const saved = await api(`/api/jobs/${task.job_id}/messages`);
          if (activeJob?.id === task.job_id) {
            const completedDraft = saved.find(
              (d) => d.id === task.result.draft_id,
            );
            if (completedDraft) {
              draftHistory = saved;
              if (!draftDirty) {
                draft = completedDraft;
                renderDraft();
              } else updateDraftHistory();
            }
          }
        }
        if (task.kind === "analysis") {
          await loadJobs();
          if (
            !draftDirty &&
            activeJob?.id === task.job_id &&
            $("#job-dialog").open
          )
            await viewJob(task.job_id);
        }
        if (task.kind === "application") await loadApps();
        toast(
          `${task.kind === "application" ? "Application package" : task.kind === "analysis" ? "Fit analysis" : task.kind === "agent_review" ? "Agent review (open in Local AI studio)" : "Draft"} ready${task.metrics?.elapsed_seconds ? " in " + task.metrics.elapsed_seconds + "s" : ""}`,
        );
      } else if (previous && ["failed", "cancelled"].includes(task.status)) {
        watchedTasks.delete(task.id);
        toast(task.error || "Generation cancelled");
      }
    }
    const visible = tasks
      .filter((t) => ["queued", "running"].includes(t.status))
      .concat(
        tasks
          .filter(
            (t) =>
              t.status === "failed" &&
              !tasks.some(
                (newer) =>
                  newer.job_id === t.job_id &&
                  newer.kind === t.kind &&
                  newer.created_at > t.created_at,
              ),
          )
          .slice(0, 1),
      );
    $("#ai-activity").hidden = !visible.length;
    $("#ai-activity").innerHTML = visible
      .map(
        (t) =>
          `<div class="task-row"><div><strong>${esc(t.kind)} / ${esc(t.model)}</strong><div>${esc(t.error || t.progress)}</div></div>${["queued", "running"].includes(t.status) ? `<button class="secondary" onclick="cancelTask('${t.id}')">Cancel</button>` : '<span class="bad">Failed</span>'}</div>`,
      )
      .join("");
    const current = tasks.find(
      (t) =>
        t.job_id === activeJob?.id && ["queued", "running"].includes(t.status),
    );
    if (current && $("#draft-status"))
      $("#draft-status").textContent =
        current.progress + " - You can close this window.";
  } finally {
    taskPolling = false;
  }
}
refreshTasks().catch(() => {});
setInterval(() => refreshTasks().catch(() => {}), 1500);

async function profilePackage(id, button) {
  button.disabled = true;
  try {
    await api(`/api/jobs/${id}/application?use_llm=false`, { method: "POST" });
    toast("Profile-only package saved in Applications. No AI tailoring used.");
    await loadApps();
  } finally {
    button.disabled = false;
  }
}

async function editFollowup(id) {
  try {
    const saved = await api(`/api/applications/${id}/followup`);
    const form = document.getElementById("followup-form");
    form.elements.application_id.value = id;
    form.elements.followup_date.value = saved.followup_date;
    form.elements.notes.value = saved.notes;
    document.getElementById("followup-dialog").showModal();
  } catch (error) {
    toast(error.message);
  }
}
async function showProvenance(id) {
  try {
    const rows = await api(`/api/jobs/${id}/observations`);
    document.getElementById("provenance-content").innerHTML = rows.length
      ? rows
          .map(
            (row) =>
              `<article class="card"><strong>${esc(row.status)}</strong><p>${esc(row.checked_at)}</p><a href="${esc(safeUrl(row.url))}" target="_blank" rel="noopener noreferrer">${esc(row.url)}</a></article>`,
          )
          .join("")
      : "<p>No observations recorded yet. Re-scan to populate provenance.</p>";
    document.getElementById("provenance-dialog").showModal();
  } catch (error) {
    toast(error.message);
  }
}
document
  .getElementById("followup-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api(
        `/api/applications/${form.elements.application_id.value}/followup`,
        {
          method: "PUT",
          body: JSON.stringify({
            followup_date: form.elements.followup_date.value,
            notes: form.elements.notes.value,
          }),
        },
      );
      document.getElementById("followup-dialog").close();
      toast("Follow-up saved");
    } catch (error) {
      toast(error.message);
    }
  });
