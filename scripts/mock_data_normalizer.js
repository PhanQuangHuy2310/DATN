/**
 * ============================================================================
 * Mock Data Normalizer — EAS (Enterprise Approval System)
 * ============================================================================
 *
 * MỤC ĐÍCH:
 *   Kéo dữ liệu từ 8 schema mock trong PostgreSQL, chuẩn hóa thành format
 *   JSON thống nhất để AI Service và API Core đọc được.
 *
 * TẠI SAO CẦN FILE NÀY:
 *   - Mỗi schema mock (mock_hr, mock_assets, ...) có cấu trúc bảng khác nhau
 *   - AI Service cần format chuẩn để train NLP classifier và risk model
 *   - API Core cần danh mục chuẩn hóa để render dropdown trong form
 *   - Tách biệt logic normalization ra khỏi application code
 *
 * CÁCH DÙNG:
 *   # Nguồn DB (mặc định) — cần DATABASE_URL và đã chạy 00_ + 01_ seed
 *   node scripts/mock_data_normalizer.js
 *   # Nguồn SQL offline — đọc trực tiếp 01_mock_seed_DEV_ONLY.sql, không cần DB
 *   node scripts/mock_data_normalizer.js --source sql
 *   # Tuỳ chọn khác
 *   node scripts/mock_data_normalizer.js --schema mock_hr --output ./out --format csv
 *
 * OUTPUT (mặc định: ai_service/data/mock/ — AI service đọc tại đây):
 *   ├── mock_hr.json
 *   ├── mock_assets.json
 *   ├── mock_facilities.json
 *   ├── mock_crm.json
 *   ├── mock_procurement.json
 *   ├── mock_it.json
 *   ├── mock_finance.json
 *   ├── mock_travel.json
 *   └── _manifest.json        (metadata tổng hợp)
 *
 * TẠI SAO OUTPUT ĐẶT Ở ai_service/data/mock/:
 *   - docker-compose mount thư mục này vào container ai-service (read-only)
 *   - AI service KHÔNG được cấp quyền DB (least privilege) → đọc snapshot JSON
 *   - Snapshot có version trong git → kết quả risk scoring tái lập được khi demo
 *
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..");
const DEFAULT_OUTPUT = path.join(REPO_ROOT, "ai_service", "data", "mock");
const DEFAULT_SEED = path.join(
  REPO_ROOT,
  "database",
  "mock_enterprise_sql",
  "01_mock_seed_DEV_ONLY.sql"
);
const NORMALIZER_VERSION = "2.1.0";

// ---------------------------------------------------------------------------
// Cấu hình kết nối — đọc từ biến môi trường hoặc dùng default dev
// ---------------------------------------------------------------------------
const DB_CONFIG = {
  connectionString:
    process.env.DATABASE_URL ||
    "postgresql://postgres:postgres@localhost:5432/postgres",
  ssl: process.env.DB_SSL === "true" ? { rejectUnauthorized: false } : false,
};

// ---------------------------------------------------------------------------
// 8 phòng ban (mock_hr.department.code) → nhãn department mà model AI đã train
// (RiskInput.department trong ai_service/routers/risk.py: it, hr, finance,
//  marketing, sales, operations, legal). HQ không có nhãn riêng → "operations".
// ---------------------------------------------------------------------------
const AI_DEPARTMENT_MAP = {
  HQ: "operations",
  IT: "it",
  SALES: "sales",
  OPS: "operations",
  FIN: "finance",
  HR: "hr",
  MKT: "marketing",
  LEGAL: "legal",
};

// ---------------------------------------------------------------------------
// SCHEMA REGISTRY — Đăng ký 8 schema mock và mapping bảng/entity
// ---------------------------------------------------------------------------
// Mỗi schema có:
//   - schema: tên schema trong PostgreSQL
//   - department: phòng ban phụ trách (mapping với eas.department)
//   - entities: danh sách bảng cần kéo + cách chuẩn hóa
//   - purpose: lý do tồn tại trong hệ thống EAS
// ---------------------------------------------------------------------------
const SCHEMA_REGISTRY = {
  mock_hr: {
    schema: "mock_hr",
    department: "HR",
    purpose:
      "Hệ thống HRIS — Quản lý nhân sự, phòng ban, ngày phép. " +
      "Schema nền tảng, tất cả schema khác tham chiếu employee_id từ đây.",
    entities: [
      {
        table: "department",
        pk: "id",
        fields: ["id", "code", "name", "cost_center", "parent_id", "status"],
        search_fields: ["code", "name"],
        normalize: (row) => ({
          id: row.id,
          code: row.code,
          label: row.name,
          cost_center: row.cost_center,
          parent_id: row.parent_id,
          ai_department: AI_DEPARTMENT_MAP[row.code] || "operations",
          is_active: row.status === "ACTIVE",
        }),
      },
      {
        // Dùng VIEW employee_directory thay vì bảng gốc (security barrier)
        table: "employee_directory",
        pk: "id",
        fields: [
          "id",
          "employee_code",
          "display_name",
          "work_email",
          "department_id",
          "manager_id",
          "job_title",
          "employment_status",
        ],
        search_fields: ["employee_code", "display_name", "work_email"],
        normalize: (row) => ({
          id: row.id,
          code: row.employee_code,
          label: row.display_name,
          email: row.work_email,
          department_id: row.department_id,
          manager_id: row.manager_id,
          job_title: row.job_title,
          status: row.employment_status,
          is_active: row.employment_status === "ACTIVE",
        }),
      },
      {
        table: "leave_balance",
        pk: "id",
        fields: [
          "id",
          "employee_id",
          "leave_type",
          "year",
          "entitled_days",
          "used_days",
        ],
        search_fields: ["leave_type"],
        normalize: (row) => ({
          id: row.id,
          employee_id: row.employee_id,
          type: row.leave_type,
          year: row.year,
          entitled: parseFloat(row.entitled_days),
          used: parseFloat(row.used_days),
          remaining: parseFloat(row.entitled_days) - parseFloat(row.used_days),
        }),
      },
    ],
  },

  mock_assets: {
    schema: "mock_assets",
    department: "OPS",
    purpose:
      "Hệ thống quản lý tài sản — Phục vụ yêu cầu EQUIPMENT (lifecycle C). " +
      "AI dùng availability_status và purchase_value để đánh giá risk.",
    entities: [
      {
        table: "asset_category",
        pk: "id",
        fields: [
          "id",
          "code",
          "name",
          "requires_approval",
          "max_loan_days",
        ],
        search_fields: ["code", "name"],
        normalize: (row) => ({
          id: row.id,
          code: row.code,
          label: row.name,
          requires_approval: row.requires_approval,
          max_loan_days: row.max_loan_days,
        }),
      },
      {
        // Dùng VIEW asset_catalog (join sẵn category)
        table: "asset_catalog",
        pk: "id",
        fields: [
          "id",
          "asset_code",
          "name",
          "category_code",
          "serial_number",
          "site_code",
          "condition",
          "availability_status",
        ],
        search_fields: ["asset_code", "name", "category_code"],
        normalize: (row) => ({
          id: row.id,
          code: row.asset_code,
          label: row.name,
          category: row.category_code,
          serial: row.serial_number,
          site: row.site_code,
          condition: row.condition,
          status: row.availability_status,
          is_available: row.availability_status === "AVAILABLE",
        }),
      },
      {
        table: "asset_loan",
        pk: "id",
        fields: [
          "id",
          "asset_id",
          "borrower_employee_id",
          "starts_at",
          "due_at",
          "returned_at",
          "status",
        ],
        search_fields: ["status"],
        normalize: (row) => ({
          id: row.id,
          asset_id: row.asset_id,
          borrower_id: row.borrower_employee_id,
          starts_at: row.starts_at,
          due_at: row.due_at,
          returned_at: row.returned_at,
          status: row.status,
          is_active: ["RESERVED", "ACTIVE", "OVERDUE"].includes(row.status),
        }),
      },
    ],
  },

  mock_facilities: {
    schema: "mock_facilities",
    department: "OPS",
    purpose:
      "Hệ thống đặt phòng họp & cơ sở vật chất — Phục vụ meeting_room, vehicle_booking. " +
      "AI dùng room_available để quyết định auto-approve.",
    entities: [
      {
        table: "site",
        pk: "id",
        fields: ["id", "site_code", "name", "timezone", "status"],
        search_fields: ["site_code", "name"],
        normalize: (row) => ({
          id: row.id,
          code: row.site_code,
          label: row.name,
          timezone: row.timezone,
          is_active: row.status === "ACTIVE",
        }),
      },
      {
        // Dùng VIEW resource_catalog
        table: "resource_catalog",
        pk: "id",
        fields: [
          "id",
          "resource_code",
          "name",
          "resource_type",
          "site_code",
          "capacity",
          "availability_status",
        ],
        search_fields: ["resource_code", "name", "resource_type"],
        normalize: (row) => ({
          id: row.id,
          code: row.resource_code,
          label: row.name,
          type: row.resource_type,
          site: row.site_code,
          capacity: row.capacity,
          status: row.availability_status,
          is_available: row.availability_status === "AVAILABLE",
        }),
      },
    ],
  },

  mock_crm: {
    schema: "mock_crm",
    department: "SALES",
    purpose:
      "Hệ thống CRM — Khách hàng, hợp đồng, support case. " +
      "AI risk scoring dùng contract value_minor để đánh giá amount_vs_limit.",
    entities: [
      {
        // Dùng VIEW customer_directory
        table: "customer_directory",
        pk: "id",
        fields: [
          "id",
          "customer_code",
          "legal_name",
          "segment",
          "account_status",
          "account_owner_employee_id",
        ],
        search_fields: ["customer_code", "legal_name", "segment"],
        normalize: (row) => ({
          id: row.id,
          code: row.customer_code,
          label: row.legal_name,
          segment: row.segment,
          status: row.account_status,
          owner_id: row.account_owner_employee_id,
          is_active: row.account_status === "ACTIVE",
        }),
      },
      {
        table: "contract",
        pk: "id",
        fields: [
          "id",
          "contract_code",
          "customer_id",
          "starts_on",
          "ends_on",
          "currency",
          "value_minor",
          "status",
        ],
        search_fields: ["contract_code", "status"],
        normalize: (row) => ({
          id: row.id,
          code: row.contract_code,
          customer_id: row.customer_id,
          period: { from: row.starts_on, to: row.ends_on },
          currency: row.currency,
          value_vnd: parseInt(row.value_minor) / 100, // minor → VND (đồng)
          status: row.status,
          is_active: row.status === "ACTIVE",
        }),
      },
    ],
  },

  mock_procurement: {
    schema: "mock_procurement",
    department: "OPS",
    purpose:
      "Hệ thống mua sắm — Nhà cung cấp, catalog sản phẩm, đơn mua hàng. " +
      "AI dùng unit_price_minor để đối chiếu amount trong risk scoring.",
    entities: [
      {
        // Dùng VIEW supplier_directory
        table: "supplier_directory",
        pk: "id",
        fields: [
          "id",
          "supplier_code",
          "legal_name",
          "category",
          "risk_rating",
          "status",
        ],
        search_fields: ["supplier_code", "legal_name", "category"],
        normalize: (row) => ({
          id: row.id,
          code: row.supplier_code,
          label: row.legal_name,
          category: row.category,
          risk: row.risk_rating,
          status: row.status,
          is_approved: row.status === "APPROVED",
        }),
      },
      {
        table: "catalog_item",
        pk: "id",
        fields: [
          "id",
          "sku",
          "name",
          "category",
          "supplier_id",
          "currency",
          "unit_price_minor",
          "status",
        ],
        search_fields: ["sku", "name", "category"],
        normalize: (row) => ({
          id: row.id,
          sku: row.sku,
          label: row.name,
          category: row.category,
          supplier_id: row.supplier_id,
          currency: row.currency,
          price_vnd: parseInt(row.unit_price_minor) / 100,
          status: row.status,
          is_available: row.status === "ACTIVE",
        }),
      },
    ],
  },

  mock_it: {
    schema: "mock_it",
    department: "IT",
    purpose:
      "Hệ thống IAM/ITSM — Ứng dụng, quyền truy cập, service catalog. " +
      "AI dùng risk_level, data_classification để tính risk cho đơn access_permission (lifecycle B).",
    entities: [
      {
        // Dùng VIEW application_catalog
        table: "application_catalog",
        pk: "id",
        fields: [
          "id",
          "app_code",
          "name",
          "data_classification",
          "owner_employee_id",
          "status",
        ],
        search_fields: ["app_code", "name", "data_classification"],
        normalize: (row) => ({
          id: row.id,
          code: row.app_code,
          label: row.name,
          classification: row.data_classification,
          owner_id: row.owner_employee_id,
          is_active: row.status === "ACTIVE",
          // AI dùng classification để tính risk: RESTRICTED > CONFIDENTIAL > INTERNAL > PUBLIC
          risk_weight: { RESTRICTED: 4, CONFIDENTIAL: 3, INTERNAL: 2, PUBLIC: 1 }[
            row.data_classification
          ] || 1,
        }),
      },
      {
        table: "access_role",
        pk: "id",
        fields: [
          "id",
          "application_id",
          "role_code",
          "name",
          "risk_level",
          "requires_sod_review",
          "status",
        ],
        search_fields: ["role_code", "name", "risk_level"],
        normalize: (row) => ({
          id: row.id,
          app_id: row.application_id,
          code: row.role_code,
          label: row.name,
          risk_level: row.risk_level,
          needs_sod: row.requires_sod_review,
          is_active: row.status === "ACTIVE",
          // AI dùng risk_level để tính risk: PRIVILEGED > HIGH > MEDIUM > LOW
          risk_weight: { PRIVILEGED: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }[
            row.risk_level
          ] || 1,
        }),
      },
      {
        table: "service_catalog",
        pk: "id",
        fields: [
          "id",
          "service_code",
          "name",
          "category",
          "default_priority",
          "target_hours",
          "status",
        ],
        search_fields: ["service_code", "name", "category"],
        normalize: (row) => ({
          id: row.id,
          code: row.service_code,
          label: row.name,
          category: row.category,
          priority: row.default_priority,
          sla_hours: row.target_hours,
          is_active: row.status === "ACTIVE",
        }),
      },
    ],
  },

  mock_finance: {
    schema: "mock_finance",
    department: "FIN",
    purpose:
      "Hệ thống tài chính — Ngân sách cost center, loại chi phí. " +
      "AI dùng budget remaining để đánh giá risk khi amount vượt ngân sách.",
    entities: [
      {
        table: "cost_center_budget",
        pk: "id",
        fields: [
          "id",
          "cost_center",
          "fiscal_year",
          "currency",
          "approved_minor",
          "committed_minor",
          "spent_minor",
        ],
        search_fields: ["cost_center", "currency"],
        normalize: (row) => ({
          id: row.id,
          cost_center: row.cost_center,
          year: row.fiscal_year,
          currency: row.currency,
          approved_vnd: parseInt(row.approved_minor) / 100,
          committed_vnd: parseInt(row.committed_minor) / 100,
          spent_vnd: parseInt(row.spent_minor) / 100,
          remaining_vnd:
            (parseInt(row.approved_minor) -
              parseInt(row.committed_minor) -
              parseInt(row.spent_minor)) /
            100,
          utilization_pct: (
            ((parseInt(row.committed_minor) + parseInt(row.spent_minor)) /
              parseInt(row.approved_minor)) *
            100
          ).toFixed(1),
        }),
      },
      {
        table: "expense_category",
        pk: "id",
        fields: [
          "id",
          "category_code",
          "name",
          "receipt_required_above_minor",
          "daily_limit_minor",
          "currency",
          "status",
        ],
        search_fields: ["category_code", "name"],
        normalize: (row) => ({
          id: row.id,
          code: row.category_code,
          label: row.name,
          receipt_threshold_vnd:
            parseInt(row.receipt_required_above_minor) / 100,
          daily_limit_vnd: row.daily_limit_minor
            ? parseInt(row.daily_limit_minor) / 100
            : null,
          currency: row.currency,
          is_active: row.status === "ACTIVE",
        }),
      },
    ],
  },

  mock_travel: {
    schema: "mock_travel",
    department: "HR",
    purpose:
      "Hệ thống quản lý công tác — Chính sách đi lại, lựa chọn chuyến. " +
      "AI dùng max_amount_minor để kiểm tra amount_vs_limit_ratio.",
    entities: [
      {
        table: "travel_policy",
        pk: "id",
        fields: [
          "id",
          "employee_grade",
          "travel_mode",
          "cabin_or_class",
          "max_amount_minor",
          "currency",
          "requires_quote_count",
          "status",
        ],
        search_fields: ["employee_grade", "travel_mode"],
        normalize: (row) => ({
          id: row.id,
          grade: row.employee_grade,
          mode: row.travel_mode,
          class: row.cabin_or_class,
          max_amount_vnd: parseInt(row.max_amount_minor) / 100,
          currency: row.currency,
          min_quotes: row.requires_quote_count,
          is_active: row.status === "ACTIVE",
        }),
      },
      {
        table: "travel_option",
        pk: "id",
        fields: [
          "id",
          "option_code",
          "travel_mode",
          "origin",
          "destination",
          "departs_at",
          "arrives_at",
          "currency",
          "price_minor",
          "refundable",
          "availability_status",
        ],
        search_fields: ["option_code", "travel_mode", "origin", "destination"],
        normalize: (row) => ({
          id: row.id,
          code: row.option_code,
          mode: row.travel_mode,
          route: `${row.origin} → ${row.destination}`,
          origin: row.origin,
          destination: row.destination,
          departs: row.departs_at,
          arrives: row.arrives_at,
          price_vnd: parseInt(row.price_minor) / 100,
          currency: row.currency,
          refundable: row.refundable,
          status: row.availability_status,
          is_bookable: ["AVAILABLE", "LIMITED"].includes(
            row.availability_status
          ),
        }),
      },
    ],
  },
};

// ---------------------------------------------------------------------------
// NGUỒN DỮ LIỆU 1: PostgreSQL (mặc định)
// ---------------------------------------------------------------------------
async function createDbSource() {
  // Lazy require: chế độ --source sql không cần cài `pg`
  const { Client, types } = require("pg");
  // DATE (OID 1082) giữ nguyên chuỗi 'YYYY-MM-DD' — tránh lệch ngày do timezone
  types.setTypeParser(1082, (v) => v);

  const client = new Client(DB_CONFIG);
  await client.connect();
  console.log("✓ Kết nối PostgreSQL thành công");

  return {
    label: DB_CONFIG.connectionString.replace(/:[^:@/]+@/, ":***@"),
    async fetch(schemaName, entity) {
      const sql = `SELECT ${entity.fields.join(", ")} FROM ${schemaName}.${entity.table} ORDER BY ${entity.pk}`;
      const result = await client.query(sql);
      return result.rows;
    },
    close: () => client.end(),
  };
}

// ---------------------------------------------------------------------------
// NGUỒN DỮ LIỆU 2: File seed SQL (offline, không cần DB)
// ---------------------------------------------------------------------------
// Parse các câu `INSERT INTO schema.table(cols) VALUES (...),(...);`
// và giả lập các VIEW security_barrier định nghĩa trong 00_mock_enterprise_schemas.sql.
// ---------------------------------------------------------------------------

/** Các bảng có cột status DEFAULT 'ACTIVE' (domain mock_hr.entity_status) */
const STATUS_DEFAULT_TABLES = new Set([
  "mock_hr.department",
  "mock_facilities.site",
  "mock_it.application",
  "mock_it.access_role",
  "mock_it.service_catalog",
  "mock_finance.expense_category",
  "mock_travel.travel_policy",
]);

