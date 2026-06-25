// SCHEDULE_ID is injected by schedule_form.html: null when creating,
// a real id when editing.

let existingActionId = null;

function setDayToggles(bitmask) {
  document.querySelectorAll("#day-toggles input").forEach((input) => {
    input.checked = !!(bitmask & (1 << Number(input.dataset.bit)));
  });
}

function getDaysOfWeekBitmask() {
  let mask = 0;
  document.querySelectorAll("#day-toggles input").forEach((input) => {
    if (input.checked) mask |= 1 << Number(input.dataset.bit);
  });
  return mask;
}

const briToPercent = (bri) => Math.round((bri / 255) * 100);
const percentToBri = (pct) => Math.round((pct / 100) * 255);

function hexToRgb(hex) {
  const m = hex.replace("#", "");
  return [parseInt(m.slice(0, 2), 16), parseInt(m.slice(2, 4), 16), parseInt(m.slice(4, 6), 16)];
}
function rgbToHex([r, g, b]) {
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

function updateTriggerFieldVisibility() {
  const triggerType = document.querySelector('input[name="trigger_type"]:checked').value;
  document.getElementById("time-field").hidden = triggerType !== "time";
  document.getElementById("offset-field").hidden = triggerType === "time";
}

function updateActionModeVisibility() {
  const mode = document.querySelector('input[name="action_mode"]:checked').value;
  document.getElementById("preset-field").hidden = mode !== "preset";
  document.getElementById("state-fields").hidden = mode === "preset";
  if (mode === "preset") loadPresetsForSelectedDevice();
}

function updateOnOffVisibility() {
  const on = document.querySelector('input[name="on_off"]:checked').value === "on";
  document.getElementById("brightness-color-fields").hidden = !on;
}

document.querySelectorAll('input[name="trigger_type"]').forEach((r) =>
  r.addEventListener("change", updateTriggerFieldVisibility)
);
document.querySelectorAll('input[name="action_mode"]').forEach((r) =>
  r.addEventListener("change", updateActionModeVisibility)
);
document.querySelectorAll('input[name="on_off"]').forEach((r) =>
  r.addEventListener("change", updateOnOffVisibility)
);
document.getElementById("brightness").addEventListener("input", (event) => {
  document.getElementById("brightness-value").textContent = `${event.target.value}%`;
});
document.getElementById("device-select").addEventListener("change", () => {
  if (document.getElementById("action-preset").checked) loadPresetsForSelectedDevice();
});

async function loadSettings() {
  const settings = await apiGet("/api/settings");
  const hasLocation = settings.latitude !== null && settings.longitude !== null;
  document.getElementById("trigger-sunrise").disabled = !hasLocation;
  document.getElementById("trigger-sunset").disabled = !hasLocation;
  document.getElementById("location-hint").hidden = hasLocation;
  document.getElementById("timezone-display").textContent = settings.timezone || "Not set";
}

async function loadDevices(selectedId) {
  const devices = await apiGet("/api/devices");
  const select = document.getElementById("device-select");
  select.innerHTML = devices.map((d) => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join("");
  if (selectedId) select.value = selectedId;
}

async function loadPresetsForSelectedDevice(selectedPresetId) {
  const deviceId = document.getElementById("device-select").value;
  const select = document.getElementById("preset-select");
  if (!deviceId) {
    select.innerHTML = "";
    return;
  }
  select.innerHTML = "<option>Loading…</option>";
  try {
    const presets = await apiGet(`/api/devices/${deviceId}/presets`);
    select.innerHTML = presets.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
    if (selectedPresetId != null) select.value = String(selectedPresetId);
  } catch (err) {
    select.innerHTML = `<option>${formatError(err)}</option>`;
  }
}

async function loadExistingSchedule() {
  const schedule = await apiGet(`/api/schedules/${SCHEDULE_ID}`);

  document.getElementById("name").value = schedule.name;
  document.querySelector(`input[name="trigger_type"][value="${schedule.trigger_type}"]`).checked = true;
  if (schedule.trigger_type === "time") {
    document.getElementById("time-of-day").value = schedule.time_of_day.slice(0, 5);
  } else {
    document.getElementById("offset-minutes").value = schedule.offset_minutes;
  }
  setDayToggles(schedule.days_of_week);
  await loadDevices(schedule.device.id);

  const action = schedule.action;
  existingActionId = action.id;

  if (action.type === "preset") {
    document.getElementById("action-preset").checked = true;
    await loadPresetsForSelectedDevice(action.payload.ps);
  } else {
    document.getElementById("action-state").checked = true;
    const on = action.payload.on !== false;
    document.querySelector(`input[name="on_off"][value="${on ? "on" : "off"}"]`).checked = true;
    if (action.payload.bri != null) {
      document.getElementById("brightness").value = briToPercent(action.payload.bri);
      document.getElementById("brightness-value").textContent = `${briToPercent(action.payload.bri)}%`;
    }
    const col = action.payload.seg && action.payload.seg[0] && action.payload.seg[0].col && action.payload.seg[0].col[0];
    if (col) document.getElementById("color").value = rgbToHex(col);
  }

  if (action.transition_ms != null) {
    const select = document.getElementById("transition");
    const match = Array.from(select.options).find((o) => Number(o.value) === action.transition_ms);
    if (match) select.value = String(action.transition_ms);
  }
}

document.getElementById("schedule-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const saveBtn = document.getElementById("save-btn");
  saveBtn.disabled = true;

  try {
    const triggerType = document.querySelector('input[name="trigger_type"]:checked').value;
    // Both trigger fields are always sent explicitly (one of them null),
    // never just one omitted, so a trigger-type switch can never leave
    // the API's partial-update validation looking at a stale leftover
    // field from before the switch.
    const schedulePayload = {
      name: document.getElementById("name").value.trim(),
      device_id: document.getElementById("device-select").value,
      trigger_type: triggerType,
      time_of_day: triggerType === "time" ? document.getElementById("time-of-day").value + ":00" : null,
      offset_minutes: triggerType === "time" ? null : Number(document.getElementById("offset-minutes").value),
      days_of_week: getDaysOfWeekBitmask(),
    };

    const actionMode = document.querySelector('input[name="action_mode"]:checked').value;
    // "4. Options" (the Fade/transition control) is hidden for v1.
    // Deliberately not reading the hidden <select>'s leftover default
    // value here: since the user never saw or chose it, sending it
    // anyway would silently apply a transition speed behind their
    // back. null means no "tt" override gets sent to the device at
    // all, so WLED's own already-configured transition setting applies.
    const transitionMs = null;
    let actionPayload;

    if (actionMode === "preset") {
      actionPayload = {
        name: schedulePayload.name,
        type: "preset",
        payload: { ps: Number(document.getElementById("preset-select").value) },
        transition_ms: transitionMs,
      };
    } else {
      const on = document.querySelector('input[name="on_off"]:checked').value === "on";
      const payload = { on };
      if (on) {
        payload.bri = percentToBri(Number(document.getElementById("brightness").value));
        payload.seg = [{ col: [hexToRgb(document.getElementById("color").value)] }];
      }
      actionPayload = { name: schedulePayload.name, type: "state", payload, transition_ms: transitionMs };
    }

    let actionId;
    if (SCHEDULE_ID) {
      await apiPatch(`/api/actions/${existingActionId}`, actionPayload);
      actionId = existingActionId;
      await apiPatch(`/api/schedules/${SCHEDULE_ID}`, { ...schedulePayload, action_id: actionId });
    } else {
      const action = await apiPost("/api/actions", actionPayload);
      actionId = action.id;
      await apiPost("/api/schedules", { ...schedulePayload, action_id: actionId });
    }

    toast("Schedule saved");
    location.href = "/schedules";
  } catch (err) {
    toast(formatError(err), { error: true });
    saveBtn.disabled = false;
  }
});

document.getElementById("run-now-btn")?.addEventListener("click", async () => {
  try {
    const result = await apiPost(`/api/schedules/${SCHEDULE_ID}/run-now`);
    if (result.status === "success") {
      toast("Ran now successfully");
    } else {
      toast(`Run failed: ${result.error_message || "unknown error"}`, { error: true });
    }
  } catch (err) {
    toast(formatError(err), { error: true });
  }
});

document.getElementById("delete-btn")?.addEventListener("click", async () => {
  if (!confirm("Delete this schedule?")) return;
  try {
    await apiDelete(`/api/schedules/${SCHEDULE_ID}`);
    toast("Schedule deleted");
    location.href = "/schedules";
  } catch (err) {
    toast(formatError(err), { error: true });
  }
});

async function init() {
  await loadSettings();
  if (SCHEDULE_ID) {
    await loadExistingSchedule();
  } else {
    setDayToggles(127);
    await loadDevices();
  }
  updateTriggerFieldVisibility();
  updateActionModeVisibility();
  updateOnOffVisibility();
}

init();
