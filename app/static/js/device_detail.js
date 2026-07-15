// DEVICE_ID is injected by device_detail.html

function relativeTime(isoUtc) {
  const then = new Date(isoUtc + "Z").getTime();
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function signalParts(percent) {
  if (percent == null) return { label: "—", sub: "No signal data" };
  let label;
  if (percent >= 80) label = "Excellent";
  else if (percent >= 60) label = "Good";
  else if (percent >= 40) label = "Fair";
  else label = "Weak";
  return { label, sub: `${percent}% signal` };
}

// Sets el's text and, only if it actually overflows el's box, wraps
// it in a duplicated, animated track so it scrolls into view instead
// of being cut off — short text (e.g. "Online") is left static since
// there's nothing to gain from scrolling it. Re-checked on every
// render (status polling can change which strings overflow). Called
// from x-effect since the wrap needs real DOM measurement, not just
// a text binding.
function setScrollableText(el, text) {
  el.classList.remove("is-scrolling");
  el.textContent = text;
  requestAnimationFrame(() => {
    if (el.scrollWidth > el.clientWidth) {
      el.innerHTML = "";
      const track = document.createElement("span");
      track.className = "marquee__track";
      const first = document.createElement("span");
      first.textContent = text;
      const gap = document.createElement("span");
      gap.className = "marquee__gap";
      const second = document.createElement("span");
      second.textContent = text;
      track.append(first, gap, second);
      el.appendChild(track);
      el.classList.add("is-scrolling");
    }
  });
}

function _deviceGlyph(iconKey, size) {
  if (iconKey && ICONS[iconKey]) {
    return ICONS[iconKey]
      .replace(/width="\d+"/, `width="${size}"`)
      .replace(/height="\d+"/, `height="${size}"`);
  }
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.4.3.6.8.6 1.3v.3h5.8v-.3c0-.5.2-1 .6-1.3A6 6 0 0 0 12 3Z"/></svg>`;
}

// Alpine component backing the whole device detail page. Registered as a
// global factory (rather than inlined in x-data) because of the amount of
// state and async logic involved — see device_detail.html for the markup.
function deviceDetailData() {
  return {
    device: null,
    schedulesCount: null,
    editing: false,
    editName: "",
    editRoom: "",
    restarting: false,

    async init() {
      this.device = await apiGet(`/api/devices/${DEVICE_ID}`);
      document.dispatchEvent(new CustomEvent("set-icon", { detail: this.device.icon ?? null }));

      document.addEventListener("icon-picker-confirmed", (e) => {
        this.setIcon((e.detail && e.detail.icon) ?? null);
      });

      const schedules = await apiGet(`/api/schedules?device_id=${DEVICE_ID}`);
      this.schedulesCount = schedules.length;
    },

    statusDetail() {
      if (!this.device) return "";
      if (this.device.online) return "Connected";
      return this.device.last_seen_at ? `Last seen ${relativeTime(this.device.last_seen_at)}` : "Never reached";
    },

    signal() {
      const caps = (this.device && this.device.capabilities) || {};
      return signalParts(caps.wifi_signal_percent);
    },

    startEdit() {
      this.editName = this.device.name;
      this.editRoom = this.device.room || "";
      this.editing = true;
      this.$nextTick(() => this.$refs.editNameInput.focus());
    },

    cancelEdit() {
      this.editing = false;
    },

    async save() {
      try {
        this.device = await apiPatch(`/api/devices/${DEVICE_ID}`, {
          name: this.editName.trim(),
          room: this.editRoom.trim() || null,
        });
        this.editing = false;
        toast("Device updated");
      } catch (err) {
        toast(formatError(err), { error: true });
      }
    },

    async setIcon(icon) {
      try {
        this.device = await apiPatch(`/api/devices/${DEVICE_ID}`, { icon });
      } catch (err) {
        toast(formatError(err), { error: true });
      }
    },

    async restart() {
      if (!confirm("Restart this device? It will briefly go offline while it reboots.")) return;
      this.restarting = true;
      try {
        await apiPost(`/api/devices/${DEVICE_ID}/restart`);
        toast("Restart command sent");
      } catch (err) {
        toast(formatError(err), { error: true });
      } finally {
        this.restarting = false;
      }
    },

    async remove() {
      if (!confirm("Remove this device? Any schedules that target it will be deleted too.")) return;
      try {
        await apiDelete(`/api/devices/${DEVICE_ID}`);
        toast("Device removed");
        location.href = "/devices";
      } catch (err) {
        toast(formatError(err), { error: true });
      }
    },
  };
}
