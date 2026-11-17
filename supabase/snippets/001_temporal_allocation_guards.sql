-- Upgrade 1.0.0 -> 1.1.0. Apply once as project postgres/migration administrator.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SET LOCAL ROLE eas_migration;

CREATE TABLE mock_hr.schema_migration (
  version varchar(40) PRIMARY KEY,
  description varchar(200) NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

DROP INDEX mock_assets.uq_asset_open_loan;
CREATE INDEX ix_asset_loan_window ON mock_assets.asset_loan(asset_id,starts_at,due_at)
  WHERE status IN ('RESERVED','ACTIVE','OVERDUE');

CREATE FUNCTION mock_assets.guard_loan_overlap() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,mock_assets AS $$
BEGIN
  IF NEW.status IN ('RESERVED','ACTIVE','OVERDUE') THEN
    PERFORM 1 FROM mock_assets.asset WHERE id=NEW.asset_id FOR UPDATE;
    IF EXISTS (
      SELECT 1 FROM mock_assets.asset_loan l
      WHERE l.asset_id=NEW.asset_id AND l.id<>NEW.id
        AND l.status IN ('RESERVED','ACTIVE','OVERDUE')
        AND tstzrange(l.starts_at,l.due_at,'[)') && tstzrange(NEW.starts_at,NEW.due_at,'[)')
    ) THEN
      RAISE EXCEPTION USING ERRCODE='23P01',MESSAGE='asset loan overlaps existing allocation';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_asset_loan_overlap BEFORE INSERT OR UPDATE OF asset_id,starts_at,due_at,status
ON mock_assets.asset_loan FOR EACH ROW EXECUTE FUNCTION mock_assets.guard_loan_overlap();

CREATE INDEX ix_reservation_window ON mock_facilities.reservation(resource_id,starts_at,ends_at)
  WHERE status IN ('TENTATIVE','CONFIRMED','CHECKED_IN');
CREATE FUNCTION mock_facilities.guard_reservation_overlap() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,mock_facilities AS $$
BEGIN
  IF NEW.status IN ('TENTATIVE','CONFIRMED','CHECKED_IN') THEN
    PERFORM 1 FROM mock_facilities.resource WHERE id=NEW.resource_id FOR UPDATE;
    IF EXISTS (
      SELECT 1 FROM mock_facilities.reservation r
      WHERE r.resource_id=NEW.resource_id AND r.id<>NEW.id
        AND r.status IN ('TENTATIVE','CONFIRMED','CHECKED_IN')
        AND tstzrange(r.starts_at,r.ends_at,'[)') && tstzrange(NEW.starts_at,NEW.ends_at,'[)')
    ) THEN
      RAISE EXCEPTION USING ERRCODE='23P01',MESSAGE='facility reservation overlaps existing allocation';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_facility_reservation_overlap BEFORE INSERT OR UPDATE OF resource_id,starts_at,ends_at,status
ON mock_facilities.reservation FOR EACH ROW EXECUTE FUNCTION mock_facilities.guard_reservation_overlap();

INSERT INTO mock_hr.schema_migration(version,description)
VALUES ('001','Temporal allocation integrity guards');
COMMIT;
