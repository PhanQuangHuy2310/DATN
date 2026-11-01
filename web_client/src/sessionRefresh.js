/** Debounced /me refresh so new or revoked roles show without re-login.
 * Triggers: tab focus/visibility and the "eas:permissions-changed" event
 * (fired after the admin changes roles). Calls within `minIntervalMs` of the
 * previous refresh are merged into one. */
export const PERMISSIONS_CHANGED = "eas:permissions-changed";

export function createRefresher(refresh, { minIntervalMs = 5000, now = () => Date.now(), schedule = setTimeout, cancel = clearTimeout } = {}) {
  let last = -Infinity;
  let timer = null;
  const run = () => {
    timer = null;
    last = now();
    refresh();
  };
  return {
    trigger() {
      if (timer !== null) return;
      const wait = Math.max(0, last + minIntervalMs - now());
      if (wait === 0) run();
      else timer = schedule(run, wait);
    },
    dispose() {
      if (timer !== null) cancel(timer);
      timer = null;
    },
  };
}

export function notifyPermissionsChanged(target = globalThis) {
  target.dispatchEvent?.(new Event(PERMISSIONS_CHANGED));
}
