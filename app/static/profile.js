/* Friendly profile editor. Preserve unknown metadata in existing career records. */
const careerSections = {
  experience: {
    title: "Experience",
    fields: [
      ["role", "Role"],
      ["company", "Company"],
      ["summary", "What you worked on"],
      ["bullets", "Evidence and achievements / one per line"],
    ],
  },
  projects: {
    title: "Projects",
    fields: [
      ["name", "Project name"],
      ["summary", "Summary"],
      ["bullets", "What you built / one per line"],
    ],
  },
  education: {
    title: "Education",
    fields: [
      ["degree", "Degree or programme"],
      ["school", "School"],
      ["year", "Year"],
    ],
  },
  certifications: {
    title: "Certifications",
    fields: [["name", "Certification name"]],
  },
};
let careerData = {};
async function loadProfile() {
  const profile = await api("/api/profile");
  for (const [key, value] of Object.entries(profile)) {
    const element = $("#profile-form").elements[key];
    if (element)
      element.value = plainListFields.includes(key)
        ? value.join("\n")
        : jsonFields.includes(key)
          ? JSON.stringify(value, null, 2)
          : (value ?? "");
  }
  for (const key of Object.keys(careerSections)) {
    careerData[key] = (profile[key] || []).map((item) =>
      typeof item === "string" ? { name: item } : structuredClone(item),
    );
    const input = $("#profile-form").elements[key];
    input.closest("label").hidden = true;
    if (!$("#career-" + key)) {
      const section = document.createElement("section");
      section.className = "career-section";
      section.id = "career-" + key;
      input.closest("label").after(section);
    }
    renderCareer(key);
  }
  const categories = $("#profile-form").elements.categories;
  categories.closest("label").hidden = true;
  if (!$("#category-weights"))
    categories
      .closest("label")
      .insertAdjacentHTML(
        "afterend",
        '<section class="career-section" id="category-weights"></section>',
      );
  $("#category-weights").innerHTML =
    '<h3>Career priorities</h3><p class="muted">Relative preference in ranking. Your evidence and experience are assessed separately.</p>' +
    Object.entries(profile.categories || {})
      .map(
        ([key, value]) =>
          `<label>${esc(key)}<input type="number" min="0" max="1" step="0.05" data-category="${esc(key)}" value="${Number(value)}"></label>`,
      )
      .join("");
}
function captureCareer(key) {
  const section = $("#career-" + key);
  if (!section) return;
  section.querySelectorAll("[data-field]").forEach((input) => {
    const index = Number(input.dataset.index),
      field = input.dataset.field;
    if (careerData[key]?.[index])
      careerData[key][index][field] =
        field === "bullets"
          ? input.value
              .split("\n")
              .map((x) => x.trim())
              .filter(Boolean)
          : input.value;
  });
}
function renderCareer(key) {
  const section = $("#career-" + key),
    spec = careerSections[key];
  section.innerHTML =
    `<div class="section-heading"><h3>${spec.title}</h3><button type="button" class="text-button" onclick="addCareer('${key}')">+ Add</button></div>` +
    careerData[key]
      .map(
        (item, index) =>
          `<div class="career-entry">${spec.fields.map(([field, label]) => `<label>${label}${field === "summary" || field === "bullets" ? `<textarea rows="3" data-index="${index}" data-field="${field}">${esc(field === "bullets" ? (item[field] || []).join("\n") : item[field] || "")}</textarea>` : `<input data-index="${index}" data-field="${field}" value="${esc(item[field] || "")}">`}</label>`).join("")}<button type="button" class="text-button remove-entry" onclick="removeCareer('${key}',${index})">Remove entry</button></div>`,
      )
      .join("") +
    (!careerData[key].length
      ? '<p class="muted">Nothing added yet. Only add facts you can substantiate.</p>'
      : "");
}
function addCareer(key) {
  captureCareer(key);
  careerData[key].push({});
  renderCareer(key);
}
function removeCareer(key, index) {
  captureCareer(key);
  careerData[key].splice(index, 1);
  renderCareer(key);
}
$("#profile-form").addEventListener(
  "submit",
  () => {
    for (const key of Object.keys(careerSections)) {
      if (!careerData[key]) continue;
      captureCareer(key);
      $("#profile-form").elements[key].value = JSON.stringify(careerData[key]);
    }
    if ($("#category-weights"))
      $("#profile-form").elements.categories.value = JSON.stringify(
        Object.fromEntries(
          $$("#category-weights input").map((input) => [
            input.dataset.category,
            Number(input.value),
          ]),
        ),
      );
  },
  true,
);
