/**
 * Small inline SVG icons, shared across pages. Plain stroke-based
 * line icons, currentColor throughout so they inherit whatever color
 * their container sets. No icon font or external library: consistent
 * with this project's no-cloud-dependency stance, and it's a handful
 * of icons, not enough to justify a dependency.
 */

const ICONS = {
  moon: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"/><path d="M18 3v2M19 4h2"/></svg>',

  sun: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="14" r="4"/><path d="M12 4v2M5 7l1.5 1.5M19 7l-1.5 1.5M3 14h2M19 14h2"/></svg>',

  sunHorizon: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.5"/><path d="M3 17h18M5 9l1.2 1.2M19 9l-1.2 1.2"/></svg>',

  clock: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',

  bulb: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.4.3.6.8.6 1.3v.3h5.8v-.3c0-.5.2-1 .6-1.3A6 6 0 0 0 12 3Z"/></svg>',

  plus: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',

  chevronRight: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',

  calendar: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',

  devices: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',

  history: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></svg>',

  gear: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 13a7.6 7.6 0 0 0 0-2l2-1.5-2-3.4-2.3.9a7.6 7.6 0 0 0-1.7-1l-.4-2.5h-4l-.4 2.5a7.6 7.6 0 0 0-1.7 1l-2.3-.9-2 3.4L6.6 11a7.6 7.6 0 0 0 0 2l-2 1.5 2 3.4 2.3-.9c.5.4 1.1.7 1.7 1l.4 2.5h4l.4-2.5c.6-.3 1.2-.6 1.7-1l2.3.9 2-3.4-2-1.5Z"/></svg>',

  sparkle: '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6Z"/></svg>',

  pencil: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',

  close: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 5l14 14M19 5L5 19"/></svg>',

  globe: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18"/></svg>',

  bolt: '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"/></svg>',

  palette: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="8.5" cy="10.5" r="1.2" fill="currentColor"/><circle cx="12" cy="8" r="1.2" fill="currentColor"/><circle cx="15.5" cy="10.5" r="1.2" fill="currentColor"/><path d="M9 16a2 2 0 0 1 2-2h2a2 2 0 1 0 0-4"/></svg>',

  brightness: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M5 5l1.4 1.4M17.6 17.6 19 19M3 12h2M19 12h2M5 19l1.4-1.4M17.6 6.4 19 5"/></svg>',

  pin: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-7.5 7-12a7 7 0 1 0-14 0c0 4.5 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg>',

  chevronLeft: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>',

  wifi: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8.5a16 16 0 0 1 20 0M5.5 12a11 11 0 0 1 13 0M9 15.5a6 6 0 0 1 6 0"/><circle cx="12" cy="19" r="1" fill="currentColor" stroke="none"/></svg>',

  shieldCheck: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6Z"/><path d="M9 12l2 2 4-4"/></svg>',

  alertTriangle: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4 2.5 20h19Z"/><path d="M12 10v4M12 17h.01"/></svg>',

  skipForward: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5v14l9-7Z"/><path d="M18 5v14"/></svg>',

  crosshair: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="7"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>',

  trash: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-8 0 1 13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l1-13"/></svg>',

  info: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/></svg>',
};

/** Picks an icon + tint for a history entry, by execution status
 * rather than the schedule's trigger mood. Status (did it actually
 * work) is the more useful signal in a log of past actions. */
function historyIcon(status) {
  if (status === "success") return { icon: ICONS.bulb, className: "icon-avatar--sun" };
  if (status === "failed") return { icon: ICONS.alertTriangle, className: "icon-avatar--danger" };
  return { icon: ICONS.skipForward, className: "icon-avatar--moon" };
}

/** Picks an icon + avatar tint for a schedule, purely from real data
 * (trigger_type, and time-of-day for fixed-time schedules), not a
 * separate "mood" field that doesn't exist in the data model. */
function scheduleIcon(schedule) {
  if (schedule.trigger_type === "sunrise") {
    return { icon: ICONS.sun, className: "icon-avatar--sun" };
  }
  if (schedule.trigger_type === "sunset") {
    return { icon: ICONS.moon, className: "icon-avatar--moon" };
  }
  // trigger_type === "time": morning hours read as "sun", evening/night as "moon"
  const hour = schedule.time_of_day ? Number(schedule.time_of_day.split(":")[0]) : 12;
  const isEvening = hour < 5 || hour >= 18;
  return isEvening
    ? { icon: ICONS.moon, className: "icon-avatar--moon" }
    : { icon: ICONS.sun, className: "icon-avatar--sun" };
}
