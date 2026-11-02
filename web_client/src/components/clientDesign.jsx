/** Back-compat names for the shared design-system primitives (components/design.jsx). */
import { PageHeader, StatCard } from "./design.jsx";

export const ClientPageHeader = PageHeader;
export const ClientStatCard = StatCard;
export function ClientFilterSection({ children, footer }) {
  return <section className="panel client-filter-toolbar ds-filter" aria-label="Bộ lọc"><div className="client-filter-fields">{children}</div><div className="client-filter-footer">{footer}</div></section>;
}
