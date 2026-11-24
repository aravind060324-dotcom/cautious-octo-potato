const form = document.querySelector("#search-form");
const locationSelect = document.querySelector("#location");
const budgetInput = document.querySelector("#budget");
const budgetButtons = document.querySelectorAll(".budget-btn");
const cuisineInput = document.querySelector("#cuisine");
const cuisineMenu = document.querySelector("#cuisine-menu");
const ratingInput = document.querySelector("#min-rating");
const wishesInput = document.querySelector("#preferences");
const limitInput = document.querySelector("#limit");
const submitButton = document.querySelector("#submit-button");
const formError = document.querySelector("#form-error");
const statusLine = document.querySelector("#status");
const results = document.querySelector("#results");
const filterCount = document.querySelector("#filter-count");

const UNAVAILABLE = "The service is unavailable. You can try again.";
const PREPARING = "Results are being prepared.";

let requestInFlight = false;
let cuisineNames = [];
const customSelects = new Map();

enhanceCustomSelect(locationSelect);
enhanceCustomSelect(limitInput);
setupCuisineSuggest();

locationSelect.addEventListener("invalid", () => {
  setFieldError("location", locationSelect.validationMessage || "Choose a neighborhood.");
});

for (const button of budgetButtons) {
  button.addEventListener("click", () => {
    const value = button.dataset.budget || "";
    budgetInput.value = value;
    for (const other of budgetButtons) {
      other.setAttribute("aria-pressed", String(other === button));
    }
    updateFilterCount();
  });
}

for (const control of [locationSelect, cuisineInput, ratingInput, wishesInput, limitInput]) {
  control.addEventListener("input", updateFilterCount);
  control.addEventListener("change", updateFilterCount);
}

document.addEventListener("click", (event) => {
  for (const ui of customSelects.values()) {
    if (!ui.root.contains(event.target)) {
      closeCustomSelect(ui);
    }
  }
  if (cuisineMenu && !cuisineInput.closest(".suggest-field").contains(event.target)) {
    closeCuisineMenu();
  }
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (requestInFlight) {
    return;
  }
  clearFieldErrors();
  closeAllMenus();
  if (!form.reportValidity()) {
    return;
  }
  search();
});

loadOptions();
updateFilterCount();

async function loadOptions() {
  try {
    const [locationResponse, cuisineResponse] = await Promise.all([
      fetch("/api/locations"),
      fetch("/api/cuisines"),
    ]);
    if (!locationResponse.ok || !cuisineResponse.ok) {
      throw new Error("unavailable");
    }
    const locationBody = await locationResponse.json();
    const cuisineBody = await cuisineResponse.json();
    fillLocations(locationBody.locations || []);
    fillCuisines(cuisineBody.cuisines || []);
  } catch {
    showStatus(UNAVAILABLE, true);
    submitButton.disabled = true;
  }
}

function fillLocations(locations) {
  for (const name of locations) {
    if (!name || name === locationSelect.value) {
      continue;
    }
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    locationSelect.append(option);
  }
  refreshCustomSelect(locationSelect);
}

function fillCuisines(cuisines) {
  cuisineNames = cuisines.map((item) => item.name).filter(Boolean);
}

