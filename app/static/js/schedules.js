const scheduleList = document.getElementById("schedule-list");
const filterRow = document.getElementById("filter-row");

let allSchedules = [];
let currentFilter = "all";

function formatDaysOfWeek(bitmask) {
  if (bitmask === 127) return "Every day";
  if (bitmask === 0b0011111) return "Weekdays"; // Mon-Fri, bits 0-4
  if (bitmask === 0b1100000) return "Weekends"; // Sat-Sun, bits 5-6
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const days = names.filter((_, i) => bitmask & (1 << i));
  return days.length ? days.join(", ") : "Never";
}

function formatTimeOfDay(timeStr) {
  const [hourStr, minuteStr] = timeStr.split(":");
  let hour = Number(hourStr);
  const period = hour >= 12 ? "PM" : "AM";
  hour = hour % 12 || 12;
  return `${hour}:${minuteStr} ${period}`;
}

function formatSunOffset(triggerType, offsetMinutes) {
  const label = triggerType === "sunrise" ? "Sunrise" : "Sunset";
  if (!offsetMinutes) return label;
  const sign = offsetMinutes > 0 ? "+" : "-";
  return `${label} ${sign}${Math.abs(offsetMinutes)}m`;
}

function scheduleRowHtml(schedule) {
  const { icon, className } = scheduleIcon(schedule);
  const daysText = formatDaysOfWeek(schedule.days_of_week);
  const timeHtml =
    schedule.trigger_type === "time"
      ? `<span class="schedule-row__time schedule-row__time--time">${ICONS.clock}${formatTimeOfDay(schedule.time_of_day)}</span>`
      : `<span class="schedule-row__time schedule-row__time--sun">${ICONS.sunHorizon}${formatSunOffset(schedule.trigger_type, schedule.offset_minutes)}</span>`;

  return `
    <div class="row" data-id="${schedule.id}">
      <div class="schedule-row">
        <div class="icon-avatar ${className}">${icon}</div>
        <div class="schedule-row__body">
          <div class="schedule-row__top">
            <div>
              <div class="row__title">${escapeHtml(schedule.name)}</div>
              <div class="row__meta">${daysText}</div>
              ${timeHtml}
            </div>
            <label class="switch" aria-label="Enabled">
              <input type="checkbox" data-action="toggle" ${schedule.enabled ? "checked" : ""}>
              <span class="switch__track"></span>
            </label>
          </div>
          <div class="schedule-row__footer">
            <span class="tag">${ICONS.bulb}${escapeHtml(schedule.device.name)}</span>
            <a href="/schedules/${schedule.id}/edit" class="schedule-row__chevron" aria-label="Edit ${escapeHtml(schedule.name)}">${ICONS.chevronRight}</a>
          </div>
        </div>
      </div>
    </div>`;
}

function renderList(schedules) {
  if (schedules.length === 0) {
    const isFiltered = currentFilter !== "all";
    scheduleList.innerHTML = `
      <div class="empty">
        <h2>${isFiltered ? "No schedules match this filter" : "No schedules yet"}</h2>
        <p>${isFiltered ? "Try a different filter." : "Create a schedule to automate your lights."}</p>
      </div>`;
    return;
  }
  scheduleList.innerHTML = schedules.map(scheduleRowHtml).join("");
}

function applyFilter() {
  let filtered = allSchedules;
  if (currentFilter === "active") filtered = allSchedules.filter((s) => s.enabled);
  if (currentFilter === "inactive") filtered = allSchedules.filter((s) => !s.enabled);
  if (currentFilter === "sun")
    filtered = allSchedules.filter((s) => s.trigger_type === "sunrise" || s.trigger_type === "sunset");
  renderList(filtered);
}

filterRow.addEventListener("click", (event) => {
  const pill = event.target.closest(".filter-pill");
  if (!pill) return;
  filterRow.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("is-active"));
  pill.classList.add("is-active");
  currentFilter = pill.dataset.filter;
  applyFilter();
});

scheduleList.addEventListener("change", async (event) => {
  const checkbox = event.target.closest('input[data-action="toggle"]');
  if (!checkbox) return;
  const id = checkbox.closest(".row").dataset.id;
  const enabled = checkbox.checked;
  checkbox.disabled = true;
  try {
    await apiPatch(`/api/schedules/${id}`, { enabled });
    const schedule = allSchedules.find((s) => s.id === id);
    if (schedule) schedule.enabled = enabled;
    toast(enabled ? "Schedule turned on" : "Schedule turned off");
  } catch (err) {
    checkbox.checked = !enabled;
    toast(formatError(err), { error: true });
  } finally {
    checkbox.disabled = false;
  }
});

async function loadSchedules() {
  try {
    const params = new URLSearchParams(location.search);
    const deviceId = params.get("device_id");
    allSchedules = await apiGet(deviceId ? `/api/schedules?device_id=${deviceId}` : "/api/schedules");
    if (deviceId && allSchedules.length > 0) {
      const banner = document.createElement("p");
      banner.innerHTML = `Showing schedules for <strong>${escapeHtml(allSchedules[0].device.name)}</strong> · <a href="/schedules">Show all</a>`;
      scheduleList.before(banner);
    }
  } catch (err) {
    scheduleList.innerHTML = `<div class="empty"><p>${formatError(err)}</p></div>`;
    return;
  }
  applyFilter();
}

loadSchedules();
