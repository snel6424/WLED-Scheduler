/** Populates the timezone <select> from the browser's own IANA
 * database (Intl.supportedValuesOf), zero network call, falling back
 * to a plain text input on browsers that don't support that API. */
function populateTimezoneOptions(selectEl, currentValue) {
  let zones;
  try {
    zones = Intl.supportedValuesOf("timeZone");
  } catch {
    zones = null;
  }
  if (!zones) {
    const input = document.createElement("input");
    input.type = "text";
    input.id = selectEl.id;
    input.placeholder = "e.g. America/Chicago";
    input.value = currentValue || "";
    selectEl.replaceWith(input);
    return input;
  }
  // UTC is a real, valid IANA designation that resolvedOptions().timeZone
  // can return (common on headless servers), but Intl.supportedValuesOf
  // doesn't actually include it in this engine. Without this, it would
  // be unselectable here, both manually and via "use my location".
  if (!zones.includes("UTC")) {
    zones = ["UTC", ...zones];
  }
  selectEl.innerHTML =
    '<option value="">Not set</option>' + zones.map((z) => `<option value="${z}">${z}</option>`).join("");
  selectEl.value = currentValue || "";
  return selectEl;
}

async function saveField(input, fieldName, parseValue = (v) => v) {
  const rawValue = input.value.trim();
  let value;
  if (rawValue === "") {
    value = null;
  } else {
    value = parseValue(rawValue);
    if (typeof value === "number" && Number.isNaN(value)) {
      toast("Enter a valid number", { error: true });
      input.value = input.dataset.lastSaved || "";
      return;
    }
  }
  try {
    await apiPatch("/api/settings", { [fieldName]: value });
    input.dataset.lastSaved = rawValue;
    toast("Settings saved");
  } catch (err) {
    input.value = input.dataset.lastSaved || "";
    toast(formatError(err), { error: true });
  }
}

document.getElementById("use-my-location-btn").addEventListener("click", () => {
  if (!navigator.geolocation) {
    toast("Geolocation isn't available in this browser", { error: true });
    return;
  }
  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const latInput = document.getElementById("latitude");
      const lngInput = document.getElementById("longitude");
      latInput.value = position.coords.latitude.toFixed(4);
      lngInput.value = position.coords.longitude.toFixed(4);
      await saveField(latInput, "latitude", Number);
      await saveField(lngInput, "longitude", Number);

      // The browser/OS already knows its own timezone for free; this
      // is not derived from the coordinates above, which would need
      // either a paid geocoding API or a bundled timezone-boundary
      // dataset to do properly offline. For the realistic case here,
      // setting up lights from wherever you currently are, the
      // browser's own timezone and the one implied by these
      // coordinates are the same thing anyway.
      const tzEl = document.getElementById("timezone");
      const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tzEl && browserTz) {
        tzEl.value = browserTz;
        if (tzEl.tagName === "SELECT" && tzEl.value !== browserTz) {
          // Defensive: covers any zone name resolvedOptions() can
          // return that Intl.supportedValuesOf() doesn't list (UTC is
          // the known case; this guards against any other one too),
          // rather than silently failing to set it.
          tzEl.insertAdjacentHTML("afterbegin", `<option value="${browserTz}">${browserTz}</option>`);
          tzEl.value = browserTz;
        }
        await saveField(tzEl, "timezone");
      }
    },
    () => {
      toast(
        "Couldn't get your location. This usually means the page isn't on HTTPS or localhost; enter coordinates manually instead.",
        { error: true }
      );
    }
  );
});

async function init() {
  const settings = await apiGet("/api/settings");

  const latInput = document.getElementById("latitude");
  const lngInput = document.getElementById("longitude");
  latInput.value = settings.latitude ?? "";
  lngInput.value = settings.longitude ?? "";
  latInput.dataset.lastSaved = latInput.value;
  lngInput.dataset.lastSaved = lngInput.value;
  latInput.addEventListener("change", () => saveField(latInput, "latitude", Number));
  lngInput.addEventListener("change", () => saveField(lngInput, "longitude", Number));

  const tzEl = populateTimezoneOptions(document.getElementById("timezone"), settings.timezone);
  tzEl.dataset.lastSaved = tzEl.value;
  tzEl.addEventListener("change", () => saveField(tzEl, "timezone"));

  const catchUpToggle = document.getElementById("catch-up-toggle");
  catchUpToggle.checked = settings.catch_up_missed;
  catchUpToggle.addEventListener("change", async () => {
    const checked = catchUpToggle.checked;
    catchUpToggle.disabled = true;
    try {
      await apiPatch("/api/settings", { catch_up_missed: checked });
      toast(checked ? "Catch-up turned on" : "Catch-up turned off");
    } catch (err) {
      catchUpToggle.checked = !checked;
      toast(formatError(err), { error: true });
    } finally {
      catchUpToggle.disabled = false;
    }
  });
}

init().catch((err) => toast(formatError(err), { error: true }));

// Update checker
(function () {
  const btn = document.getElementById("check-update-btn");
  const statusEl = document.getElementById("update-status");
  const actionEl = document.getElementById("update-action");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    statusEl.textContent = "Checking…";
    actionEl.hidden = true;
    actionEl.innerHTML = "";

    let result;
    try {
      result = await apiGet("/api/update/check");
    } catch {
      statusEl.textContent = "Couldn't check for updates — are you connected to the internet?";
      btn.disabled = false;
      return;
    }

    if (!result.update_available) {
      statusEl.textContent = `You're up to date (v${result.current_version}).`;
      btn.disabled = false;
      return;
    }

    // An update is available.
    statusEl.textContent = `v${result.latest_version} is available (you have v${result.current_version}).`;

    if (!result.can_apply_automatically) {
      // Docker / generic install — show the manual command.
      actionEl.innerHTML =
        `<p class="field__hint" style="margin:0;">To update, run:</p>` +
        `<pre style="margin:0.5rem 0 0; background:var(--surface-raised); border:1px solid var(--border); border-radius:var(--radius-sm); padding:0.6rem 0.75rem; font-size:0.82rem; overflow-x:auto; white-space:pre-wrap; word-break:break-all;">git pull && docker compose up --build -d</pre>`;
      actionEl.hidden = false;
    } else {
      // Pi native install — offer the one-click button.
      const updateBtn = document.createElement("button");
      updateBtn.type = "button";
      updateBtn.className = "btn btn--primary";
      updateBtn.textContent = "Update now";
      updateBtn.addEventListener("click", async () => {
        if (!confirm("Update WLED Scheduler now?\n\nThe app will be briefly unavailable while it updates. Check back in about a minute.")) return;
        updateBtn.disabled = true;
        try {
          await apiPost("/api/update/apply");
          actionEl.innerHTML =
            `<p class="field__hint" style="margin:0; color:var(--success);">Update started. The app will be briefly unavailable — check back in about a minute.</p>`;
        } catch (err) {
          toast(formatError(err), { error: true });
          updateBtn.disabled = false;
        }
      });
      actionEl.appendChild(updateBtn);
      actionEl.hidden = false;
    }

    btn.disabled = false;
  });
})();

// Theme toggle — persisted in localStorage, not the Settings table (per-browser preference)
const themeToggle = document.getElementById("theme-toggle");
themeToggle.checked = localStorage.getItem("theme") !== "light";
themeToggle.addEventListener("change", () => {
  if (themeToggle.checked) {
    delete document.documentElement.dataset.theme;
    localStorage.removeItem("theme");
  } else {
    document.documentElement.dataset.theme = "light";
    localStorage.setItem("theme", "light");
  }
});
