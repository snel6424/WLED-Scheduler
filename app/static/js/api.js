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
    const detail = body && body.detail ? (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)) : `Request failed (${response.status})`;
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

/** A toast with a single action button (e.g. "Undo"), dismissed either by
 * the timeout or by the action firing, whichever comes first. */
function toastWithAction(message, actionLabel, onAction, { timeout = 6000 } = {}) {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const el = document.createElement("div");
  el.className = "toast";

  const text = document.createElement("span");
  text.textContent = message;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "toast__action";
  btn.textContent = actionLabel;

  const timer = setTimeout(() => el.remove(), timeout);
  btn.addEventListener("click", () => {
    clearTimeout(timer);
    el.remove();
    onAction();
  });

  el.append(text, btn);
  region.appendChild(el);
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

/* Shared page sizing behavior now lives in page-init.js. */
