// SCHEDULE_ID is injected by schedule_form.html: null when creating,
// a real id when editing.

let existingActionId = null;

// Device names for the per-device preset rows' labels, keyed by id.
// Populated by loadDevices(), which is the only place device data is
// ever fetched in this form.
let deviceNamesById = new Map();

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

// Custom color picker only exposes hue + saturation (value is fixed at
// 100%; dimming is the separate Brightness slider), so these only need
// to round-trip those two axes, not a full HSV/RGB implementation.
function hsToRgb(h, s) {
  const c = s / 100;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  let [r, g, b] = [0, 0, 0];
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  const m = 1 - c;
  return [r, g, b].map((v) => Math.round((v + m) * 255));
}
function rgbToHs([r, g, b]) {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  const s = max === 0 ? 0 : d / max;
  return [Math.round(h), Math.round(s * 100)];
}

// Sets a radio button's checked state and dispatches a change event so
// Alpine's x-model binding picks up the new value reactively. Without
// the event, setting .checked programmatically doesn't notify Alpine.
function setRadio(name, value) {
  const radio = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (!radio) return;
  radio.checked = true;
  radio.dispatchEvent(new Event("change", { bubbles: true }));
}

function updateActionModeVisibility() {
  const mode = document.querySelector('input[name="action_mode"]:checked').value;
  // Alpine's x-show handles preset-field / preset-per-device / state-fields
  // visibility; this function's remaining job is to trigger preset-list
  // loading (single dropdown vs. one dropdown per device).
  if (mode === "preset") {
    if (getSelectedDeviceIds().length > 1) {
      loadPresetsPerDevice();
    } else {
      loadPresetsForSelectedDevice();
    }
  } else {
    setPresetEmptyState("");
    setPresetPerDeviceEmptyState("");
    updateSaveButtonState();
  }
}

// Devices are a checkbox-pill picker (#device-toggles), not a <select>,
// since a schedule can now target more than one. Presets are always
// loaded from each device's own /presets.json (WLED preset numbers are
// per-device, there's no cross-device notion of "the same preset"): a
// single dropdown when exactly one device is selected, one dropdown
// per device (see loadPresetsPerDevice) once more than one is.
function getSelectedDeviceIds() {
  return Array.from(document.querySelectorAll('#device-toggles input:checked')).map((i) => i.value);
}

// Alpine's x-show (not the fragile `hidden` attribute, see CLAUDE.md) owns
// switching between the single preset dropdown and the per-device rows, but
// that switch is driven by device selection count, which lives in plain
// vanilla state (#device-toggles' checkboxes), not an Alpine-bound input.
// This is the bridge: same document-event pattern the set-icon/set-color
// hidden inputs elsewhere in this form use to reach into Alpine state.
function syncDeviceCount() {
  document.dispatchEvent(new CustomEvent("device-count-changed", { detail: getSelectedDeviceIds().length }));
}

function getDevicePresetsMap() {
  const map = {};
  document.querySelectorAll("#preset-per-device-rows [data-device-id]").forEach((row) => {
    const select = row.querySelector("select");
    if (select && select.value) map[row.dataset.deviceId] = Number(select.value);
  });
  return map;
}

function updateSaveButtonState() {
  const saveBtn = document.getElementById("save-btn");
  const selectedIds = getSelectedDeviceIds();
  const noDevicesSelected = selectedIds.length === 0;
  const presetMode = document.getElementById("action-preset").checked;
  let presetInvalid = false;
  if (presetMode) {
    if (selectedIds.length > 1) {
      const presets = getDevicePresetsMap();
      presetInvalid = selectedIds.some((id) => !(id in presets));
    } else {
      presetInvalid = document.getElementById("preset-select").disabled;
    }
  }
  saveBtn.disabled = noDevicesSelected || presetInvalid;
}

