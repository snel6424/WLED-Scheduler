LongPressDelete.attach(document.getElementById("schedule-list"), {
  deleteItem: (id) => apiDelete(`/api/schedules/${id}`),
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
