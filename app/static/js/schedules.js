const scheduleList = document.getElementById("schedule-list");

scheduleList.addEventListener("change", async (event) => {
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
