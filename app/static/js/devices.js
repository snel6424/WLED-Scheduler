/** Devices page — add-device form only.
 *
 * Device list rendering and status polling are now handled server-side
 * (Jinja initial render + htmx OOB swaps on every poll tick). This
 * file is responsible only for the add-device form submission, which
 * still goes through the existing apiPost helper so error messages from
 * the server surface cleanly in the toast.
 *
 * After a successful add, htmx.ajax re-fetches the list fragment, which
 * carries OOB updates for the stats row and systems card as well, so one
 * request brings every counter back in sync.
 */

LongPressDelete.attach(document.getElementById("device-list"), {
  deleteItem: (id) => apiDelete(`/api/devices/${id}`),
  afterDelete() {
    const sort = (document.getElementById("sort-select") || {}).value || "name";
    htmx.ajax("GET", `/fragments/devices/list?sort=${sort}`, {
      target: "#device-list",
      swap: "innerHTML",
    });
  },
});

// A hand-edited host no longer necessarily belongs to whatever scan
// result last filled the mdns_name hidden field, so clear it rather
// than submit a mismatched pair.
document.getElementById("device-host").addEventListener("input", () => {
  document.getElementById("device-mdns-name").value = "";
});

document.getElementById("add-device-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("device-name").value.trim();
  const host = document.getElementById("device-host").value.trim();
  const room = document.getElementById("device-room").value.trim() || null;
  const mdnsName = document.getElementById("device-mdns-name").value.trim();
  const payload = { host, room };
  if (name) payload.name = name;
  if (mdnsName) payload.mdns_name = mdnsName;

  const submitBtn = event.target.querySelector('[type="submit"]');
  submitBtn.disabled = true;

  try {
    await apiPost("/api/devices", payload);
    toast(`Added ${name || host}`);
    event.target.reset();

    // Close the Alpine-managed add form. Dispatching on document lets
    // the x-data component's @device-added.document listener pick it up
    // even though the form sits inside a different DOM subtree.
    document.dispatchEvent(new CustomEvent("device-added"));

    // Refresh the device list (and stats via OOB) without a full reload.
    const sortSelect = document.getElementById("sort-select");
    const sort = sortSelect ? sortSelect.value : "name";
    htmx.ajax("GET", `/fragments/devices/list?sort=${sort}`, {
      target: "#device-list",
      swap: "innerHTML",
    });
  } catch (err) {
    toast(formatError(err), { error: true });
  } finally {
    submitBtn.disabled = false;
  }
});
