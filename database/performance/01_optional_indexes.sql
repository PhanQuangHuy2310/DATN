-- OPTIONAL / DBA REVIEW: PostgreSQL indexes for request reports and inboxes.
-- Only deploy after examining production pg_indexes and EXPLAIN plans.
-- Apply with a direct psql connection, autocommit ON, outside BEGIN/COMMIT.
-- CREATE INDEX CONCURRENTLY requires transaction-pooling aware maintenance
-- and may be inappropriate for a very small or write-heavy database.
-- This file is never run automatically by Django or startup scripts.

-- Reporting WHERE requester_id=... AND created_at BETWEEN ... ; existing
-- request_owner_updated indexes updated_at, NOT the created_at predicate.
CREATE INDEX CONCURRENTLY IF NOT EXISTS eas_request_owner_created_perf
  ON eas.request (requester_id, created_at DESC)
  WHERE status <> 'DRAFT';

-- All-visible reporting scope by creation window (admin / auditor).
CREATE INDEX CONCURRENTLY IF NOT EXISTS eas_request_created_perf
  ON eas.request (created_at DESC)
  WHERE status <> 'DRAFT';

-- First submitted revision per request: MIN(submitted_at) in metrics query.
CREATE INDEX CONCURRENTLY IF NOT EXISTS eas_request_revision_first_submitted_perf
  ON eas.request_revision (request_id, submitted_at);

-- Paginated notifications ORDER BY created_at for one recipient (all reads).
-- Existing notification_inbox begins with (recipient_id, read_at), hence
-- cannot satisfy the date ordering for both read and unread items at once.
CREATE INDEX CONCURRENTLY IF NOT EXISTS eas_notification_recent_perf
  ON eas.notification (recipient_id, created_at DESC, id DESC);