function stripSqlComments(sql) {
  let out = "";
  let inStr = false;
  for (let i = 0; i < sql.length; i++) {
    const ch = sql[i];
    if (inStr) {
      out += ch;
      if (ch === "'") {
        if (sql[i + 1] === "'") {
          out += sql[++i];
        } else {
          inStr = false;
        }
      }
    } else if (ch === "'") {
      inStr = true;
      out += ch;
    } else if (ch === "-" && sql[i + 1] === "-") {
      while (i < sql.length && sql[i] !== "\n") i++;
      out += "\n";
    } else {
      out += ch;
    }
  }
  return out;
}

/** Chuyển literal SQL → giá trị JS */
function parseLiteral(token) {
  const t = token.trim();
  if (/^null$/i.test(t)) return null;
  if (/^true$/i.test(t)) return true;
  if (/^false$/i.test(t)) return false;
  if (t.startsWith("'")) return t.slice(1, -1).replace(/''/g, "'");
  if (/^-?\d+(\.\d+)?$/.test(t)) return t; // giữ dạng chuỗi như pg (bigint/numeric)
  throw new Error(`Literal không hỗ trợ: ${t}`);
}

/** Tách phần VALUES thành danh sách tuple, mỗi tuple là mảng token */
function parseTuples(valuesSql) {
  const tuples = [];
  let depth = 0;
  let inStr = false;
  let token = "";
  let current = null;
  for (let i = 0; i < valuesSql.length; i++) {
    const ch = valuesSql[i];
    if (inStr) {
      token += ch;
      if (ch === "'") {
        if (valuesSql[i + 1] === "'") token += valuesSql[++i];
        else inStr = false;
      }
      continue;
    }
    if (ch === "'") {
      inStr = true;
      token += ch;
    } else if (ch === "(") {
      depth++;
      if (depth === 1) {
        current = [];
        token = "";
      } else token += ch;
    } else if (ch === ")") {
      depth--;
      if (depth === 0) {
        current.push(parseLiteral(token));
        tuples.push(current);
        current = null;
        token = "";
      } else token += ch;
    } else if (ch === "," && depth === 1) {
      current.push(parseLiteral(token));
      token = "";
    } else if (depth >= 1) {
      token += ch;
    }
  }
  return tuples;
}