function enhanceCustomSelect(select) {
  const root = select.closest(".custom-select");
  if (!root || customSelects.has(select)) {
    return;
  }

  select.classList.add("native-select");
  select.tabIndex = -1;

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "select-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.innerHTML = `
    <span class="select-label"></span>
    <span class="material-symbols-outlined chevron" aria-hidden="true">expand_more</span>
  `;

  const menu = document.createElement("div");
  menu.className = "select-menu";
  menu.hidden = true;

  const searchable = root.dataset.searchable === "true";
  let search = null;
  if (searchable) {
    search = document.createElement("input");
    search.type = "search";
    search.className = "select-search";
    search.placeholder = "Search neighborhoods…";
    search.setAttribute("aria-label", "Search neighborhoods");
    menu.append(search);
  }

  const list = document.createElement("div");
  list.className = "select-options";
  list.setAttribute("role", "listbox");
  menu.append(list);

  root.append(trigger, menu);

  const ui = { select, root, trigger, menu, list, search, activeIndex: -1 };
  customSelects.set(select, ui);
  syncCustomSelectLabel(ui);
  rebuildCustomSelectOptions(ui);

  trigger.addEventListener("click", () => {
    if (ui.root.classList.contains("is-open")) {
      closeCustomSelect(ui);
    } else {
      openCustomSelect(ui);
    }
  });

  trigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openCustomSelect(ui);
    }
  });

  if (search) {
    search.addEventListener("input", () => {
      ui.activeIndex = 0;
      rebuildCustomSelectOptions(ui, search.value);
    });
    search.addEventListener("keydown", (event) => handleMenuKey(event, ui));
  }

  list.addEventListener("keydown", (event) => handleMenuKey(event, ui));

  select.addEventListener("change", () => {
    syncCustomSelectLabel(ui);
    rebuildCustomSelectOptions(ui, search ? search.value : "");
  });
}

function refreshCustomSelect(select) {
  const ui = customSelects.get(select);
  if (!ui) {
    return;
  }
  rebuildCustomSelectOptions(ui);
  syncCustomSelectLabel(ui);
}

function rebuildCustomSelectOptions(ui, query = "") {
  const needle = query.trim().toLowerCase();
  ui.list.replaceChildren();
  const options = [...ui.select.options].filter((option) => {
    if (!needle) {
      return true;
    }
    return option.textContent.toLowerCase().includes(needle);
  });

  if (!options.length) {
    const empty = document.createElement("div");
    empty.className = "select-empty";
    empty.textContent = "No matches";
    ui.list.append(empty);
    ui.activeIndex = -1;
    return;
  }

  options.forEach((option, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "select-option";
    button.setAttribute("role", "option");
    button.dataset.value = option.value;
    button.textContent = option.textContent;
    if (option.value === ui.select.value) {
      button.classList.add("is-selected");
      button.setAttribute("aria-selected", "true");
    }
    if (index === ui.activeIndex) {
      button.classList.add("is-active");
    }
    button.addEventListener("click", () => {
      chooseCustomSelectValue(ui, option.value);
    });
    ui.list.append(button);
  });
}

function chooseCustomSelectValue(ui, value) {
  ui.select.value = value;
  ui.select.dispatchEvent(new Event("change", { bubbles: true }));
  syncCustomSelectLabel(ui);
  closeCustomSelect(ui);
  updateFilterCount();
}

function syncCustomSelectLabel(ui) {
  const label = ui.trigger.querySelector(".select-label");
  const selected = ui.select.selectedOptions[0];
  const text = selected ? selected.textContent : "";
  const isPlaceholder = !ui.select.value;
  label.textContent = text || "Select";
  label.classList.toggle("is-placeholder", isPlaceholder);
}

function openCustomSelect(ui) {
  for (const other of customSelects.values()) {
    if (other !== ui) {
      closeCustomSelect(other);
    }
  }
  closeCuisineMenu();
  ui.root.classList.add("is-open");
  ui.menu.hidden = false;
  ui.trigger.setAttribute("aria-expanded", "true");
  ui.activeIndex = Math.max(
    0,
    [...ui.list.querySelectorAll(".select-option")].findIndex((item) =>
      item.classList.contains("is-selected"),
    ),
  );
  rebuildCustomSelectOptions(ui, ui.search ? ui.search.value : "");
  if (ui.search) {
    ui.search.value = "";
    rebuildCustomSelectOptions(ui, "");
    ui.search.focus();
  } else {
    const active = ui.list.querySelector(".select-option.is-active, .select-option.is-selected");
    (active || ui.list.querySelector(".select-option"))?.focus();
  }
}

function closeCustomSelect(ui) {
  ui.root.classList.remove("is-open");
  ui.menu.hidden = true;
  ui.trigger.setAttribute("aria-expanded", "false");
}

function handleMenuKey(event, ui) {
  const options = [...ui.list.querySelectorAll(".select-option")];
  if (!options.length) {
    if (event.key === "Escape") {
      closeCustomSelect(ui);
      ui.trigger.focus();
    }
    return;
  }

  if (event.key === "ArrowDown") {
    event.preventDefault();
    ui.activeIndex = (ui.activeIndex + 1) % options.length;
    markActiveOption(ui, options);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    ui.activeIndex = (ui.activeIndex - 1 + options.length) % options.length;
    markActiveOption(ui, options);
  } else if (event.key === "Enter") {
    event.preventDefault();
    const active = options[ui.activeIndex] || options[0];
    if (active) {
      chooseCustomSelectValue(ui, active.dataset.value);
    }
  } else if (event.key === "Escape") {
    event.preventDefault();
    closeCustomSelect(ui);
    ui.trigger.focus();
  }
}

function markActiveOption(ui, options) {
  options.forEach((option, index) => {
    option.classList.toggle("is-active", index === ui.activeIndex);
  });
  options[ui.activeIndex]?.scrollIntoView({ block: "nearest" });
}

function setupCuisineSuggest() {
  if (!cuisineInput || !cuisineMenu) {
    return;
  }

  cuisineInput.addEventListener("focus", () => {
    renderCuisineSuggestions(cuisineInput.value);
  });

  cuisineInput.addEventListener("input", () => {
    renderCuisineSuggestions(cuisineInput.value);
    updateFilterCount();
  });

  cuisineInput.addEventListener("keydown", (event) => {
    const options = [...cuisineMenu.querySelectorAll(".select-option")];
    if (!options.length) {
      return;
    }
    const active = cuisineMenu.querySelector(".select-option.is-active");
    let index = options.indexOf(active);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      index = Math.min(options.length - 1, index + 1);
      setCuisineActive(options, index);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      index = Math.max(0, index - 1);
      setCuisineActive(options, index);
    } else if (event.key === "Enter" && index >= 0) {
      event.preventDefault();
      chooseCuisine(options[index].dataset.value);
    } else if (event.key === "Escape") {
      closeCuisineMenu();
    }
  });
}

function renderCuisineSuggestions(query) {
  const needle = query.trim().toLowerCase();
  const matches = cuisineNames.filter(
    (name) => !needle || name.toLowerCase().includes(needle),
  );

  cuisineMenu.replaceChildren();
  if (!matches.length) {
    closeCuisineMenu();
    return;
  }

  matches.forEach((name, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "select-option";
    button.setAttribute("role", "option");
    button.dataset.value = name;
    button.textContent = name;
    if (index === 0) {
      button.classList.add("is-active");
    }
    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      chooseCuisine(name);
    });
    cuisineMenu.append(button);
  });

  openCuisineMenu();
}

function setCuisineActive(options, index) {
  options.forEach((option, i) => {
    option.classList.toggle("is-active", i === index);
  });
}

function chooseCuisine(name) {
  cuisineInput.value = name;
  cuisineInput.dispatchEvent(new Event("input", { bubbles: true }));
  closeCuisineMenu();
  updateFilterCount();
}

function openCuisineMenu() {
  for (const ui of customSelects.values()) {
    closeCustomSelect(ui);
  }
  cuisineMenu.hidden = false;
  cuisineInput.closest(".suggest-field")?.classList.add("is-open");
  cuisineInput.setAttribute("aria-expanded", "true");
}

function closeCuisineMenu() {
  if (!cuisineMenu) {
    return;
  }
  cuisineMenu.hidden = true;
  cuisineInput.closest(".suggest-field")?.classList.remove("is-open");
  cuisineInput.setAttribute("aria-expanded", "false");
}

function closeAllMenus() {
  for (const ui of customSelects.values()) {
    closeCustomSelect(ui);
  }
  closeCuisineMenu();
}

async function search() {
  requestInFlight = true;
  submitButton.disabled = true;
  showStatus(PREPARING, false);
  results.replaceChildren();
  formError.textContent = "";

  try {
    const response = await fetch("/api/recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody()),
    });
    if (response.status === 422) {
      hideStatus();
      showFieldErrors(await response.json());
      return;
    }
    if (!response.ok) {
      showStatus(UNAVAILABLE, true);
      return;
    }
    hideStatus();
    renderResults(await response.json());
  } catch {
    showStatus(UNAVAILABLE, true);
  } finally {
    requestInFlight = false;
    submitButton.disabled = false;
  }
}

function requestBody() {
  const body = { location: locationSelect.value };
  if (budgetInput.value) {
    body.budget = budgetInput.value;
  }
  const cuisine = cuisineInput.value.trim();
  if (cuisine) {
    body.cuisine = cuisine;
  }
  if (ratingInput.value !== "") {
    body.min_rating = Number(ratingInput.value);
  }
  const wishes = wishesInput.value.trim();
  if (wishes) {
    body.preferences = wishes;
  }
  body.limit = Number(limitInput.value);
  return body;
}

function showFieldErrors(payload) {
  hideStatus();
  const detail = payload && payload.detail;
  if (typeof detail === "string") {
    formError.textContent = detail;
    return;
  }
  if (!Array.isArray(detail)) {
    formError.textContent = "Check the form and try again.";
    return;
  }
  for (const item of detail) {
    const loc = Array.isArray(item.loc) ? item.loc : [];
    const field = loc[loc.length - 1];
    const message = item.msg || "Check this field.";
    if (!setFieldError(field, message)) {
      formError.textContent = message;
    }
  }
}

function setFieldError(field, message) {
  const slot = document.querySelector(`[data-error-for="${field}"]`);
  if (!slot) {
    return false;
  }
  slot.textContent = message;
  const control = slot.closest(".field")?.querySelector(".control");
  if (control) {
    control.classList.add("is-invalid");
  }
  return true;
}

function clearFieldErrors() {
  formError.textContent = "";
  for (const slot of document.querySelectorAll(".field-error")) {
    slot.textContent = "";
  }
  for (const control of document.querySelectorAll(".control.is-invalid")) {
    control.classList.remove("is-invalid");
  }
}

function renderResults(body) {
  results.replaceChildren();
  const cards = Array.isArray(body.recommendations) ? body.recommendations : [];

  if (cards.length === 0) {
    results.append(renderEmptyState(body));
    return;
  }

  results.append(renderSummary(body.summary || "", cards.length));

  if (body.explanations_available === false) {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = "Written reasons are unavailable. The list is ordered by rating.";
    results.append(note);
  }

  const list = document.createElement("div");
  list.className = "cards";
  const ordered = cards.slice().sort((left, right) => left.rank - right.rank);
  for (const card of ordered) {
    list.append(renderCard(card));
  }
  results.append(list);
}

function renderSummary(text, count) {
  const card = document.createElement("div");
  card.className = "summary-card";
  card.innerHTML = `
    <div class="summary-inner">
      <div class="summary-icon">
        <span class="material-symbols-outlined filled" aria-hidden="true">auto_awesome</span>
      </div>
      <div>
        <div class="summary-meta">
          <span class="summary-kicker">Curated for your evening</span>
          <span class="summary-count">• ${count} match${count === 1 ? "" : "es"} ranked</span>
        </div>
        <p class="summary-text"></p>
      </div>
    </div>
  `;
  card.querySelector(".summary-text").textContent = text;
  return card;
}

function renderEmptyState(body) {
  const section = document.createElement("section");
  section.className = "empty-state";

  const glyph = document.createElement("div");
  glyph.className = "empty-glyph";
  glyph.innerHTML = `<span class="material-symbols-outlined filled" aria-hidden="true">ramen_dining</span>`;

  const title = document.createElement("h2");
  title.textContent = body.summary || "No restaurants matched these choices.";

  const label = document.createElement("p");
  label.className = "empty-label";
  label.textContent = "Choices used";

  const chips = document.createElement("div");
  chips.className = "filter-chips";
  for (const text of filterChipLabels(body.applied_filters)) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = text;
    chips.append(chip);
  }

  const invite = document.createElement("p");
  invite.className = "empty-copy";
  invite.textContent = "No restaurants matched. Widen the search and try again.";

  section.append(glyph, title, label, chips, invite);
  return section;
}

function renderCard(card) {
  const article = document.createElement("article");
  article.className = "card";

  const body = document.createElement("div");
  body.className = "card-body";

  const top = document.createElement("div");
  top.className = "card-top";

  const heading = document.createElement("div");
  heading.className = "card-heading";

  const titleRow = document.createElement("div");
  titleRow.className = "card-title-row";

  const rank = document.createElement("span");
  rank.className = "rank-badge";
  rank.textContent = `Rank #${card.rank}`;

  const title = document.createElement("h3");
  title.className = "card-title";
  title.textContent = card.name || "";
  titleRow.append(rank, title);

  const cuisines = document.createElement("p");
  cuisines.className = "card-cuisines";
  const cuisineText = Array.isArray(card.cuisines) ? card.cuisines.filter(Boolean).join(", ") : "";
  cuisines.textContent = cuisineText ? `Cuisine: ${cuisineText}` : "Cuisine: unavailable";

  const experience = document.createElement("p");
  experience.className = "card-experience";
  const experienceText = Array.isArray(card.rest_types)
    ? card.rest_types.filter(Boolean).join(", ")
    : "";
  experience.textContent = experienceText
    ? `Experience: ${experienceText}`
    : "Experience: unavailable";

  heading.append(titleRow, cuisines, experience);

  const rating = document.createElement("div");
  rating.className = "rating-chip";
  rating.innerHTML = `<span class="material-symbols-outlined" aria-hidden="true">star</span>`;
  const ratingValue = document.createElement("span");
  if (card.rating === null || card.rating === undefined) {
    ratingValue.textContent = "No rating yet";
  } else {
    const votes = Number(card.votes) || 0;
    ratingValue.textContent = `${card.rating} · ${votes.toLocaleString("en-IN")} ratings`;
  }
  rating.append(ratingValue);

  top.append(heading, rating);

  const meta = document.createElement("div");
  meta.className = "card-meta";
  meta.append(
    metaItem(
      "payments",
      card.cost_for_two === null || card.cost_for_two === undefined
        ? "Cost unavailable"
        : `${formatRupees(card.cost_for_two)} for two`,
    ),
    metaItem("location_on", card.location || ""),
  );

  const explanation = document.createElement("div");
  explanation.className = "explanation";
  explanation.innerHTML = `<span class="material-symbols-outlined" aria-hidden="true">tips_and_updates</span>`;
  const explanationText = document.createElement("p");
  explanationText.textContent = card.explanation
    ? card.explanation
    : "A written reason is unavailable.";
  explanation.append(explanationText);

  body.append(top, meta, explanation);
  article.append(body);
  return article;
}

