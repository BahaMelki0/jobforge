const { JSDOM } = require("jsdom");
const fs = require("fs");
const assert = require("node:assert/strict");
const sharedTheme = fs.readFileSync("app/static/design-system.css", "utf8");
assert.match(sharedTheme, /--brand-accent:\s*#f04452/i);
assert.match(sharedTheme, /--brand-bg:\s*#090a0d/i);
assert.match(
  fs.readFileSync("app/templates/index.html", "utf8"),
  /design-system\.css/,
);
const dom = new JSDOM(fs.readFileSync("app/templates/index.html", "utf8"), {
  url: "http://127.0.0.1:8000",
  runScripts: "outside-only",
  pretendToBeVisual: true,
});
const w = dom.window;
w.structuredClone = structuredClone;
w.HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
w.HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
w.HTMLElement.prototype.scrollIntoView = function () {};
w.setInterval = () => 0;
w.confirm = () => false;
const jobs = Array.from({ length: 30 }, (_, i) => ({
  id: i + 1,
  title: "Cloud Security " + i,
  company: "Example",
  location: "Paris",
  source_id: 1,
  focus: { status: "junior_france", reasons: [] },
  detail_status: i === 29 ? "link_only" : "full",
  application_status: i === 0 ? "open" : "unknown",
  url: `https://example.com/jobs/${i}`,
  description: "Security engineering",
  score:
    i === 29 ? null : { total: 80, category: "Cloud", strengths: [], gaps: [] },
  published_at: "2026-09-22T00:00:00",
  first_seen_at: "2026-09-23T00:00:00",
}));
let task = null;
let messages = [];
let profile = {
  name: "Test Candidate",
  headline: "Junior IT",
  summary: "Evidence",
  skills: ["Python"],
  preferred_locations: ["France"],
  categories: { "IT Support / Help Desk": 1 },
  experience: [
    {
      role: "Intern",
      company: "Example",
      summary: "Support",
      bullets: ["Resolved tickets"],
      custom_metadata: "preserve",
    },
  ],
  projects: [],
  education: [],
  certifications: ["Certificate"],
  languages: ["French"],
};
let savedProfile = null,
  savedDraft = null;
w.fetch = async (url, opts = {}) => {
  let data;
  if (url === "/api/sources")
    data = [
      { id: 1, name: "Example", kind: "greenhouse", enabled: true, config: {} },
    ];
  else if (url.startsWith("/api/jobs?")) data = jobs;
  else if (url === "/api/scans") data = { running: false, runs: [] };
  else if (url === "/api/ai/status")
    data = {
      online: true,
      installed: ["test:4b", "quality:9b"],
      loaded: [],
      fast_model: "test:4b",
      quality_model: "quality:9b",
    };
  else if (url === "/api/profile") {
    if (opts.method === "PUT") savedProfile = JSON.parse(opts.body);
    data = profile;
  } else if (url.startsWith("/api/messages/")) {
    savedDraft = JSON.parse(opts.body);
    data = { ok: true };
  } else if (url === "/api/ai-tasks") data = task ? [task] : [];
  else if (url.endsWith("/ai-tasks"))
    data = {
      task: (task = {
        id: "abc",
        job_id: 1,
        kind: "message",
        status: "queued",
        model: "test:4b",
        progress: "Queued",
        request: JSON.parse(opts.body),
      }),
      cached: false,
    };
  else if (url.endsWith("/messages")) data = messages;
  else if (url.startsWith("/api/jobs/"))
    data = jobs.find((j) => j.id === Number(url.split("/")[3]));
  else throw new Error("Unexpected endpoint " + url);
  return { ok: true, json: async () => data };
};
w.eval(
  ["app.js", "studio.js", "profile.js"]
    .map((file) => fs.readFileSync("app/static/" + file, "utf8"))
    .join("\n"),
);
const settle = () => new Promise((r) => setTimeout(r, 20));
(async () => {
  await settle();
  assert.equal(w.document.querySelectorAll(".job-card").length, 24);
  assert.match(
    w.document.querySelector(".application-state").textContent,
    /Application open/,
  );
  assert.equal(
    w.document.querySelector(".listing-link").href,
    "https://example.com/jobs/0",
  );
  assert.ok(w.document.querySelector("#job-application-status"));
  w.changePage(1);
  assert.equal(w.document.querySelectorAll(".job-card").length, 5);
  const filter = w.document.querySelector("#job-readiness");
  filter.value = "link_only";
  filter.dispatchEvent(new w.Event("change"));
  assert.equal(w.document.querySelectorAll(".job-card").length, 1);
  await w.health();
  assert.match(
    w.document.querySelector("#ai-model-status").textContent,
    /quality:9b/,
  );
  await w.viewJob(1, true);
  assert.match(
    w.document.querySelector("#draft-quality").textContent,
    /quality:9b/,
  );
  await w.generateDraft();
  assert.equal(task.request.quality, "quality");
  assert.match(w.document.querySelector("#ai-activity").textContent, /Queued/);
  await w.viewJob(2);
  assert.match(
    w.document.querySelector("#job-detail h2").textContent,
    /Cloud Security 1/,
  );
  messages = [
    {
      id: 11,
      job_id: 1,
      model: "test:4b",
      language: "fr",
      tone: "warm",
      created_at: "2026-09-24T10:00:00",
      content: { recruiter_message: "Bonjour, voici mon experience." },
    },
  ];
  await w.viewJob(1, true);
  const editor = w.document.querySelector("#draft-recruiter_message");
  editor.value = "My unsaved edit";
  editor.dispatchEvent(new w.Event("input"));
  assert.match(
    w.document.querySelector("#draft-save-state").textContent,
    /Unsaved/,
  );
  await w.viewJob(2);
  assert.match(
    w.document.querySelector("#job-detail h2").textContent,
    /Cloud Security 0/,
  );
  // A completed task must not replace edits or change the save target.
  messages.unshift({
    ...messages[0],
    id: 12,
    content: { recruiter_message: "New generated draft" },
  });
  task = {
    ...task,
    status: "succeeded",
    result: { draft_id: 12 },
    metrics: { elapsed_seconds: 3 },
  };
  await w.refreshTasks();
  assert.equal(editor.value, "My unsaved edit");
  await w.saveDraft();
  assert.equal(savedDraft.recruiter_message, "My unsaved edit");
  assert.equal(w.document.querySelector("#draft-history").options.length, 2);
  await w.generateDraft(true);
  assert.equal(task.request.force, true);
  await w.loadProfile();
  const input = w.document.querySelector(
    "#career-experience input[data-field=role]",
  );
  input.value = "Junior Support Intern";
  const form = w.document.querySelector("#profile-form");
  form.dispatchEvent(
    new w.Event("submit", { bubbles: true, cancelable: true }),
  );
  await settle();
  assert.equal(savedProfile.experience[0].role, "Junior Support Intern");
  assert.equal(savedProfile.experience[0].custom_metadata, "preserve");
  await w.viewJob(30, true);
  assert.equal(w.document.querySelector("#generate-draft").disabled, true);
  await w.investigateJob(1);
  assert.equal(task.request.kind, "agent_review");
  task = {
    ...task,
    kind: "agent_review",
    status: "succeeded",
    result: {
      report: {
        summary: "Review <script>bad()</script>",
        evidence: ["Saved profile"],
        gaps: ["Check experience"],
        next_steps: ["Ask recruiter"],
      },
      tools: [{ tool: "read_candidate_profile" }],
      focus: { reasons: [] },
    },
  };
  await w.refreshTasks();
  await w.openTaskResult(task.id);
  assert.equal(w.document.querySelector("#agent-review-dialog").open, true);
  assert.equal(w.document.querySelector("#agent-review-dialog script"), null);
  dom.window.close();
  console.log(
    "UI checks passed: filters, pagination, model status, background generation, draft history, unsaved-edit protection, regeneration, structured profile save and incomplete-job guard.",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
  dom.window.close();
});
