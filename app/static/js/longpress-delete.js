/**
 * iOS-style long-press delete mode, as two web components shared between
 * Devices and Schedules: <confirm-dialog> (the "Delete X?" prompt, one
 * singleton instance in base.html) and <delete-list> (wraps a row list,
 * used in place of a plain <div> for #device-list / #schedule-list).
 *
 * Both are native custom elements specifically because htmx's boosted
 * navigation replaces the whole <body> (see CLAUDE.md: a <script> tag
 * delivered that way never re-executes, so page-specific JS like
 * devices.js only ever runs once, at the original hard load), which
 * destroys and recreates every element in it on every tab switch. A
 * plain <div> plus manually-bound listeners loses those listeners on
 * that swap; connectedCallback is the platform's own hook for "this
 * element (re)entered the DOM," so a custom element rebinds itself for
 * free every time, with no registry or re-attach bookkeeping needed.
 *
 * <delete-list> still needs its per-list opts (deleteItem/afterDelete/
 * getLabel callbacks) to survive that same swap, and those can only be
 * supplied by devices.js/schedules.js's own one-time run. `configure()`
 * stashes them in the module-level registry below, keyed by element id,
 * so the *next* <delete-list> instance with that id (post-swap) can
 * still find them in its own connectedCallback.
 */
