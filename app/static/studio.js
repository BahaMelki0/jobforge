/* AI workspace: shared model diagnostics, job studio and saved draft navigation. */
let modelInfo = null;
let draftHistory = [];
let draftDirty = false;
let openingJob = 0;
let aiTasks = [];

async function health() {
  modelInfo = await api("/api/ai/status");
  const ready =
    modelInfo.online && modelInfo.installed.includes(modelInfo.quality_model);
  $("#health").textContent = ready
    ? `${modelInfo.quality_model} / Local AI ready`
    : modelInfo.error || "Local model missing";
  const status = $("#ai-model-status");
  if (status) {
    const memory = modelInfo.memory?.find(
      (entry) => entry.model === modelInfo.quality_model,
    );
    const memoryLabel = memory
      ? `${memory.gpu_gb} GiB VRAM / ${memory.total_gb} GiB total`
      : "Loads on first request";
    status.innerHTML = `<div class="model-orb ${ready ? "ready" : ""}">AI</div><div><span class="eyebrow">ON YOUR DEVICE</span><h2>${esc(modelInfo.quality_model)}</h2><p>${ready ? "Ready for private drafting and fit analysis." : esc(modelInfo.error || "Install the configured model in Ollama.")}</p><span class="chip">${esc(memoryLabel)}</span><span class="chip">${modelInfo.loaded.includes(modelInfo.quality_model) ? "Loaded in memory" : "Not loaded"}</span><span class="chip">No cloud API</span></div>`;
  }
  updateModelChoices();
  const prepareButton = $("#prepare-model");
  if (prepareButton) {
    prepareButton.disabled = modelInfo.warmup?.status === "loading" || !ready;
    prepareButton.textContent =
      modelInfo.warmup?.status === "loading"
        ? "Preparing model..."
        : "Prepare model";
  }
  return modelInfo;
}

async function prepareModel() {
  await api("/api/ai/warmup", { method: "POST" });
  toast("Preparing the model in the background. You can keep browsing.");
  await health();
}

function updateModelChoices() {
  const select = $("#draft-quality");
  if (!select || !modelInfo) return;
  const previous = select.value;
  select.innerHTML =
    `<option value="quality">Best quality / ${esc(modelInfo.quality_model)}</option>` +
    (modelInfo.quality_model !== modelInfo.fast_model
      ? `<option value="fast">Faster / ${esc(modelInfo.fast_model)}</option>`
      : "");
  select.value = [...select.options].some((o) => o.value === previous)
    ? previous
    : "quality";
}

