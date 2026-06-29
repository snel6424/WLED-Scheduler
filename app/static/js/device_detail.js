// DEVICE_ID is injected by device_detail.html

function signalLabel(percent) {
  if (percent == null) return "—";
  if (percent >= 80) return `Excellent (${percent}%)`;
  if (percent >= 60) return `Good (${percent}%)`;
  if (percent >= 40) return `Fair (${percent}%)`;
  return `Weak (${percent}%)`;
}

function _deviceGlyph(iconKey, size) {
  if (iconKey && ICONS[iconKey]) {
    return ICONS[iconKey]
      .replace(/width="\d+"/, `width="${size}"`)
      .replace(/height="\d+"/, `height="${size}"`);
  }
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.4.3.6.8.6 1.3v.3h5.8v-.3c0-.5.2-1 .6-1.3A6 6 0 0 0 12 3Z"/></svg>`;
}

function renderDeviceInfo(device) {
  document.getElementById("device-name").textContent = device.name;
  document.getElementById("device-room").textContent = device.room || "No room set";

  const icon = document.getElementById("device-icon");
  icon.classList.remove("icon-avatar--sun", "icon-avatar--moon");
  icon.classList.add(device.online && device.powered_on ? "icon-avatar--sun" : "icon-avatar--moon");
  icon.innerHTML = _deviceGlyph(device.icon, 28);

  document.dispatchEvent(new CustomEvent("set-icon", { detail: device.icon ?? null }));

  const statusEl = document.getElementById("device-status");
  const detailEl = document.getElementById("device-status-detail");
  statusEl.textContent = device.online ? "Online" : "Offline";
  statusEl.style.color = device.online ? "var(--success)" : "var(--danger)";
  detailEl.textContent = device.online
    ? "Connected and responsive"
    : device.last_seen_at
      ? `Last seen ${new Date(device.last_seen_at + "Z").toLocaleString()}`
      : "Never reached";

  const caps = device.capabilities || {};
  document.getElementById("device-signal").textContent = signalLabel(caps.wifi_signal_percent);

  document.getElementById("device-info-detail").innerHTML = `
    <div class="row__meta">Firmware</div>
    <div style="margin-bottom: 0.75rem;">${escapeHtml(caps.version || "Unknown")}</div>
    <div class="row__meta">LEDs</div>
    <div style="margin-bottom: 0.75rem;">${caps.led_count ?? "Unknown"}</div>
    <div class="row__meta">Host</div>
    <div style="margin-bottom: 0.75rem;">${escapeHtml(device.host)}</div>
    <div class="row__meta">MAC address</div>
    <div>${escapeHtml(device.mac || "Unknown")}</div>
  `;

  document.getElementById("edit-name").value = device.name;
  document.getElementById("edit-room").value = device.room || "";
  document.getElementById("edit-row-subtitle").textContent = device.room
    ? `${device.name} · ${device.room}`
    : device.name;
}

document.getElementById("device-info-toggle").addEventListener("click", () => {
  const detail = document.getElementById("device-info-detail");
  detail.hidden = !detail.hidden;
});

document.getElementById("edit-name-row").addEventListener("click", () => {
  document.getElementById("edit-card").hidden = false;
});
document.getElementById("cancel-edit-btn").addEventListener("click", () => {
  document.getElementById("edit-card").hidden = true;
});

document.addEventListener("icon-picker-confirmed", async (e) => {
  try {
    const icon = (e.detail && e.detail.icon) ?? null;
    const device = await apiPatch(`/api/devices/${DEVICE_ID}`, { icon });
    renderDeviceInfo(device);
  } catch (err) {
    toast(formatError(err), { error: true });
  }
});

document.getElementById("save-edit-btn").addEventListener("click", async () => {
  const name = document.getElementById("edit-name").value.trim();
  const room = document.getElementById("edit-room").value.trim() || null;
  try {
    const device = await apiPatch(`/api/devices/${DEVICE_ID}`, { name, room });
    renderDeviceInfo(device);
    document.getElementById("edit-card").hidden = true;
    toast("Device updated");
  } catch (err) {
    toast(formatError(err), { error: true });
  }
});

document.getElementById("remove-device-btn").addEventListener("click", async () => {
  if (!confirm("Remove this device? Any schedules that target it will be deleted too.")) return;
  try {
    await apiDelete(`/api/devices/${DEVICE_ID}`);
    toast("Device removed");
    location.href = "/devices";
  } catch (err) {
    toast(formatError(err), { error: true });
  }
});

async function init() {
  const device = await apiGet(`/api/devices/${DEVICE_ID}`);
  renderDeviceInfo(device);

  document.getElementById("schedules-row").href = `/schedules?device_id=${DEVICE_ID}`;
  document.getElementById("history-row").href = `/history?device_id=${DEVICE_ID}`;

  const schedules = await apiGet(`/api/schedules?device_id=${DEVICE_ID}`);
  document.getElementById("schedules-count").textContent =
    `${schedules.length} schedule${schedules.length === 1 ? "" : "s"}`;
}

init().catch((err) => toast(formatError(err), { error: true }));