function parseSeedFile(seedPath) {
  const sql = stripSqlComments(fs.readFileSync(seedPath, "utf-8"));
  const tables = {};
  const re = /INSERT\s+INTO\s+([a-z_]+)\.([a-z_]+)\s*\(([^)]*)\)\s*VALUES/gi;
  let match;
  while ((match = re.exec(sql)) !== null) {
    const key = `${match[1]}.${match[2]}`;
    const cols = match[3].split(",").map((c) => c.trim());
    // Tìm dấu ; kết thúc câu lệnh (ngoài chuỗi)
    let end = re.lastIndex;
    let inStr = false;
    for (; end < sql.length; end++) {
      const ch = sql[end];
      if (ch === "'") {
        if (inStr && sql[end + 1] === "'") end++;
        else inStr = !inStr;
      } else if (ch === ";" && !inStr) break;
    }
    const rows = parseTuples(sql.slice(re.lastIndex, end)).map((vals) => {
      if (vals.length !== cols.length) {
        throw new Error(`${key}: số cột (${cols.length}) ≠ số giá trị (${vals.length})`);
      }
      const row = Object.fromEntries(cols.map((c, i) => [c, vals[i]]));
      if (STATUS_DEFAULT_TABLES.has(key) && row.status === undefined) row.status = "ACTIVE";
      return row;
    });
    tables[key] = (tables[key] || []).concat(rows);
    re.lastIndex = end;
  }
  return tables;
}

