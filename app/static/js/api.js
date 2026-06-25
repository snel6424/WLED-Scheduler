/**
 * Shared fetch wrapper for every page. The one place that knows the
 * API's error shape ({"detail": "..."}, from FastAPI's HTTPException),
 * so every page gets the actual server-provided reason rather than a
 * generic "request failed" message.
 */

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (response.status === 204) {
    return null;
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = body && body.detail ? body.detail : `Request failed (${response.status})`;
    throw new ApiError(detail, response.status);
  }

  return body;
}

const apiGet = (path) => api(path);
const apiPost = (path, data) => api(path, { method: "POST", body: data ? JSON.stringify(data) : undefined });
const apiPatch = (path, data) => api(path, { method: "PATCH", body: JSON.stringify(data) });
const apiDelete = (path) => api(path, { method: "DELETE" });

/** Toasts. One region, shared across pages; base.html provides the container. */
function toast(message, { error = false } = {}) {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const el = document.createElement("div");
  el.className = "toast" + (error ? " toast--error" : "");
  el.textContent = message;
  region.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

/** Converts a UTC ISO datetime string to a 0-100 position on the
 * 24-hour day bar, in the given IANA timezone. Used identically for
 * every trigger type, since next_run_at is always a concrete instant
 * regardless of how it was triggered. */
function dayBarPosition(isoUtc, timezone) {
  const date = new Date(isoUtc.endsWith("Z") ? isoUtc : isoUtc + "Z");
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone || "UTC",
    hour: "numeric",
    minute: "numeric",
    hourCycle: "h23",
  }).formatToParts(date);
  const hour = Number(parts.find((p) => p.type === "hour").value);
  const minute = Number(parts.find((p) => p.type === "minute").value);
  return ((hour * 60 + minute) / 1440) * 100;
}

/** Renders a day-bar element (the signature gradient + marker) given
 * a next_run_at ISO string and timezone. Returns an HTML string. */
function renderDayBar(isoUtc, timezone, label) {
  if (!isoUtc) {
    return '<div class="day-bar"></div><div class="day-bar__label"><span>Not yet scheduled</span></div>';
  }
  const pct = dayBarPosition(isoUtc, timezone);
  const localTime = new Date(isoUtc.endsWith("Z") ? isoUtc : isoUtc + "Z").toLocaleString("en-US", {
    timeZone: timezone || "UTC",
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
  return (
    `<div class="day-bar"><div class="day-bar__marker" style="left:${pct}%"></div></div>` +
    `<div class="day-bar__label"><span>${label || "Next run"}</span><span>${localTime}</span></div>`
  );
}

function formatError(err) {
  return err instanceof ApiError ? err.message : "Something went wrong. Check the console for details.";
}

/** Shared across every page; avoids each page's JS reimplementing this. */
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : str;
  return div.innerHTML;
}

/** Measures the real rendered tab bar height and exposes it as a CSS
 * variable, rather than guessing a static pixel value in CSS (which
 * was 16px too short on at least one real page, leaving Run now and
 * Delete partly hidden behind the tab bar). Re-measures on resize,
 * since font size, zoom, or orientation changes can all change it. */
function setTabbarHeightVariable() {
  const tabbar = document.querySelector(".tabbar");
  if (!tabbar) return;
  const height = tabbar.getBoundingClientRect().height;
  if (height > 0) {
    document.documentElement.style.setProperty("--tabbar-height", `${height}px`);
  }
}
document.addEventListener("DOMContentLoaded", setTabbarHeightVariable);
window.addEventListener("resize", setTabbarHeightVariable);