async function viewJob(id, studio = false) {
  if (
    draftDirty &&
    !confirm("Discard unsaved draft edits before opening this role?")
  )
    return;
  const request = ++openingJob;
  const job = await api("/api/jobs/" + id);
  if (request !== openingJob) return;
  activeJob = job;
  draft = null;
  draftHistory = [];
  draftDirty = false;
  const j = job,
    incomplete = j.detail_status === "link_only";
  const applicationLabels = {
    open: "Application open",
    unknown: "Check application status on the employer site",
    closed: "Closed",
    expired: "Application deadline passed",
  };
  $("#job-detail").innerHTML = `
    <div class="detail-header"><div class="eyebrow">${esc(j.company)} / ${esc(j.location)}</div>
      <h2>${esc(j.title)}</h2><p class="muted">${esc(posted(j.published_at))}</p>
      <div class="actions"><span class="match">${j.score ? Math.round(j.score.total) + "% match" : "Unscored"}</span><span class="chip application-state ${j.application_status || "unknown"}">${esc(applicationLabels[j.application_status] || applicationLabels.unknown)}${j.application_deadline ? ` · until ${esc(new Date(j.application_deadline).toLocaleDateString())}` : ""}</span>
      <a class="secondary" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener noreferrer">Open original listing &nearr;</a></div>
    </div>
    <div class="detail-tabs" role="tablist" aria-label="Job details">
      <button role="tab" class="detail-tab ${!studio ? "active" : ""}" data-detail="role" aria-selected="${!studio}">Role & fit</button>
      <button role="tab" class="detail-tab ${studio ? "active" : ""}" data-detail="studio" aria-selected="${studio}">AI writing studio</button>
    </div>
    <div id="detail-role" ${studio ? "hidden" : ""}>
      <p class="notice">${esc((j.focus?.reasons || []).join(" / ") || "France location and junior experience level match your focus.")}</p>
      <div class="fit-grid"><div class="card"><h3>Evidence that fits</h3><ul>${(j.score?.strengths || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>Import a description to check the fit.</li>"}</ul></div>
      <div class="card"><h3>Gaps to check</h3><ul>${(j.score?.gaps || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>Verify the original requirements.</li>"}</ul></div></div>
      <div class="package-actions"><div><h3>Build your application</h3><p>CV, cover letter, outreach and interview preparation, saved together.</p></div><div class="actions">
      <button class="primary" ${incomplete ? "disabled" : ""} onclick="makeApp(${id},this)">Generate package</button>
      <button class="secondary" ${incomplete ? "disabled" : ""} onclick="rankJob(${id},this)">Analyze fit</button>
      <button class="secondary" ${incomplete ? "disabled" : ""} onclick="investigateJob(${id})">Investigate fit with agent</button>
      <button class="text-button" ${incomplete ? "disabled" : ""} onclick="profilePackage(${id},this)">Profile-only package</button></div></div>
      <details class="description-disclosure" open><summary>Full job description</summary><div class="desc">${esc(j.description || "Description unavailable. Add it to enable local AI.")}</div></details>
    </div>
    <div id="detail-studio" ${!studio ? "hidden" : ""}>
      ${incomplete ? `<div class="notice">This is a discovered link. Add its description before drafting. <button class="text-button" onclick="enrichJob(${id})">Add description</button></div>` : ""}
      <div class="studio-layout"><aside class="studio-settings">
        <div class="eyebrow">01 / YOUR BRIEF</div><h3>Make the introduction yours.</h3>
        <div class="studio-controls">
          <label>Write a<select id="draft-channel"><option value="recruiter_message">Recruiter message</option><option value="connection_note">Connection note</option><option value="email_body">Application email</option></select></label>
          <div class="two-col"><label>Language<select id="draft-language"><option value="fr">Fran&ccedil;ais</option><option value="en">English</option></select></label>
          <label>Tone<select id="draft-tone"><option value="professional">Professional</option><option value="warm">Warm</option><option value="concise">Concise</option></select></label></div>
          <label>Recruiter name <small>optional</small><input id="recruiter-name" placeholder="First name" maxlength="100"></label>
          <label>Local model<select id="draft-quality"><option value="quality">Best quality (default)</option><option value="fast">Faster drafting</option></select></label>
          <button class="primary" id="generate-draft" ${incomplete ? "disabled" : ""}>Generate draft</button>
          <button class="text-button" id="regenerate-draft" ${incomplete ? "disabled" : ""}>Write a new version</button>
        </div>
        <details class="evidence-note"><summary>What the AI works from</summary><p>Your saved profile and this listing. It must not invent certifications, experience or achievements.</p><ul>${(
          j.score?.strengths || []
        )
          .slice(0, 3)
          .map((x) => `<li>${esc(x)}</li>`)
          .join("")}</ul></details>
      </aside><section class="studio-editor" aria-label="Draft editor">
        <div class="editor-heading"><div><div class="eyebrow">02 / REVIEW & PERSONALIZE</div><h3>Your draft</h3></div><select id="draft-history" aria-label="Saved draft versions"><option>No saved drafts</option></select></div>
        <div class="studio-status" id="draft-status" role="status">Checking saved drafts...</div>
        <div id="draft-output"><div class="writing-empty"><span class="writing-mark">Aa</span><h3>A good introduction starts with your experience.</h3><p>Choose a draft type and generate. Your result appears here, ready to edit and copy.</p><div class="chip">Saved locally / Never sent automatically</div></div></div>
      </section></div>
    </div>`;
  $$(".detail-tab").forEach(
    (button) =>
      (button.onclick = () => {
        $$(".detail-tab").forEach((x) => {
          x.classList.toggle("active", x === button);
          x.setAttribute("aria-selected", String(x === button));
        });
        $("#detail-role").hidden = button.dataset.detail !== "role";
        $("#detail-studio").hidden = button.dataset.detail !== "studio";
      }),
  );
  $("#generate-draft").onclick = () => generateDraft(false);
  $("#regenerate-draft").onclick = () => generateDraft(true);
  $("#draft-history").onchange = () =>
    selectDraft(Number($("#draft-history").value));
  updateModelChoices();
  if (!$("#job-dialog").open) $("#job-dialog").showModal();
  const saved = await api(`/api/jobs/${id}/messages`);
  if (request !== openingJob) return;
  draftHistory = saved;
  updateDraftHistory();
  if (saved.length) selectDraft(saved[0].id);
  else
    $("#draft-status").textContent = incomplete
      ? "A description is required."
      : "Ready when you are. The first request also loads the model.";
}

