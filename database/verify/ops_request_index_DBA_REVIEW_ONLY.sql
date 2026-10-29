-- DATN 2026-10-28: performance review for /api/v1/ops/requests.
-- Read only section. Execute from Supabase SQL editor to inspect current indexes.
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'eas' AND tablename = 'request'
ORDER BY indexname;

-- POTENTIAL index for the default ORDER BY r.updated_at DESC, r.id DESC
-- used by /api/v1/ops/requests; current schema indexes start with
-- requester_id or (status, type_id), which cannot always satisfy this order.
--
-- Do not run the statement below without DBA review and a representative
-- EXPLAIN (ANALYZE, BUFFERS) of the actual scoped query. Large tables can
-- incur maintenance / write overhead. Concurrent index creation must run
-- outside an explicit transaction block and requires suitable privileges.
--
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_request_ops_updated
--   ON eas.request (updated_at DESC, id DESC);
