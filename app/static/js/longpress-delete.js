/**
 * iOS-style long-press delete mode, shared between Devices and Schedules.
 *
 * Call LongPressDelete.attach(listEl, opts) once per list:
 *   opts.deleteItem(id)   async, calls the delete API
 *   opts.afterDelete()    optional, called after the row is removed
 *   opts.getLabel(row)    optional, returns the dialog item name
 *
 * This file lives in <head> and executes exactly once. Event delegation is
 * used for the confirm dialog so listeners survive htmx body swaps. A
 * registry re-attaches list bindings after every htmx:afterSettle so
 * boost-navigating away and back works without a hard refresh.
 */
(function () {
  'use strict';

  var LONG_PRESS_MS = 500;
  var SKIP_KEY = 'wled-delete-skip-confirm';
  var MOVE_PX = 8;

  var activeList = null;
  var pressTimer = null;
  var pressX = 0;
  var pressY = 0;
  var swallowNext = false;
  var pendingOk = null;

  // ── confirmation dialog — event delegation so listeners survive body swaps ──

  document.addEventListener('click', function (e) {
    if (e.target.id === 'delete-confirm-ok') {
      if (document.getElementById('delete-confirm-no-ask').checked) {
        localStorage.setItem(SKIP_KEY, '1');
      }
      document.getElementById('delete-confirm-backdrop').hidden = true;
      var cb = pendingOk; pendingOk = null;
      if (cb) cb();
    } else if (e.target.id === 'delete-confirm-cancel') {
      document.getElementById('delete-confirm-backdrop').hidden = true;
      pendingOk = null;
    } else if (e.target.id === 'delete-confirm-backdrop') {
      document.getElementById('delete-confirm-backdrop').hidden = true;
      pendingOk = null;
    }
  });

  function showConfirm(name, onOk) {
    if (localStorage.getItem(SKIP_KEY) === '1') { onOk(); return; }
    var span = document.getElementById('delete-confirm-item-name');
    if (span) span.textContent = name;
    document.getElementById('delete-confirm-no-ask').checked = false;
    pendingOk = onOk;
    document.getElementById('delete-confirm-backdrop').hidden = false;
  }

  // ── delete mode ──────────────────────────────────────────────────────────

  function enter(listEl) {
    if (activeList === listEl) return;
    if (activeList) activeList.classList.remove('is-delete-mode');
    activeList = listEl;
    listEl.classList.add('is-delete-mode');
    if (navigator.vibrate) navigator.vibrate(25);
    document.addEventListener('click', onOutside, true);
  }

  function exit() {
    if (!activeList) return;
    activeList.classList.remove('is-delete-mode');
    activeList = null;
    document.removeEventListener('click', onOutside, true);
  }

  function onOutside(e) {
    if (!activeList) return;
    var t = e.target;
    if (t.closest('#delete-confirm-backdrop') || t.closest('.delete-mode-btn')) return;
    if (!activeList.contains(t)) exit();
  }

  // ── long-press detection ─────────────────────────────────────────────────

  function cancelPress() {
    if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
  }

  // ── attach internals ─────────────────────────────────────────────────────

  var _registry = [];

  function _doAttach(listEl, opts) {
    if (listEl._lpdAttached) return;
    listEl._lpdAttached = true;

    // Prevent the browser's native context-menu / link-preview on long press.
    listEl.addEventListener('contextmenu', function (e) { e.preventDefault(); });

    listEl.addEventListener('pointerdown', function (e) {
      if (e.target.closest('.delete-mode-btn')) return;
      if (!e.target.closest('.row[data-id]')) return;
      pressX = e.clientX;
      pressY = e.clientY;
      pressTimer = setTimeout(function () {
        pressTimer = null;
        swallowNext = true;   // the pointerup will generate a synthetic click — eat it
        enter(listEl);
      }, LONG_PRESS_MS);
    });

    listEl.addEventListener('pointerup',     cancelPress);
    listEl.addEventListener('pointercancel', cancelPress);
    listEl.addEventListener('pointermove', function (e) {
      if (!pressTimer) return;
      if (Math.abs(e.clientX - pressX) > MOVE_PX || Math.abs(e.clientY - pressY) > MOVE_PX) {
        cancelPress();
      }
    });

    // Capture phase so we can preventDefault before <a> navigation fires.
    listEl.addEventListener('click', function (e) {
      // Eat the click that fires immediately after the long-press timer fires.
      if (swallowNext) {
        swallowNext = false;
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }

      var deleteBtn = e.target.closest('.delete-mode-btn');
      if (deleteBtn && activeList === listEl) {
        e.preventDefault();
        e.stopPropagation();
        var row = deleteBtn.closest('.row[data-id]');
        if (!row) return;
        var id  = row.dataset.id;
        var lbl = (opts.getLabel ? opts.getLabel(row) : null)
          || (row.querySelector('.row__title') || {}).textContent.trim()
          || 'this item';
        showConfirm(lbl, async function () {
          try {
            await opts.deleteItem(id);
            row.remove();
            if (opts.afterDelete) opts.afterDelete();
          } catch (err) {
            toast(formatError(err), { error: true });
          }
        });
        return;
      }

      // Tapping a card body in delete mode exits the mode without navigating.
      if (activeList === listEl && e.target.closest('.row[data-id]')) {
        e.preventDefault();
        exit();
      }
    }, true);
  }

  // Re-attach after htmx boost navigations. This file lives in <head> and runs
  // once; the registry and this listener survive any number of body swaps.
  document.addEventListener('htmx:afterSettle', function () {
    _registry.forEach(function (entry) {
      var el = entry.id ? document.getElementById(entry.id) : null;
      if (el && !el._lpdAttached) {
        _doAttach(el, entry.opts);
      }
    });
  });

  // ── public attach ────────────────────────────────────────────────────────

  function attach(listEl, opts) {
    if (!listEl) return;
    _registry.push({ id: listEl.id, opts: opts });
    _doAttach(listEl, opts);
  }

  window.LongPressDelete = { attach: attach, exit: exit };
}());
