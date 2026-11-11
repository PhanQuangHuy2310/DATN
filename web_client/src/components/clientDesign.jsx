/** Shared visual building blocks for client workspaces. Business filters remain mounted
 * when folded, so the user never loses their selected criteria. */
import { Children, useId, useState } from "react";
import { PageHeader, StatCard } from "./design.jsx";

export const ClientPageHeader = PageHeader;
export const ClientStatCard = StatCard;

/** Display two everyday filters up front; less-used filters are one click away. */
export function ClientFilterSection({ children, footer, advanced = false, activeAdvancedCount = 0 }) {
  const [expanded, setExpanded] = useState(() => activeAdvancedCount > 0);
  const controlsId = useId();
  const fields = Children.toArray(children);
  const hasAdvanced = advanced && fields.length > 2;
  return (
    <section className="panel client-filter-toolbar ds-filter" aria-label="Bộ lọc">
      {hasAdvanced ? (
        <>
          <div className="client-filter-primary">
            <div className="client-filter-fields client-filter-essential">{fields.slice(0, 2)}</div>
            <button
              type="button"
              className="secondary client-filter-expand"
              aria-expanded={expanded}
              aria-controls={controlsId}
              onClick={() => setExpanded((value) => !value)}
            >
              <span aria-hidden="true">{expanded ? "−" : "+"}</span>
              {expanded ? "Thu gọn bộ lọc" : "Bộ lọc nâng cao"}
              {activeAdvancedCount > 0 && (
                <span className="client-filter-active-count" aria-label={`${activeAdvancedCount} bộ lọc đang áp dụng`}>
                  {activeAdvancedCount}
                </span>
              )}
            </button>
          </div>
          <div id={controlsId} className="client-filter-fields client-filter-advanced" hidden={!expanded}>
            {fields.slice(2)}
          </div>
        </>
      ) : (
        <div className="client-filter-fields">{children}</div>
      )}
      {footer && <div className="client-filter-footer">{footer}</div>}
    </section>
  );
}