(function () {
  'use strict';

  var LONG_PRESS_MS = 500;
  var MOVE_PX = 8;
  var SKIP_KEY = 'wled-delete-skip-confirm';

  var optsRegistry = new Map(); // element id -> opts, set by configure()

  class ConfirmDialog extends HTMLElement {
    connectedCallback() {
      this._nameEl = this.querySelector('.confirm-dialog__item-name');
      this._noAskEl = this.querySelector('.confirm-dialog__no-ask-input');
      this._resolve = null;

      this._onOk = () => this._settle(true);
      this._onCancel = () => this._settle(false);
      this._onBackdrop = (e) => { if (e.target === this) this._settle(false); };

      this.querySelector('.confirm-dialog__ok-btn').addEventListener('click', this._onOk);
      this.querySelector('.confirm-dialog__cancel-btn').addEventListener('click', this._onCancel);
      this.addEventListener('click', this._onBackdrop);
    }

    disconnectedCallback() {
      // Don't leave an in-flight caller waiting forever if this instance
      // is torn down (e.g. mid-confirm, a boosted nav fires) mid-dialog.
      this._settle(false);
    }

    /** Returns a Promise<boolean>: true if the user confirmed. */
    confirm(name) {
      if (localStorage.getItem(SKIP_KEY) === '1') return Promise.resolve(true);
      this._nameEl.textContent = name;
      this._noAskEl.checked = false;
      this.hidden = false;
      return new Promise((resolve) => { this._resolve = resolve; });
    }

    _settle(ok) {
      if (!this._resolve) return;
      if (ok && this._noAskEl.checked) localStorage.setItem(SKIP_KEY, '1');
      this.hidden = true;
      const resolve = this._resolve;
      this._resolve = null;
      resolve(ok);
    }
  }

  class DeleteList extends HTMLElement {
    connectedCallback() {
      this._opts = optsRegistry.get(this.id) || {};
      this._active = false;
      this._pressTimer = null;
      this._swallowNext = false;
      this._pressX = 0;
      this._pressY = 0;

      // Prevent the browser's native context-menu / link-preview on long press.
      this.addEventListener('contextmenu', (e) => e.preventDefault());

      this.addEventListener('pointerdown', (e) => {
        if (e.target.closest('.delete-mode-btn')) return;
        if (!e.target.closest('.row[data-id]')) return;
        this._pressX = e.clientX;
        this._pressY = e.clientY;
        this._pressTimer = setTimeout(() => {
          this._pressTimer = null;
          this._swallowNext = true; // the pointerup will generate a synthetic click — eat it
          this._enterDeleteMode();
        }, LONG_PRESS_MS);
      });

      const cancelPress = () => {
        if (this._pressTimer) { clearTimeout(this._pressTimer); this._pressTimer = null; }
      };
      this.addEventListener('pointerup', cancelPress);
      this.addEventListener('pointercancel', cancelPress);
      this.addEventListener('pointermove', (e) => {
        if (!this._pressTimer) return;
        if (Math.abs(e.clientX - this._pressX) > MOVE_PX || Math.abs(e.clientY - this._pressY) > MOVE_PX) {
          cancelPress();
        }
      });

      // Capture phase so we can preventDefault before <a> navigation fires.
      this._onOutsideClick = (e) => {
        if (!this._active) return;
        const t = e.target;
        if (t.closest('confirm-dialog') || t.closest('.delete-mode-btn')) return;
        if (!this.contains(t)) this._exitDeleteMode();
      };

      this.addEventListener('click', (e) => this._handleClick(e), true);
    }

    disconnectedCallback() {
      if (this._active) document.removeEventListener('click', this._onOutsideClick, true);
    }

    /** Called once by the page's own script (devices.js/schedules.js). */
    configure(opts) {
      optsRegistry.set(this.id, opts);
      this._opts = opts;
    }

    _enterDeleteMode() {
      if (this._active) return;
      this._active = true;
      this.classList.add('is-delete-mode');
      if (navigator.vibrate) navigator.vibrate(25);
      document.addEventListener('click', this._onOutsideClick, true);
    }

    _exitDeleteMode() {
      if (!this._active) return;
      this._active = false;
      this.classList.remove('is-delete-mode');
      document.removeEventListener('click', this._onOutsideClick, true);
    }

    async _handleClick(e) {
      // Eat the click that fires immediately after the long-press timer fires.
      if (this._swallowNext) {
        this._swallowNext = false;
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }

      const deleteBtn = e.target.closest('.delete-mode-btn');
      if (deleteBtn && this._active) {
        e.preventDefault();
        e.stopPropagation();
        const row = deleteBtn.closest('.row[data-id]');
        if (!row) return;
        const id = row.dataset.id;
        const label = (this._opts.getLabel ? this._opts.getLabel(row) : null)
          || (row.querySelector('.row__title') || {}).textContent.trim()
          || 'this item';

        const dialog = document.querySelector('confirm-dialog');
        const ok = await dialog.confirm(label);
        if (!ok) return;

        // Captured before the delete call, while the item still exists —
        // opts.restore(snapshot) is what a later "Undo" tap replays.
        let snapshot = null;
        if (this._opts.captureForUndo) {
          try {
            snapshot = await this._opts.captureForUndo(id);
          } catch {
            snapshot = null; // no snapshot, no undo offered — deletion still proceeds
          }
        }

        try {
          await this._opts.deleteItem(id);
          row.remove();
          if (this._opts.afterDelete) this._opts.afterDelete();
          if (snapshot && this._opts.restore) {
            toastWithAction(`Deleted "${label}"`, "Undo", async () => {
              try {
                await this._opts.restore(snapshot);
                toast(`Restored "${label}"`);
                if (this._opts.afterRestore) this._opts.afterRestore();
              } catch (err) {
                toast(formatError(err), { error: true });
              }
            });
          }
        } catch (err) {
          toast(formatError(err), { error: true });
        }
        return;
      }

      // Tapping a card body in delete mode exits the mode without navigating.
      if (this._active && e.target.closest('.row[data-id]')) {
        e.preventDefault();
        this._exitDeleteMode();
      }
    }
  }

  customElements.define('confirm-dialog', ConfirmDialog);
  customElements.define('delete-list', DeleteList);

  // Kept as the public API so devices.js/schedules.js don't need to change:
  // attach(el, opts) just forwards to the element's own configure().
  function attach(listEl, opts) {
    if (!listEl) return;
    listEl.configure(opts);
  }

  window.LongPressDelete = { attach: attach };
}());