function updateRepeatAnnuallyVisibility() {
  const annual = document.getElementById("repeat-annually").checked;
  document.getElementById("repeat-annually-hint").hidden = !annual;
  document.getElementById("start-date-label").textContent = annual ? "Start (month & day)" : "Start date";
  document.getElementById("end-date-label").textContent = annual ? "End (month & day)" : "End date";
  document.getElementById("start-date-hint").textContent = annual
    ? "Required. Only the month and day are used."
    : "Optional. Leave blank to start immediately.";
  document.getElementById("end-date-hint").textContent = annual
    ? "Required. Only the month and day are used."
    : "Optional. Leave blank to continue indefinitely.";
}

document.getElementById("repeat-annually").addEventListener("change", updateRepeatAnnuallyVisibility);
document.querySelectorAll('input[name="action_mode"]').forEach((r) =>
  r.addEventListener("change", updateActionModeVisibility)
);
document.getElementById("brightness").addEventListener("input", (event) => {
  document.getElementById("brightness-value").textContent = `${event.target.value}%`;
});
// Document-level delegation: both #device-toggles and
// #preset-per-device-rows are rebuilt from scratch on every
// loadDevices() / loadPresetsPerDevice() call, so a listener bound
// directly to their children wouldn't survive a reload.
document.getElementById("preset-per-device-rows").addEventListener("change", () => {
  updateSaveButtonState();
});

document.getElementById("device-toggles").addEventListener("change", () => {
  syncDeviceCount();
  updateSaveButtonState();
  if (document.getElementById("action-preset").checked) {
    if (getSelectedDeviceIds().length > 1) loadPresetsPerDevice();
    else loadPresetsForSelectedDevice();
  }
});

async function loadSettings() {
  const settings = await apiGet("/api/settings");
  const hasLocation = settings.latitude !== null && settings.longitude !== null;
  document.getElementById("trigger-sunrise").disabled = !hasLocation;
  document.getElementById("trigger-sunset").disabled = !hasLocation;
  document.getElementById("location-hint").hidden = hasLocation;
  document.getElementById("timezone-display").textContent = settings.timezone || "Not set";
}

function setDeviceEmptyState(message) {
  const hint = document.getElementById("device-empty-state");
  hint.hidden = !message;
  hint.innerHTML = message || "";
}

function setPresetEmptyState(message) {
  const hint = document.getElementById("preset-empty-state");
  hint.hidden = !message;
  hint.innerHTML = message || "";
}

function setPresetPerDeviceEmptyState(message) {
  const hint = document.getElementById("preset-per-device-empty-state");
  hint.hidden = !message;
  hint.innerHTML = message || "";
}

async function loadDevices(selectedIds) {
  const devices = await apiGet("/api/devices");
  const container = document.getElementById("device-toggles");
  const selected = new Set(selectedIds || []);

  if (devices.length === 0) {
    container.innerHTML = "";
    setDeviceEmptyState(
      'No devices yet. <a href="/devices">Add a device</a> before creating a schedule.'
    );
    const presetSelect = document.getElementById("preset-select");
    presetSelect.innerHTML = "";
    presetSelect.disabled = true;
    setPresetEmptyState("");
    syncDeviceCount();
    updateSaveButtonState();
    return;
  }

  setDeviceEmptyState("");
  deviceNamesById = new Map(devices.map((d) => [d.id, d.name]));
  container.innerHTML = devices
    .map((d) => {
      const icon = ICONS[d.icon] || ICONS.lightbulb;
      const checked = selected.has(d.id) ? "checked" : "";
      return `<input type="checkbox" id="device-${d.id}" value="${d.id}" ${checked}>` +
        `<label for="device-${d.id}">${icon}${escapeHtml(d.name)}</label>`;
    })
    .join("");
  const presetSelect = document.getElementById("preset-select");
  presetSelect.disabled = false;
  setPresetEmptyState("");
  syncDeviceCount();
  updateSaveButtonState();
}

