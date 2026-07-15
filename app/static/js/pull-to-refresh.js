/**
 * Pull-to-refresh, since overscroll-behavior-y: none (added to stop
 * the fixed/sticky tab bar jittering on Android) also suppresses the
 * browser's own native pull-to-refresh gesture. Global, lives in
 * <head> like longpress-delete.js and page-init.js, works the same
 * on every page: reloads the whole document rather than trying to
 * re-fetch just the current page's data, since this app runs
 * entirely over a LAN where a full reload is already near-instant
 * (see the htmx-history-cache reasoning in base.html/CLAUDE.md).
 */
(function () {
  'use strict';

  var THRESHOLD_PX = 64;
  var MAX_PULL_PX = 110;

  var startY = null;
  var pulling = false;
  var released = false;
  var indicator = null;
  var icon = null;

  function ensureIndicator() {
    if (indicator) return indicator;
    indicator = document.createElement('div');
    indicator.className = 'ptr-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    icon = document.createElement('span');
    icon.className = 'ptr-indicator__icon';
    icon.innerHTML =
      '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" ' +
      'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M12 2v4"/><path d="m16.2 7.8 2.9-2.9"/><path d="M18 12h4"/>' +
      '<path d="m16.2 16.2 2.9 2.9"/><path d="M12 18v4"/><path d="m4.9 19.1 2.9-2.9"/>' +
      '<path d="M2 12h4"/><path d="m4.9 4.9 2.9 2.9"/></svg>';
    indicator.appendChild(icon);
    document.body.appendChild(indicator);
    return indicator;
  }

  // The icon-picker modal scrolls its own results grid internally, not the
  // document; a drag inside it shouldn't be read as a page-level pull.
  function insideOwnScroller(target) {
    return !!(target.closest && target.closest('.icon-picker-backdrop'));
  }

  function onTouchStart(e) {
    if (released) return;
    if (window.scrollY > 0) { startY = null; return; }
    if (e.touches.length !== 1 || insideOwnScroller(e.target)) { startY = null; return; }
    startY = e.touches[0].clientY;
    pulling = false;
  }

  function onTouchMove(e) {
    if (startY == null) return;
    var delta = e.touches[0].clientY - startY;
    if (delta <= 0) return;
    // Still at the top and being dragged down — this is a pull gesture,
    // not a normal scroll; take over from here.
    if (window.scrollY > 0) { startY = null; return; }

    pulling = true;
    e.preventDefault();

    var distance = Math.min(delta * 0.5, MAX_PULL_PX);
    var progress = Math.min(distance / THRESHOLD_PX, 1);

    var el = ensureIndicator();
    el.classList.add('is-visible');
    el.classList.toggle('is-loading', progress >= 1);
    el.style.transform = 'translate(-50%, ' + (48 + distance) + 'px)';
    icon.style.transform = 'rotate(' + progress * 180 + 'deg)';
  }

  function onTouchEnd() {
    if (!pulling) { startY = null; return; }
    pulling = false;

    var el = indicator;
    var wasAtThreshold = el && el.classList.contains('is-loading');
    startY = null;

    if (!el) return;

    if (wasAtThreshold) {
      released = true;
      el.style.transform = 'translate(-50%, ' + (48 + THRESHOLD_PX) + 'px)';
      location.reload();
      return;
    }

    el.classList.remove('is-visible', 'is-loading');
    el.style.transform = 'translate(-50%, -48px)';
    icon.style.transform = 'rotate(0deg)';
  }

  document.addEventListener('touchstart', onTouchStart, { passive: true });
  document.addEventListener('touchmove', onTouchMove, { passive: false });
  document.addEventListener('touchend', onTouchEnd, { passive: true });
  document.addEventListener('touchcancel', onTouchEnd, { passive: true });
}());
