import { useEffect } from "react";

/** The top bar already names the current page, so the first page heading of
 * every screen drops its eyebrow and title visually. The h1 stays in the DOM
 * (screen-reader only) and the description/actions stay visible. A request
 * detail header names the record itself, so it is never hidden. */
export function usePageTitleDedupe(active) {
  useEffect(() => {
    if (!active) return undefined;
    const mark = () => {
      const main = document.querySelector("main#main.content");
      if (!main) return;
      const first = main.querySelector(".page-heading:not(.ds-detail-header)");
      main.querySelectorAll(".page-heading.is-page-root").forEach((el) => {
        if (el !== first) el.classList.remove("is-page-root");
      });
      if (first && !first.classList.contains("is-page-root")) first.classList.add("is-page-root");
    };
    mark();
    const observer = new MutationObserver(mark);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [active]);
}