async function loadPresetsForSelectedDevice(selectedPresetId) {
  // Presets are per-device on WLED itself; when several devices are
  // selected, the dropdown reflects whichever one is first.
  const deviceId = getSelectedDeviceIds()[0];
  const select = document.getElementById("preset-select");
  if (!deviceId) {
    select.innerHTML = "";
    select.disabled = true;
    setPresetEmptyState("Select a device to load presets.");
    updateSaveButtonState();
    return;
  }
  select.disabled = false;
  select.innerHTML = "<option>Loading…</option>";
  try {
    const presets = await apiGet(`/api/devices/${deviceId}/presets`);
    if (presets.length === 0) {
      select.innerHTML = `<option value="">No saved presets</option>`;
      select.disabled = true;
      setPresetEmptyState(
        'This device has no saved presets. Choose "Custom" or save a preset on the device first.'
      );
    } else {
      select.innerHTML = presets.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
      if (selectedPresetId != null) select.value = String(selectedPresetId);
      setPresetEmptyState("");
    }
  } catch (err) {
    select.innerHTML = `<option>${formatError(err)}</option>`;
    select.disabled = true;
    setPresetEmptyState("Could not load presets.");
  }
  updateSaveButtonState();
}

// One dropdown per linked device, each scoped to that device's own
// presets (fetched independently, since WLED preset numbers only mean
// something per-device). selectedByDeviceId is {device_id: preset_id},
// used when loading an existing schedule for editing.
async function loadPresetsPerDevice(selectedByDeviceId) {
  const deviceIds = getSelectedDeviceIds();
  const container = document.getElementById("preset-per-device-rows");

  if (deviceIds.length === 0) {
    container.innerHTML = "";
    setPresetPerDeviceEmptyState("Select at least one device.");
    updateSaveButtonState();
    return;
  }
  setPresetPerDeviceEmptyState("");

  container.innerHTML = deviceIds
    .map((deviceId) => {
      const name = deviceNamesById.get(deviceId) || deviceId;
      return `<div class="input-row" data-device-id="${deviceId}">` +
        `<div class="input-row__body">` +
        `<label>${escapeHtml(name)}</label>` +
        `<select disabled><option>Loading…</option></select>` +
        `</div></div>`;
    })
    .join("");

  await Promise.all(
    deviceIds.map(async (deviceId) => {
      const row = container.querySelector(`[data-device-id="${deviceId}"]`);
      const select = row.querySelector("select");
      try {
        const presets = await apiGet(`/api/devices/${deviceId}/presets`);
        if (presets.length === 0) {
          select.innerHTML = `<option value="">No saved presets</option>`;
          select.disabled = true;
        } else {
          select.innerHTML = presets
            .map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`)
            .join("");
          select.disabled = false;
          const preselected = selectedByDeviceId?.[deviceId];
          if (preselected != null) select.value = String(preselected);
        }
      } catch (err) {
        select.innerHTML = `<option>${formatError(err)}</option>`;
        select.disabled = true;
      }
      updateSaveButtonState();
    })
  );

  const anyWithoutPresets = deviceIds.some((deviceId) => {
    const select = container.querySelector(`[data-device-id="${deviceId}"] select`);
    return select && select.disabled;
  });
  setPresetPerDeviceEmptyState(
    anyWithoutPresets
      ? 'One or more devices has no saved presets. Choose "Custom" or save a preset on that device first.'
      : ""
  );
  updateSaveButtonState();
}

async function loadExistingSchedule() {
  const schedule = await apiGet(`/api/schedules/${SCHEDULE_ID}`);

  document.getElementById("name").value = schedule.name;
  document.getElementById("description").value = schedule.description || "";
  document.dispatchEvent(new CustomEvent("set-icon", { detail: schedule.icon ?? null }));
  setRadio("trigger_type", schedule.trigger_type);
  if (schedule.trigger_type === "time") {
    document.getElementById("time-of-day").value = schedule.time_of_day.slice(0, 5);
  } else {
    document.getElementById("offset-minutes").value = schedule.offset_minutes;
  }
  setDayToggles(schedule.days_of_week);
  document.getElementById("start-date").value = schedule.start_date || "";
  document.getElementById("end-date").value = schedule.end_date || "";
  document.getElementById("repeat-annually").checked = !!schedule.repeat_annually;
  await loadDevices(schedule.devices.map((d) => d.id));

  const action = schedule.action;
  existingActionId = action.id;

  if (action.type === "preset") {
    setRadio("action_mode", "preset");
    if (schedule.devices.length > 1) {
      // schedule.devices[*].preset is the API's already-resolved effective
      // preset per device (the schedule_devices override if one was ever
      // saved, else the Action's own shared `ps`), so this pre-fills every
      // row even for a schedule that predates per-device mapping.
      const selectedByDeviceId = {};
      for (const d of schedule.devices) {
        if (d.preset != null) selectedByDeviceId[d.id] = d.preset;
      }
      await loadPresetsPerDevice(selectedByDeviceId);
    } else {
      await loadPresetsForSelectedDevice(schedule.devices[0]?.preset ?? action.payload.ps);
    }
  } else {
    setRadio("action_mode", "state");
    const on = action.payload.on !== false;
    setRadio("on_off", on ? "on" : "off");
    if (action.payload.bri != null) {
      document.getElementById("brightness").value = briToPercent(action.payload.bri);
      document.getElementById("brightness-value").textContent = `${briToPercent(action.payload.bri)}%`;
    }
    const col = action.payload.seg && action.payload.seg[0] && action.payload.seg[0].col && action.payload.seg[0].col[0];
    if (col) document.dispatchEvent(new CustomEvent("set-color", { detail: rgbToHex(col) }));
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
      description: document.getElementById("description").value.trim() || null,
      device_ids: getSelectedDeviceIds(),
      trigger_type: triggerType,
      time_of_day: triggerType === "time" ? document.getElementById("time-of-day").value + ":00" : null,
      offset_minutes: triggerType === "time" ? null : Number(document.getElementById("offset-minutes").value),
      days_of_week: getDaysOfWeekBitmask(),
      start_date: document.getElementById("start-date").value || null,
      end_date: document.getElementById("end-date").value || null,
      repeat_annually: document.getElementById("repeat-annually").checked,
      icon: document.getElementById("schedule-icon")?.value || null,
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
      if (schedulePayload.device_ids.length > 1) {
        // The Action itself stays device-agnostic (schedule_devices is the
        // real source of truth for which preset each device gets); ps here
        // is just a representative value carried on the Action record,
        // taken from the first linked device since PresetPayload requires
        // some value. `n` (the friendly preset name) doesn't get one clean
        // answer across devices with different presets, so it's left unset
        // rather than guessing.
        const devicePresets = getDevicePresetsMap();
        schedulePayload.device_presets = devicePresets;
        const representativePs = devicePresets[schedulePayload.device_ids[0]];
        actionPayload = {
          name: schedulePayload.name,
          type: "preset",
          payload: { ps: representativePs },
          transition_ms: transitionMs,
        };
      } else {
        const presetSelect = document.getElementById("preset-select");
        const presetName = presetSelect.options[presetSelect.selectedIndex]?.text || null;
        actionPayload = {
          name: schedulePayload.name,
          type: "preset",
          payload: { ps: Number(presetSelect.value), n: presetName },
          transition_ms: transitionMs,
        };
      }
    } else {
      const on = document.querySelector('input[name="on_off"]:checked').value === "on";
      const payload = { on };
      if (on) {
        payload.bri = percentToBri(Number(document.getElementById("brightness").value));
        payload.seg = [{ col: [hexToRgb(document.getElementById("color").value)], fx: 0 }];
      }
      actionPayload = { name: schedulePayload.name, type: "state", payload, transition_ms: transitionMs };
    }

    if (SCHEDULE_ID) {
      await apiPatch(`/api/actions/${existingActionId}`, actionPayload);
      await apiPatch(`/api/schedules/${SCHEDULE_ID}`, { ...schedulePayload, action_id: existingActionId });
    } else {
      const action = await apiPost("/api/actions", actionPayload);
      await apiPost("/api/schedules", { ...schedulePayload, action_id: action.id });
    }

    toast("Schedule saved");
    location.href = "/schedules";
  } catch (err) {
    toast(formatError(err), { error: true });
    saveBtn.disabled = false;
  }
});

function reportRunResult(deviceResults) {
  if (!deviceResults || deviceResults.length === 0) {
    toast("No devices to run", { error: true });
    return;
  }
  const succeeded = deviceResults.filter((r) => r.status === "success").length;
  const total = deviceResults.length;
  if (succeeded === total) {
    toast(total === 1 ? "Ran successfully" : `Ran successfully on all ${total} devices`);
  } else if (succeeded === 0) {
    const firstError = deviceResults.find((r) => r.error_message)?.error_message;
    toast(firstError || "Run failed", { error: true });
  } else {
    toast(`Ran on ${succeeded}/${total} devices; see history for details`, { error: true });
  }
}

document.getElementById("run-now-btn").addEventListener("click", async () => {
  const btn = document.getElementById("run-now-btn");
  btn.disabled = true;
  try {
    if (SCHEDULE_ID) {
      // Existing schedule: route through the schedule's run-now endpoint so
      // the execution is recorded in history, exactly as the scheduler does.
      const result = await apiPost(`/api/schedules/${SCHEDULE_ID}/run-now`, {});
      reportRunResult(result.device_results);
    } else {
      // New schedule (not yet saved): preview using current form state,
      // applied directly to every currently-selected device.
      const deviceIds = getSelectedDeviceIds();
      if (deviceIds.length === 0) {
        toast("Select at least one device first", { error: true });
        return;
      }

      const actionMode = document.querySelector('input[name="action_mode"]:checked').value;
      let payloadForDevice;

      if (actionMode === "preset") {
        if (deviceIds.length > 1) {
          // Per-device presets, same mapping the per-device dropdowns feed
          // into the schedule on save.
          const devicePresets = getDevicePresetsMap();
          const missing = deviceIds.filter((id) => !(id in devicePresets));
          if (missing.length > 0) {
            toast("Select a preset for every device first", { error: true });
            return;
          }
          payloadForDevice = (id) => ({ ps: devicePresets[id] });
        } else {
          const presetId = document.getElementById("preset-select").value;
          const presetNum = Number(presetId);
          if (!presetId || isNaN(presetNum) || presetNum < 1) {
            toast("Select a preset first", { error: true });
            return;
          }
          payloadForDevice = () => ({ ps: presetNum });
        }
      } else {
        const on = document.querySelector('input[name="on_off"]:checked').value === "on";
        const payload = { on };
        if (on) {
          payload.bri = percentToBri(Number(document.getElementById("brightness").value));
          payload.seg = [{ col: [hexToRgb(document.getElementById("color").value)], fx: 0 }];
        }
        payloadForDevice = () => payload;
      }

      const results = await Promise.all(
        deviceIds.map((id) =>
          apiPost(`/api/devices/${id}/apply`, { payload: payloadForDevice(id) }).then(
            (r) => ({ status: r.status === "success" ? "success" : "failed", error_message: r.error_message }),
            (err) => ({ status: "failed", error_message: formatError(err) })
          )
        )
      );
      reportRunResult(results);
    }
  } catch (err) {
    toast(formatError(err), { error: true });
  } finally {
    btn.disabled = false;
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
  const saveBtn = document.getElementById("save-btn");
  saveBtn.disabled = true;
  try {
    await loadSettings();
    if (SCHEDULE_ID) {
      await loadExistingSchedule();
    } else {
      setDayToggles(127);
      await loadDevices();
    }
    // Alpine's x-show handles triggerType / actionMode / onOff visibility.
    // updateActionModeVisibility still runs here to trigger preset loading
    // when editing an existing preset schedule.
    updateActionModeVisibility();
    updateRepeatAnnuallyVisibility();
  } finally {
    updateSaveButtonState();
  }
}

init();