/** Giả lập VIEW giống hệt định nghĩa trong 00_mock_enterprise_schemas.sql */
function buildViews(t) {
  const byId = (key) => Object.fromEntries((t[key] || []).map((r) => [r.id, r]));
  const categories = byId("mock_assets.asset_category");
  const sites = byId("mock_facilities.site");
  return {
    "mock_hr.employee_directory": t["mock_hr.employee"] || [],
    "mock_assets.asset_catalog": (t["mock_assets.asset"] || []).map((a) => ({
      ...a,
      category_code: categories[a.category_id]?.code ?? null,
    })),
    "mock_facilities.resource_catalog": (t["mock_facilities.resource"] || []).map((r) => ({
      ...r,
      site_code: sites[r.site_id]?.site_code ?? null,
    })),
    "mock_crm.customer_directory": t["mock_crm.customer"] || [],
    "mock_procurement.supplier_directory": t["mock_procurement.supplier"] || [],
    "mock_it.application_catalog": t["mock_it.application"] || [],
  };
}

function createSqlSource(seedPath) {
  const tables = parseSeedFile(seedPath);
  const all = { ...tables, ...buildViews(tables) };
  console.log(`✓ Đã parse seed: ${path.relative(REPO_ROOT, seedPath)} (${Object.keys(tables).length} bảng)`);
  return {
    label: `sql:${path.relative(REPO_ROOT, seedPath).replace(/\\/g, "/")}`,
    async fetch(schemaName, entity) {
      const rows = all[`${schemaName}.${entity.table}`] || [];
      // Chỉ giữ các cột khai báo (giống SELECT), cột thiếu → null
      return rows
        .map((r) => Object.fromEntries(entity.fields.map((f) => [f, r[f] ?? null])))
        .sort((a, b) => String(a[entity.pk]).localeCompare(String(b[entity.pk])));
    },
    close: async () => {},
  };
}