function updateDraftHistory() {
  const select = $("#draft-history");
  if (!select) return;
  select.innerHTML = draftHistory.length
    ? draftHistory
        .map(
          (d, i) =>
            `<option value="${d.id}">${i === 0 ? "Latest / " : ""}${esc(date(d.created_at))} / ${esc(d.language.toUpperCase())}</option>`,
        )
        .join("")
    : "<option>No saved drafts</option>";
  if (draft) select.value = String(draft.id);
}

function selectDraft(id) {
  if (
    draftDirty &&
    !confirm("Discard unsaved edits and open another version?")
  ) {
    $("#draft-history").value = String(draft.id);
    return;
  }
  const selected = draftHistory.find((d) => d.id === id);
  if (!selected) return;
  draft = selected;
  draftDirty = false;
  $("#draft-language").value = draft.language;
  $("#draft-tone").value = draft.tone;
  $("#draft-channel").value = draft.content.email_body
    ? "email_body"
    : draft.content.recruiter_message
      ? "recruiter_message"
      : "connection_note";
  renderDraft();
}

function renderDraft() {
  if (!draft || !$("#draft-output")) return;
  if (!draftHistory.some((d) => d.id === draft.id)) draftHistory.unshift(draft);
  updateDraftHistory();
  $("#draft-status").textContent =
    `${draft.model} / ${date(draft.created_at)} / Saved locally`;
  $("#draft-output").innerHTML =
    draftFields
      .filter(([key]) => draft.content[key])
      .map(
        ([key, label, rows]) => `
    <div class="draft-block"><div class="draft-heading"><label for="draft-${key}">${label}</label><button class="text-button" onclick="copyDraft('${key}')">Copy text</button></div>
    <textarea id="draft-${key}" rows="${rows + 2}" ${key === "connection_note" ? 'maxlength="300"' : ""}>${esc(draft.content[key])}</textarea><div class="word-counter" id="count-${key}"></div></div>`,
      )
      .join("") +
    '<div class="draft-footer"><small id="draft-save-state">Saved. Review facts and tone before sharing.</small><button class="primary" id="save-draft" onclick="saveDraft()">Save edits</button></div>';
  draftFields.forEach(([key]) => {
    const input = $("#draft-" + key);
    if (!input) return;
    const count = () => {
      $("#count-" + key).textContent =
        `${input.value.trim().split(/\s+/).filter(Boolean).length} words / ${input.value.length}${key === "connection_note" ? " of 300" : ""} characters`;
    };
    input.oninput = () => {
      draftDirty = true;
      $("#draft-save-state").textContent = "Unsaved edits";
      count();
    };
    count();
  });
}

async function generateDraft(force = false) {
  if (draftDirty && !confirm("Generate a new draft without saving your edits?"))
    return;
  const id = activeJob.id;
  const body = {
    kind: "message",
    channel: $("#draft-channel").value,
    quality: $("#draft-quality").value,
    language: $("#draft-language").value,
    tone: $("#draft-tone").value,
    recruiter_name: $("#recruiter-name").value,
    force,
  };
  $("#generate-draft").disabled = true;
  $("#draft-status").textContent = "Submitting to your local model...";
  try {
    await queueTask(id, body);
  } catch (error) {
    if (activeJob?.id === id) $("#draft-status").textContent = error.message;
    throw error;
  } finally {
    if (activeJob?.id === id)
      $("#generate-draft").disabled = activeJob.detail_status === "link_only";
  }
}

async function saveDraft() {
  const id = draft.id;
  const content = Object.fromEntries(
    draftFields.map(([key]) => [key, $("#draft-" + key)?.value || ""]),
  );
  await api("/api/messages/" + id, {
    method: "PUT",
    body: JSON.stringify(content),
  });
  const saved = draftHistory.find((d) => d.id === id);
  if (saved) saved.content = content;
  if (draft?.id === id) {
    draft.content = content;
    draftDirty = false;
    $("#draft-save-state").textContent = "All edits saved.";
  }
  toast("Draft edits saved");
}

