const deviceList = document.getElementById("device-list");
const addCard = document.getElementById("add-device-card");
let allDevices = [];
let currentSort = "name";

document.getElementById("show-add-device").addEventListener("click", () => {
  addCard.hidden = !addCard.hidden;
});
document.getElementById("cancel-add-device").addEventListener("click", () => {
  addCard.hidden = true;
});

document.getElementById("add-device-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("device-name").value.trim();
  const host = document.getElementById("device-host").value.trim();
  const room = document.getElementById("device-room").value.trim() || null;
  const payload = { host, room };
  if (name) {
    payload.name = name;
  }

  try {
    await apiPost("/api/devices", payload);
    toast(`Added ${name || host}`);
    document.getElementById("add-device-form").reset();
    addCard.hidden = true;
    await loadDevices();
  } catch (err) {
    toast(formatError(err), { error: true });
  }
});

document.getElementById("sort-select").addEventListener("change", (event) => {
  currentSort = event.target.value;
  renderDevices();
});

function sortDevices(devices) {
  const sorted = [...devices];
  if (currentSort === "status") {
    sorted.sort((a, b) => Number(b.online) - Number(a.online) || a.name.localeCompare(b.name));
  } else {
    sorted.sort((a, b) => a.name.localeCompare(b.name));
  }
  return sorted;
}

function deviceRowHtml(device) {
  const caps = device.capabilities || {};
  const subtitle = device.room || caps.led_count ? `${device.room ? escapeHtml(device.room) : `${caps.led_count} LEDs`}` : device.host;
  const statusClass = device.online ? "badge--success" : "badge--danger";
  const statusText = device.online ? "Online" : "Offline";

  return `
    <a class="row" href="/devices/${device.id}" style="display:flex; align-items:center; text-decoration:none; color:inherit;">
      <div class="icon-avatar icon-avatar--moon" style="margin-right: 1rem;">${ICONS.bulb}</div>
      <div class="row__main">
        <div class="row__title">${escapeHtml(device.name)}</div>
        <div class="row__meta">${subtitle}</div>
      </div>
      <span class="badge ${statusClass}" style="margin-right: 0.75rem;">${statusText}</span>
      <span class="schedule-row__chevron">${ICONS.chevronRight}</span>
    </a>`;
}

function renderSystemsCard(devices) {
  const card = document.getElementById("systems-card");
  const offlineCount = devices.filter((d) => !d.online).length;
  if (devices.length === 0) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  if (offlineCount === 0) {
    card.innerHTML = `
      <div class="info-card__icon">${ICONS.shieldCheck}</div>
      <div><h3>All systems operational</h3><p>All your devices are working normally.</p></div>`;
  } else {
    card.innerHTML = `
      <div class="info-card__icon" style="color: var(--danger);">${ICONS.alertTriangle}</div>
      <div><h3>${offlineCount} device${offlineCount > 1 ? "s" : ""} offline</h3><p>Check power and network connectivity.</p></div>`;
  }
}

function renderDevices() {
  document.getElementById("stat-total").textContent = allDevices.length;
  document.getElementById("stat-online").textContent = allDevices.filter((d) => d.online).length;
  document.getElementById("stat-offline").textContent = allDevices.filter((d) => !d.online).length;
  document.getElementById("stats-row").hidden = allDevices.length === 0;

  renderSystemsCard(allDevices);

  const showAddButton = document.getElementById("show-add-device");
  if (allDevices.length === 0) {
    showAddButton.classList.add("highlight");
    deviceList.innerHTML = `
      <div class="empty">
        <h2>No devices yet</h2>
        <p>Add the IP address of a WLED device on your network to get started.</p>
      </div>`;
    return;
  }

  showAddButton.classList.remove("highlight");
  deviceList.innerHTML = sortDevices(allDevices).map(deviceRowHtml).join("");
}

async function loadDevices() {
  try {
    allDevices = await apiGet("/api/devices");
  } catch (err) {
    deviceList.innerHTML = `<div class="empty"><p>${formatError(err)}</p></div>`;
    return;
  }
  renderDevices();
  startPolling();
}

/* Polling: update device status badges in-place every 15 seconds */
let pollInterval = null;
const POLL_INTERVAL_MS = 15000; // 15 seconds

async function pollDevices() {
  try {
    const devices = await apiGet("/api/devices");

    // Update allDevices array
    allDevices = devices;

    // Update stats
    document.getElementById("stat-total").textContent = allDevices.length;
    document.getElementById("stat-online").textContent = allDevices.filter((d) => d.online).length;
    document.getElementById("stat-offline").textContent = allDevices.filter((d) => !d.online).length;

    // Update each device row's status badge without re-rendering the entire list
    devices.forEach((device) => {
      const row = document.querySelector(`[data-id="${device.id}"]`);
      if (!row) return; // Device row not in DOM, skip

      const badge = row.querySelector(".badge");
      if (badge) {
        const statusClass = device.online ? "badge--success" : "badge--danger";
        const statusText = device.online ? "Online" : "Offline";

        // Update badge classes and text
        badge.classList.remove("badge--success", "badge--danger");
        badge.classList.add(statusClass);
        badge.textContent = statusText;
      }
    });
  } catch (err) {
    // Fail silently for poll ticks; just try again next interval
  }
}

function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(pollDevices, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// Pause polling when tab is hidden, resume immediately when visible again
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopPolling();
  } else {
    // Immediately fetch when tab becomes visible
    pollDevices();
    startPolling();
  }
});

// Stop polling when page unloads
window.addEventListener("beforeunload", () => {
  stopPolling();
});

loadDevices();
