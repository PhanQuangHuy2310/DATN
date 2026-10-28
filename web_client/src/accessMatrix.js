/** Visualize only explicitly assigned role/endpoint pairs in the read-only API contract.
 *  Aliases such as PARTICIPANT and AUTHENTICATED are intentionally not expanded
 *  into direct grants; actual access is evaluated by Django at request time.
 */
export function buildAccessMatrix(roleDefinitions = [], endpoints = []) {
  const roleKeys = new Set(roleDefinitions.map((role) => role.role));
  const documented = endpoints.filter((endpoint) =>
    (endpoint.roles || []).some((role) => roleKeys.has(role)));
  const domains = [...new Set(documented.map((endpoint) => endpoint.domain))];
  const rows = roleDefinitions.map((role) => ({
    ...role,
    cells: domains.map((domain) => {
      const matches = documented.filter((endpoint) => endpoint.domain === domain && (endpoint.roles || []).includes(role.role));
      const reads = matches.filter((endpoint) => endpoint.method === "GET").length;
      const writes = matches.length - reads;
      return {domain, role: role.role, reads, writes, count: matches.length,
        kind: reads && writes ? "both" : reads ? "read" : writes ? "write" : "none", endpoints: matches};
    }),
  }));
  return {domains, rows, documentedCount: documented.length};
}
