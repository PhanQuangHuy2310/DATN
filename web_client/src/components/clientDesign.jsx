/** Shared Web Client primitives: one hierarchy for all role-scoped pages. */
export function ClientPageHeader({ eyebrow, title, description, action }) {
  return <div className="page-heading client-page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{description && <p className="muted">{description}</p>}</div>{action}</div>;
}
export function ClientStatCard({ title, value, detail }) {
  return <article className="panel client-metric"><span>{title}</span><strong>{value}</strong><small>{detail}</small></article>;
}
export function ClientFilterSection({ children, footer }) {
  return <section className="panel client-filter-toolbar" aria-label="Bộ lọc yêu cầu"><div className="client-filter-fields">{children}</div><div className="client-filter-footer">{footer}</div></section>;
}