function renderAIHistory(tasks) {
  aiTasks = tasks;
  if (!$("#ai-task-history")) return;
  $("#ai-task-history").innerHTML =
    tasks
      .slice(0, 12)
      .map((t) => {
        const job = allJobs.find((j) => j.id === t.job_id);
        return `<article class="ai-history-row"><span class="task-status ${esc(t.status)}">${esc(t.status)}</span><div class="task-description"><strong>${esc(job?.title || "Saved job #" + t.job_id)}</strong><small>${esc(t.kind)} / ${esc(t.model)} / ${esc(date(t.created_at))}</small>${t.error ? `<p class="bad">${esc(t.error)}</p>` : ""}</div><div class="task-result">${t.metrics?.elapsed_seconds ? `<span>${t.metrics.elapsed_seconds}s</span>` : ""}${t.status === "succeeded" ? `<button class="secondary" onclick="openTaskResult('${t.id}')">Open result</button>` : ["queued", "running"].includes(t.status) ? `<button class="secondary" onclick="cancelTask('${t.id}')">Cancel</button>` : `<button class="secondary" onclick="retryTask('${t.id}')">Retry</button>`}</div></article>`;
      })
      .join("") ||
    '<div class="empty"><h3>Your AI workspace is ready.</h3><p>Open a role to write an introduction or build an application.</p><button class="primary" onclick="tab(\'jobs\')">Find a role</button></div>';
}

async function openTaskResult(id) {
  const task = aiTasks.find((t) => t.id === id);
  if (!task) return;
  if (task.kind === "agent_review") {
    showAgentReview(task);
    return;
  }
  if (task.kind === "application") {
    tab("applications");
    return;
  }
  await viewJob(task.job_id, task.kind === "message");
  if (activeJob?.id === task.job_id && task.result?.draft_id)
    selectDraft(task.result.draft_id);
}
async function retryTask(id) {
  const task = aiTasks.find((t) => t.id === id);
  if (task) await queueTask(task.job_id, { ...task.request, force: true });
}

async function investigateJob(id) {
  await queueTask(id, {
    kind: "agent_review",
    quality: "quality",
    language: "fr",
  });
  toast(
    "Local agent review queued. Open its result in Local AI studio when ready.",
  );
}

function showAgentReview(task) {
  let dialog = $("#agent-review-dialog");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "agent-review-dialog";
    document.body.append(dialog);
  }
  const job = allJobs.find((j) => j.id === task.job_id);
  const result = task.result || {},
    report = result.report || {};
  dialog.innerHTML = `<button class="close" aria-label="Close review" onclick="this.closest('dialog').close()">&times;</button>
    <div class="eyebrow">LOCAL AGENT REVIEW</div><h2>${esc(job?.title || "Saved offer")}</h2>
    <p class="muted">${esc(task.model)} / ${esc(date(task.created_at))}</p>
    <p class="notice">${esc((result.focus?.reasons || []).join(" / ") || "France / junior focus matches.")}</p>
    <p>${esc(report.summary || "")}</p><div class="fit-grid">
    ${[
      ["evidence", "Supporting evidence"],
      ["gaps", "Gaps and uncertainties"],
    ]
      .map(
        ([key, label]) =>
          `<div class="card"><h3>${label}</h3><ul>${(report[key] || []).map((text) => `<li>${esc(text)}</li>`).join("")}</ul></div>`,
      )
      .join("")}</div>
    <div class="card"><h3>Suggested next steps</h3><ol>${(report.next_steps || []).map((text) => `<li>${esc(text)}</li>`).join("")}</ol></div>
    <p class="muted">Checked: ${(result.tools || []).map((t) => esc({ read_candidate_profile: "saved profile", read_job_requirements: "job requirements", check_career_focus: "France / junior rules" }[t.tool] || t.tool)).join(", ")}. This review made no changes to your profile or applications.</p>`;
  if (!dialog.open) dialog.showModal();
}
window.addEventListener("beforeunload", (event) => {
  if (draftDirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});
$("#job-dialog").addEventListener("cancel", (event) => {
  if (draftDirty && !confirm("Close without saving your edits?"))
    event.preventDefault();
});
$("#job-dialog .close").onclick = () => {
  if (!draftDirty || confirm("Close without saving your edits?")) {
    $("#job-dialog").close();
    draftDirty = false;
  }
};
