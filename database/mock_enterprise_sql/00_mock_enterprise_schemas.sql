-- EAS synthetic enterprise source systems 1.0.0
-- Precondition: EAS base installer has created role eas_migration and eas_api.
-- Intended for development/staging demonstrations; contains no production PII.

BEGIN;

CREATE SCHEMA mock_hr AUTHORIZATION eas_migration;
CREATE SCHEMA mock_assets AUTHORIZATION eas_migration;
CREATE SCHEMA mock_facilities AUTHORIZATION eas_migration;
CREATE SCHEMA mock_crm AUTHORIZATION eas_migration;
CREATE SCHEMA mock_procurement AUTHORIZATION eas_migration;
CREATE SCHEMA mock_it AUTHORIZATION eas_migration;
CREATE SCHEMA mock_finance AUTHORIZATION eas_migration;
CREATE SCHEMA mock_travel AUTHORIZATION eas_migration;

SET LOCAL ROLE eas_migration;

CREATE DOMAIN mock_hr.entity_status AS text
  CHECK (VALUE IN ('ACTIVE','INACTIVE'));

CREATE TABLE mock_hr.department (
  id uuid PRIMARY KEY,
  code varchar(30) NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_-]{2,30}$'),
  name varchar(160) NOT NULL,
  cost_center varchar(30) NOT NULL,
  parent_id uuid REFERENCES mock_hr.department(id),
  status mock_hr.entity_status NOT NULL DEFAULT 'ACTIVE',
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE TABLE mock_hr.employee (
  id uuid PRIMARY KEY,
  employee_code varchar(30) NOT NULL UNIQUE,
  display_name varchar(160) NOT NULL,
  work_email varchar(254) NOT NULL UNIQUE CHECK (work_email = lower(work_email)),
  department_id uuid NOT NULL REFERENCES mock_hr.department(id),
  manager_id uuid REFERENCES mock_hr.employee(id),
  job_title varchar(160) NOT NULL,
  employment_status text NOT NULL CHECK (employment_status IN ('ACTIVE','ON_LEAVE','OFFBOARDING','TERMINATED')),
  hired_on date NOT NULL,
  ended_on date,
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (manager_id IS NULL OR manager_id <> id),
  CHECK (ended_on IS NULL OR ended_on >= hired_on),
  CHECK ((employment_status = 'TERMINATED') = (ended_on IS NOT NULL))
);

CREATE TABLE mock_hr.leave_balance (
  id uuid PRIMARY KEY,
  employee_id uuid NOT NULL REFERENCES mock_hr.employee(id),
  leave_type text NOT NULL CHECK (leave_type IN ('ANNUAL','SICK','UNPAID','PARENTAL')),
  year smallint NOT NULL CHECK (year BETWEEN 2020 AND 2100),
  entitled_days numeric(6,2) NOT NULL CHECK (entitled_days >= 0),
  used_days numeric(6,2) NOT NULL DEFAULT 0 CHECK (used_days >= 0),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  UNIQUE (employee_id,leave_type,year),
  CHECK (used_days <= entitled_days OR leave_type = 'UNPAID')
);

