const PAGE_SIZE = 20;
let offset = 0;
let allEntries = [];
let reachedEnd = false;

function sinceParam() {
  const days = document.getElementById("range-select").value;
  if (days === "all") return null;
  const date = new Date();
  date.setDate(date.getDate() - Number(days));
  return date.toISOString();
}

function groupLabel(isoString) {
  const date = new Date(isoString);
  const entryDate = new Date(date);
  entryDate.setHours(0, 0, 0, 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const formatted = entryDate.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  if (entryDate.getTime() === today.getTime()) return `Today — ${formatted}`;
  if (entryDate.getTime() === yesterday.getTime()) return `Yesterday — ${formatted}`;
  return formatted;
}

// Maps an action to a short label. Preset-type actions don't have an
// inherent on/off concept (applying a preset is just "apply it"), so
// "Turn On / Turn Off" only really applies to state-type actions;
// presets get their own distinct label rather than a forced fit.
function actionLabel(action) {
  if (action.type === "preset") {
    return `Preset #${action.payload.ps}`;
  }
  return action.payload.on === false ? "Turn Off" : "Turn On";
}

// "Successful" / "Failed" covers the two outcomes of an actual fire
// attempt. Skipped is a real, distinct third outcome (a missed
// schedule deliberately not fired because catch-up is off), not a
// failure, so it keeps its own label rather than being folded into
// "Failed".
const STATUS_LABEL = { success: "Successful", failed: "Failed", skipped: "Skipped" };
const STATUS_COLOR = { success: "var(--success)", failed: "var(--danger)", skipped: "var(--text-muted)" };

function entryHtml(entry) {
  const { icon, className } = historyIcon(entry.status);
  const time = new Date(entry.fired_at.endsWith("Z") ? entry.fired_at : entry.fired_at + "Z").toLocaleTimeString(
    "en-US", { hour: "numeric", minute: "2-digit" }
  );
  return `
    <div class="row" style="display:flex; align-items:center;">
      <div class="icon-avatar ${className}" style="margin-right:1rem; flex-shrink:0;">${icon}</div>
      <div class="row__main">
        <div class="row__title">${escapeHtml(entry.schedule.name)} - ${actionLabel(entry.action)} -
          <span style="color:${STATUS_COLOR[entry.status]};">${STATUS_LABEL[entry.status]}</span>
        </div>
        <div class="row__meta">${escapeHtml(entry.device.name)}${entry.error_message ? ` · ${escapeHtml(entry.error_message)}` : ""}</div>
      </div>
      <div class="row__meta mono" style="flex-shrink:0; margin-left: 0.5rem;">${time}</div>
    </div>`;
}

function render() {
  const container = document.getElementById("history-groups");
  if (allEntries.length === 0) {
    container.innerHTML = `<div class="empty"><h2>No activity yet</h2><p>Schedule runs will show up here once they start firing.</p></div>`;
    document.getElementById("load-more-btn").hidden = true;
    return;
  }

  const groups = new Map();
  for (const entry of allEntries) {
    const label = groupLabel(entry.fired_at.endsWith("Z") ? entry.fired_at : entry.fired_at + "Z");
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(entry);
  }

  let html = "";
  for (const [label, entries] of groups) {
    html += `<h3 style="margin: 1.5rem 0 0.75rem;">${escapeHtml(label)}</h3><div class="list">`;
    html += entries.map(entryHtml).join("");
    html += `</div>`;
  }
  container.innerHTML = html;
  document.getElementById("load-more-btn").hidden = reachedEnd;
}

async function loadPage(reset) {
  if (reset) {
    offset = 0;
    allEntries = [];
    reachedEnd = false;
  }
  const params = new URLSearchParams();
  const deviceId = document.getElementById("device-filter").value;
  if (deviceId) params.set("device_id", deviceId);
  const since = sinceParam();
  if (since) params.set("since", since);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(offset));

  try {
    const page = await apiGet(`/api/history?${params.toString()}`);
    allEntries = allEntries.concat(page);
    offset += page.length;
    reachedEnd = page.length < PAGE_SIZE;
    render();
  } catch (err) {
    document.getElementById("history-groups").innerHTML = `<div class="empty"><p>${formatError(err)}</p></div>`;
  }
}

document.getElementById("range-select").addEventListener("change", () => loadPage(true));
document.getElementById("device-filter").addEventListener("change", () => loadPage(true));
document.getElementById("load-more-btn").addEventListener("click", () => loadPage(false));

async function init() {
  const devices = await apiGet("/api/devices");
  const select = document.getElementById("device-filter");
  select.insertAdjacentHTML(
    "beforeend",
    devices.map((d) => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join("")
  );

  const params = new URLSearchParams(location.search);
  const deviceId = params.get("device_id");
  if (deviceId) select.value = deviceId;

  await loadPage(true);
}

init().catch((err) => toast(formatError(err), { error: true }));