// ---------------------------------------------------------------------------
// Core Functions
// ---------------------------------------------------------------------------

/**
 * Kéo dữ liệu từ 1 entity (bảng/view) và chuẩn hóa
 */
async function fetchEntity(source, schemaName, entity) {
  try {
    const rows = await source.fetch(schemaName, entity);
    return {
      table: entity.table,
      raw_count: rows.length,
      search_fields: entity.search_fields,
      data: rows.map(entity.normalize),
    };
  } catch (err) {
    console.error(`  ✗ Lỗi khi kéo ${schemaName}.${entity.table}: ${err.message}`);
    return {
      table: entity.table,
      raw_count: 0,
      search_fields: entity.search_fields,
      data: [],
      error: err.message,
    };
  }
}

/**
 * Kéo và chuẩn hóa toàn bộ 1 schema
 */
async function normalizeSchema(source, schemaKey) {
  const config = SCHEMA_REGISTRY[schemaKey];
  if (!config) {
    throw new Error(
      `Schema không tồn tại: ${schemaKey}. Hợp lệ: ${Object.keys(SCHEMA_REGISTRY).join(", ")}`
    );
  }

  console.log(`\n📦 ${schemaKey} (${config.department}) — ${config.purpose.split(" — ")[0]}`);

  const entities = {};
  let totalRecords = 0;
  let errors = 0;

  for (const entity of config.entities) {
    const result = await fetchEntity(source, config.schema, entity);
    entities[entity.table] = result;
    totalRecords += result.raw_count;
    if (result.error) errors++;
    console.log(`  ${result.error ? "✗" : "✓"} ${entity.table}: ${result.raw_count} bản ghi`);
  }

  return {
    schema: config.schema,
    department: config.department,
    purpose: config.purpose,
    entities,
    meta: {
      total_records: totalRecords,
      entity_count: config.entities.length,
      error_count: errors,
      source: source.label,
      normalizer_version: NORMALIZER_VERSION,
    },
  };
}