CREATE TABLE mock_hr.schema_migration (
  version varchar(40) PRIMARY KEY,
  description varchar(200) NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE VIEW mock_hr.employee_directory WITH (security_barrier=true) AS
SELECT id,employee_code,display_name,work_email,department_id,manager_id,
       job_title,employment_status,updated_at
FROM mock_hr.employee;

CREATE TABLE mock_assets.asset_category (
  id uuid PRIMARY KEY,
  code varchar(30) NOT NULL UNIQUE,
  name varchar(120) NOT NULL,
  requires_approval boolean NOT NULL DEFAULT true,
  max_loan_days integer NOT NULL CHECK (max_loan_days BETWEEN 1 AND 365)
);

CREATE TABLE mock_assets.asset (
  id uuid PRIMARY KEY,
  asset_code varchar(40) NOT NULL UNIQUE,
  name varchar(160) NOT NULL,
  category_id uuid NOT NULL REFERENCES mock_assets.asset_category(id),
  serial_number varchar(120) UNIQUE,
  site_code varchar(30) NOT NULL,
  condition text NOT NULL CHECK (condition IN ('NEW','GOOD','FAIR','DAMAGED','RETIRED')),
  availability_status text NOT NULL CHECK (availability_status IN ('AVAILABLE','RESERVED','ON_LOAN','MAINTENANCE','RETIRED')),
  purchase_value_minor bigint CHECK (purchase_value_minor >= 0),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (condition <> 'RETIRED' OR availability_status = 'RETIRED')
);

CREATE TABLE mock_assets.asset_loan (
  id uuid PRIMARY KEY,
  asset_id uuid NOT NULL REFERENCES mock_assets.asset(id),
  borrower_employee_id uuid NOT NULL REFERENCES mock_hr.employee(id),
  source_request_id uuid,
  starts_at timestamptz NOT NULL,
  due_at timestamptz NOT NULL,
  returned_at timestamptz,
  status text NOT NULL CHECK (status IN ('RESERVED','ACTIVE','RETURNED','OVERDUE','CANCELLED')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (due_at > starts_at),
  CHECK (returned_at IS NULL OR returned_at >= starts_at),
  CHECK ((status = 'RETURNED') = (returned_at IS NOT NULL))
);
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
REVOKE ALL ON FUNCTION mock_assets.guard_loan_overlap() FROM PUBLIC;

CREATE VIEW mock_assets.asset_catalog WITH (security_barrier=true) AS
SELECT a.id,a.asset_code,a.name,c.code AS category_code,a.serial_number,
       a.site_code,a.condition,a.availability_status,a.updated_at
FROM mock_assets.asset a JOIN mock_assets.asset_category c ON c.id=a.category_id;

CREATE TABLE mock_facilities.site (
  id uuid PRIMARY KEY,
  site_code varchar(30) NOT NULL UNIQUE,
  name varchar(160) NOT NULL,
  timezone varchar(60) NOT NULL,
  status mock_hr.entity_status NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE mock_facilities.resource (
  id uuid PRIMARY KEY,
  resource_code varchar(40) NOT NULL UNIQUE,
  name varchar(160) NOT NULL,
  resource_type text NOT NULL CHECK (resource_type IN ('MEETING_ROOM','DESK','PARKING','VEHICLE')),
  site_id uuid NOT NULL REFERENCES mock_facilities.site(id),
  capacity integer NOT NULL DEFAULT 1 CHECK (capacity > 0),
  availability_status text NOT NULL CHECK (availability_status IN ('AVAILABLE','RESERVED','MAINTENANCE','INACTIVE')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE mock_facilities.reservation (
  id uuid PRIMARY KEY,
  resource_id uuid NOT NULL REFERENCES mock_facilities.resource(id),
  requester_employee_id uuid NOT NULL REFERENCES mock_hr.employee(id),
  source_request_id uuid,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('TENTATIVE','CONFIRMED','CHECKED_IN','COMPLETED','CANCELLED','NO_SHOW')),
  purpose varchar(300) NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (ends_at > starts_at)
);

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
REVOKE ALL ON FUNCTION mock_facilities.guard_reservation_overlap() FROM PUBLIC;

CREATE VIEW mock_facilities.resource_catalog WITH (security_barrier=true) AS
SELECT r.id,r.resource_code,r.name,r.resource_type,s.site_code,r.capacity,
       r.availability_status,r.updated_at
FROM mock_facilities.resource r JOIN mock_facilities.site s ON s.id=r.site_id;

CREATE TABLE mock_crm.customer (
  id uuid PRIMARY KEY,
  customer_code varchar(40) NOT NULL UNIQUE,
  legal_name varchar(200) NOT NULL,
  segment text NOT NULL CHECK (segment IN ('SMB','MID_MARKET','ENTERPRISE','PUBLIC_SECTOR')),
  account_status text NOT NULL CHECK (account_status IN ('PROSPECT','ACTIVE','SUSPENDED','CLOSED')),
  account_owner_employee_id uuid REFERENCES mock_hr.employee(id),
  tax_country char(2) NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE mock_crm.contract (
  id uuid PRIMARY KEY,
  contract_code varchar(40) NOT NULL UNIQUE,
  customer_id uuid NOT NULL REFERENCES mock_crm.customer(id),
  starts_on date NOT NULL,
  ends_on date NOT NULL,
  currency char(3) NOT NULL,
  value_minor bigint NOT NULL CHECK (value_minor >= 0),
  status text NOT NULL CHECK (status IN ('DRAFT','ACTIVE','EXPIRED','TERMINATED')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (ends_on >= starts_on)
);

CREATE TABLE mock_crm.support_case (
  id uuid PRIMARY KEY,
  case_code varchar(40) NOT NULL UNIQUE,
  customer_id uuid NOT NULL REFERENCES mock_crm.customer(id),
  priority text NOT NULL CHECK (priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  category text NOT NULL,
  status text NOT NULL CHECK (status IN ('OPEN','PENDING','RESOLVED','CLOSED')),
  owner_employee_id uuid REFERENCES mock_hr.employee(id),
  opened_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE VIEW mock_crm.customer_directory WITH (security_barrier=true) AS
SELECT id,customer_code,legal_name,segment,account_status,
       account_owner_employee_id,updated_at
FROM mock_crm.customer;

CREATE TABLE mock_procurement.supplier (
  id uuid PRIMARY KEY,
  supplier_code varchar(40) NOT NULL UNIQUE,
  legal_name varchar(200) NOT NULL,
  category varchar(80) NOT NULL,
  risk_rating text NOT NULL CHECK (risk_rating IN ('LOW','MEDIUM','HIGH')),
  status text NOT NULL CHECK (status IN ('PENDING_DUE_DILIGENCE','APPROVED','SUSPENDED','INACTIVE')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE mock_procurement.catalog_item (
  id uuid PRIMARY KEY,
  sku varchar(50) NOT NULL UNIQUE,
  name varchar(200) NOT NULL,
  category varchar(80) NOT NULL,
  supplier_id uuid NOT NULL REFERENCES mock_procurement.supplier(id),
  currency char(3) NOT NULL,
  unit_price_minor bigint NOT NULL CHECK (unit_price_minor >= 0),
  status text NOT NULL CHECK (status IN ('ACTIVE','OUT_OF_STOCK','DISCONTINUED')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE mock_procurement.purchase_order (
  id uuid PRIMARY KEY,
  po_code varchar(40) NOT NULL UNIQUE,
  supplier_id uuid NOT NULL REFERENCES mock_procurement.supplier(id),
  requester_employee_id uuid NOT NULL REFERENCES mock_hr.employee(id),
  source_request_id uuid,
  currency char(3) NOT NULL,
  total_minor bigint NOT NULL CHECK (total_minor >= 0),
  status text NOT NULL CHECK (status IN ('DRAFT','APPROVED','SENT','PARTIALLY_RECEIVED','RECEIVED','CANCELLED')),
  issued_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE VIEW mock_procurement.supplier_directory WITH (security_barrier=true) AS
SELECT id,supplier_code,legal_name,category,risk_rating,status,updated_at
FROM mock_procurement.supplier;

CREATE TABLE mock_it.application (
  id uuid PRIMARY KEY,
  app_code varchar(40) NOT NULL UNIQUE,
  name varchar(160) NOT NULL,
  data_classification text NOT NULL CHECK (data_classification IN ('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED')),
  owner_employee_id uuid NOT NULL REFERENCES mock_hr.employee(id),
  status mock_hr.entity_status NOT NULL DEFAULT 'ACTIVE',
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE mock_it.access_role (
  id uuid PRIMARY KEY,
  application_id uuid NOT NULL REFERENCES mock_it.application(id),
  role_code varchar(60) NOT NULL,
  name varchar(160) NOT NULL,
  risk_level text NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH','PRIVILEGED')),
  requires_sod_review boolean NOT NULL DEFAULT false,
  status mock_hr.entity_status NOT NULL DEFAULT 'ACTIVE',
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  UNIQUE (application_id,role_code)
);

CREATE TABLE mock_it.user_access (
  id uuid PRIMARY KEY,
  employee_id uuid NOT NULL REFERENCES mock_hr.employee(id),
  access_role_id uuid NOT NULL REFERENCES mock_it.access_role(id),
  source_request_id uuid,
  granted_at timestamptz NOT NULL,
  expires_at timestamptz,
  revoked_at timestamptz,
  status text NOT NULL CHECK (status IN ('ACTIVE','EXPIRED','REVOKED')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (expires_at IS NULL OR expires_at > granted_at),
  CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);
CREATE UNIQUE INDEX uq_user_active_access ON mock_it.user_access(employee_id,access_role_id)
  WHERE status='ACTIVE';

CREATE TABLE mock_it.service_catalog (
  id uuid PRIMARY KEY,
  service_code varchar(40) NOT NULL UNIQUE,
  name varchar(160) NOT NULL,
  category text NOT NULL CHECK (category IN ('ACCOUNT','HARDWARE','SOFTWARE','NETWORK','SECURITY','DATA')),
  default_priority text NOT NULL CHECK (default_priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  target_hours integer NOT NULL CHECK (target_hours BETWEEN 1 AND 720),
  status mock_hr.entity_status NOT NULL DEFAULT 'ACTIVE',
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE VIEW mock_it.application_catalog WITH (security_barrier=true) AS
SELECT id,app_code,name,data_classification,owner_employee_id,status,updated_at
FROM mock_it.application;

CREATE TABLE mock_finance.cost_center_budget (
  id uuid PRIMARY KEY,
  cost_center varchar(30) NOT NULL,
  fiscal_year smallint NOT NULL CHECK (fiscal_year BETWEEN 2020 AND 2100),
  currency char(3) NOT NULL,
  approved_minor bigint NOT NULL CHECK (approved_minor >= 0),
  committed_minor bigint NOT NULL DEFAULT 0 CHECK (committed_minor >= 0),
  spent_minor bigint NOT NULL DEFAULT 0 CHECK (spent_minor >= 0),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  UNIQUE (cost_center,fiscal_year,currency),
  CHECK (committed_minor + spent_minor <= approved_minor)
);

CREATE TABLE mock_finance.expense_category (
  id uuid PRIMARY KEY,
  category_code varchar(40) NOT NULL UNIQUE,
  name varchar(160) NOT NULL,
  receipt_required_above_minor bigint NOT NULL CHECK (receipt_required_above_minor >= 0),
  daily_limit_minor bigint CHECK (daily_limit_minor >= 0),
  currency char(3) NOT NULL,
  status mock_hr.entity_status NOT NULL DEFAULT 'ACTIVE',
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE mock_travel.travel_policy (
  id uuid PRIMARY KEY,
  employee_grade varchar(30) NOT NULL,
  travel_mode text NOT NULL CHECK (travel_mode IN ('AIR','RAIL','ROAD','HOTEL')),
  cabin_or_class varchar(40) NOT NULL,
  max_amount_minor bigint NOT NULL CHECK (max_amount_minor >= 0),
  currency char(3) NOT NULL,
  requires_quote_count smallint NOT NULL DEFAULT 1 CHECK (requires_quote_count BETWEEN 1 AND 5),
  status mock_hr.entity_status NOT NULL DEFAULT 'ACTIVE',
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  UNIQUE (employee_grade,travel_mode,currency)
);

CREATE TABLE mock_travel.travel_option (
  id uuid PRIMARY KEY,
  option_code varchar(40) NOT NULL UNIQUE,
  travel_mode text NOT NULL CHECK (travel_mode IN ('AIR','RAIL','ROAD','HOTEL')),
  origin varchar(100) NOT NULL,
  destination varchar(100) NOT NULL,
  departs_at timestamptz NOT NULL,
  arrives_at timestamptz NOT NULL,
  supplier_id uuid REFERENCES mock_procurement.supplier(id),
  currency char(3) NOT NULL,
  price_minor bigint NOT NULL CHECK (price_minor >= 0),
  refundable boolean NOT NULL DEFAULT false,
  availability_status text NOT NULL CHECK (availability_status IN ('AVAILABLE','LIMITED','SOLD_OUT','EXPIRED')),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (arrives_at > departs_at),
  CHECK (origin <> destination)
);

REVOKE ALL ON SCHEMA mock_hr,mock_assets,mock_facilities,mock_crm,mock_procurement,mock_it,mock_finance,mock_travel FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA mock_hr,mock_assets,mock_facilities,mock_crm,mock_procurement,mock_it,mock_finance,mock_travel FROM PUBLIC;
GRANT USAGE ON SCHEMA mock_hr,mock_assets,mock_facilities,mock_crm,mock_procurement,mock_it,mock_finance,mock_travel TO eas_api,eas_backup;
GRANT SELECT ON
  mock_hr.department,mock_hr.employee_directory,mock_hr.leave_balance,mock_hr.schema_migration,
  mock_assets.asset_catalog,mock_assets.asset_loan,
  mock_facilities.resource_catalog,
  mock_crm.customer_directory,mock_crm.contract,
  mock_procurement.supplier_directory,mock_procurement.catalog_item,
  mock_it.application_catalog,mock_it.access_role,mock_it.service_catalog,
  mock_finance.cost_center_budget,mock_finance.expense_category,
  mock_travel.travel_policy,mock_travel.travel_option
TO eas_api;
GRANT SELECT ON ALL TABLES IN SCHEMA mock_hr,mock_assets,mock_facilities,mock_crm,mock_procurement,mock_it,mock_finance,mock_travel TO eas_backup;

ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_hr REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_assets REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_facilities REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_crm REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_procurement REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_it REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_finance REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE eas_migration IN SCHEMA mock_travel REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

INSERT INTO mock_hr.schema_migration(version,description)
VALUES
  ('001','Temporal allocation integrity guards'),
  ('002','Least-privilege function defaults'),
  ('003','Runtime readiness contract grant');

COMMIT;
