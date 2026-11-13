import { lazy } from "react";

/** React.lazy that can be loaded ahead of time. Once preloaded, the page
 * renders synchronously: no Suspense fallback, so React's ~300 ms fallback
 * throttle never shows "Đang tải trang…" on a page whose code is ready. */
export function lazyWithPreload(factory) {
  let Loaded = null;
  let promise = null;
  const load = () => {
    promise ||= factory().then((module) => {
      Loaded = module.default;
      return module;
    });
    return promise;
  };
  const Lazy = lazy(load);
  function Preloadable(props) {
    return Loaded ? <Loaded {...props} /> : <Lazy {...props} />;
  }
  Preloadable.preload = () => load().catch(() => {});
  return Preloadable;
}
