// Restoring re-POSTs the same fields against the *same* Action row (deleting
// a schedule never deletes its Action — see CLAUDE.md), so this is a
// near-complete restore. Two things it can't bring back: the schedule gets
// a new id (any bookmarked edit link for the old one breaks), and its
// execution history is gone for good (ScheduleExecution rows cascade-delete
// with the schedule at the DB level).
async function restoreSchedule(snapshot) {
  const devicePresets = {};
  for (const d of snapshot.devices) {
    if (d.preset != null) devicePresets[d.id] = d.preset;
  }
  await apiPost("/api/schedules", {
    name: snapshot.name,
    description: snapshot.description,
    device_ids: snapshot.devices.map((d) => d.id),
    action_id: snapshot.action.id,
    trigger_type: snapshot.trigger_type,
    time_of_day: snapshot.time_of_day,
    offset_minutes: snapshot.offset_minutes,
    days_of_week: snapshot.days_of_week,
    start_date: snapshot.start_date,
    end_date: snapshot.end_date,
    repeat_annually: snapshot.repeat_annually,
    enabled: snapshot.enabled,
    icon: snapshot.icon,
    device_presets: Object.keys(devicePresets).length ? devicePresets : undefined,
  });
}

LongPressDelete.attach(document.getElementById("schedule-list"), {
  deleteItem: (id) => apiDelete(`/api/schedules/${id}`),
  captureForUndo: (id) => apiGet(`/api/schedules/${id}`),
  restore: restoreSchedule,
  // Only fires after a successful Undo — a plain delete just removes the
  // row in place, same as before, no need to refetch. Restoring creates a
  // schedule with a brand-new id, though, so the list needs a real refetch
  // (matching whatever filter/device is currently selected) to show it.
  afterRestore() {
    const filter = (document.getElementById("active-filter") || {}).value || "all";
    const deviceId = (document.getElementById("device-filter") || {}).value || "";
    const params = new URLSearchParams({ filter });
    if (deviceId) params.set("device_id", deviceId);
    htmx.ajax("GET", `/fragments/schedules/list?${params}`, {
      target: "#schedule-list",
      swap: "innerHTML",
    });
  },
});

// Document-level delegation so this handler survives htmx body swaps.
// Guard prevents double-registration if htmx ever re-evaluates this script.
if (!window._scheduleToggleListenerAttached) {
  window._scheduleToggleListenerAttached = true;
  document.addEventListener("change", async (event) => {
    if (!event.target.closest("#schedule-list")) return;
    const checkbox = event.target.closest('input[data-action="toggle"]');
    if (!checkbox) return;
    const id = checkbox.closest(".row").dataset.id;
    const enabled = checkbox.checked;
    checkbox.disabled = true;
    try {
      await apiPatch(`/api/schedules/${id}`, { enabled });
      toast(enabled ? "Schedule turned on" : "Schedule turned off");
    } catch (err) {
      checkbox.checked = !enabled;
      toast(formatError(err), { error: true });
    } finally {
      checkbox.disabled = false;
    }
  });
}