/**
 * Xuất dữ liệu chuẩn hóa ra file
 */
function writeOutput(data, outputDir, format = "json") {
  fs.mkdirSync(outputDir, { recursive: true });

  if (format === "csv") {
    for (const [entityName, entityData] of Object.entries(data.entities)) {
      if (entityData.data.length === 0) continue;
      const csvPath = path.join(outputDir, `${data.schema}_${entityName}.csv`);
      const headers = Object.keys(entityData.data[0]);
      const rows = entityData.data.map((row) =>
        headers
          .map((h) => {
            const v = row[h];
            return typeof v === "object" && v !== null ? JSON.stringify(JSON.stringify(v)) : JSON.stringify(v ?? "");
          })
          .join(",")
      );
      fs.writeFileSync(csvPath, [headers.join(","), ...rows].join("\n") + "\n", "utf-8");
      console.log(`  📄 ${path.relative(REPO_ROOT, csvPath)}`);
    }
    return;
  }

  const filePath = path.join(outputDir, `${data.schema}.json`);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + "\n", "utf-8");
  console.log(`  💾 ${path.relative(REPO_ROOT, filePath)}`);
}

// ---------------------------------------------------------------------------
// CLI Entry Point
// ---------------------------------------------------------------------------
async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help") || args.includes("-h")) {
    console.log(`
Cách dùng:
  node scripts/mock_data_normalizer.js [tuỳ chọn]

Tuỳ chọn:
  --source <db|sql>     Nguồn dữ liệu: 'db' (PostgreSQL) hoặc 'sql' (offline seed) [mặc định: auto]
  --schema <tên>        Chỉ chạy cho 1 schema (vd: mock_hr, mock_finance)
  --output <đường_dẫn>  Thư mục xuất file [mặc định: ai_service/data/mock]
  --seed <đường_dẫn>    Đường dẫn file seed SQL nếu dùng --source sql
  --format <json|csv>   Định dạng file xuất [mặc định: json]
  --help, -h            Hiện hướng dẫn này
`);
    return;
  }

  const outputDir = path.resolve(getArg(args, "--output") || DEFAULT_OUTPUT);
  const schemaFilter = getArg(args, "--schema");
  const format = getArg(args, "--format") || "json";
  let sourceType = getArg(args, "--source");
  const seedPath = path.resolve(getArg(args, "--seed") || DEFAULT_SEED);

  if (!sourceType) {
    try {
      require.resolve("pg");
      sourceType = "db";
    } catch {
      console.log("ℹ️  Chưa cài module 'pg' — tự động chuyển sang nguồn SQL offline (--source sql)\n");
      sourceType = "sql";
    }
  }

  if (!["json", "csv"].includes(format)) throw new Error(`--format không hợp lệ: ${format}`);
  if (!["db", "sql"].includes(sourceType)) throw new Error(`--source không hợp lệ: ${sourceType}`);

  console.log("═══════════════════════════════════════════════════════════");
  console.log(` EAS Mock Data Normalizer v${NORMALIZER_VERSION} — nguồn: ${sourceType}`);
  console.log("═══════════════════════════════════════════════════════════");

  const source = sourceType === "sql" ? createSqlSource(seedPath) : await createDbSource();
  let failed = false;

  try {
    const schemas = schemaFilter ? [schemaFilter] : Object.keys(SCHEMA_REGISTRY);
    const manifest = {
      generator: `scripts/mock_data_normalizer.js v${NORMALIZER_VERSION}`,
      source: source.label,
      generated_at: new Date().toISOString(),
      ai_department_map: AI_DEPARTMENT_MAP,
      schemas: {},
    };

    for (const schemaKey of schemas) {
      const data = await normalizeSchema(source, schemaKey);
      writeOutput(data, outputDir, format);
      if (data.meta.error_count > 0) failed = true;
      manifest.schemas[schemaKey] = {
        department: data.department,
        total_records: data.meta.total_records,
        entities: Object.fromEntries(
          Object.entries(data.entities).map(([k, v]) => [k, v.raw_count])
        ),
        purpose: data.purpose,
      };
    }

    if (format === "json") {
      const manifestPath = path.join(outputDir, "_manifest.json");
      fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf-8");
      console.log(`\n📋 ${path.relative(REPO_ROOT, manifestPath)}`);
    }

    const totalRecords = Object.values(manifest.schemas).reduce((s, x) => s + x.total_records, 0);
    console.log("\n═══════════════════════════════════════════════════════════");
    console.log(` ${failed ? "⚠️  Có lỗi" : "✅ Hoàn tất"}: ${schemas.length} schema, ${totalRecords} bản ghi`);
    console.log("═══════════════════════════════════════════════════════════");
  } finally {
    await source.close();
  }
  if (failed) process.exitCode = 1;
}

function getArg(args, flag) {
  const idx = args.indexOf(flag);
  return idx !== -1 && idx + 1 < args.length ? args[idx + 1] : null;
}

if (require.main === module) {
  main().catch((err) => {
    console.error(`\n❌ Lỗi: ${err.message}`);
    process.exit(1);
  });
}

module.exports = { SCHEMA_REGISTRY, AI_DEPARTMENT_MAP, parseSeedFile, normalizeSchema, createSqlSource };