function metaItem(icon, text) {
  const span = document.createElement("span");
  span.className = "meta-item";
  span.innerHTML = `<span class="material-symbols-outlined" aria-hidden="true">${icon}</span>`;
  span.append(document.createTextNode(text));
  return span;
}

function formatRupees(amount) {
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

function filterChipLabels(filters) {
  if (!filters || typeof filters !== "object") {
    return ["none"];
  }
  const labels = {
    location: "Neighborhood",
    budget: "Budget",
    cuisine: "Cuisine",
    min_rating: "Minimum rating",
    preferences: "Extra wishes",
  };
  const parts = Object.entries(filters).map(([key, value]) => `${labels[key] || key}: ${value}`);
  return parts.length ? parts : ["none"];
}

function updateFilterCount() {
  if (!filterCount) {
    return;
  }
  let count = 1;
  if (budgetInput.value) {
    count += 1;
  }
  if (cuisineInput.value.trim()) {
    count += 1;
  }
  if (ratingInput.value !== "") {
    count += 1;
  }
  if (wishesInput.value.trim()) {
    count += 1;
  }
  if (limitInput.value) {
    count += 1;
  }
  filterCount.textContent = `${count} filter${count === 1 ? "" : "s"}`;
}

function showStatus(message, isError) {
  statusLine.hidden = false;
  statusLine.textContent = message;
  statusLine.classList.toggle("is-error", Boolean(isError));
}

function hideStatus() {
  statusLine.hidden = true;
  statusLine.textContent = "";
  statusLine.classList.remove("is-error");
}
