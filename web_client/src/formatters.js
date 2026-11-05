/**
 * Enterprise Vietnamese formatting utilities for EAS Web Client:
 * - VND currency formatting with dot separators & Vietnamese financial words
 * - Business enum, boolean, ISO date/datetime, and UUID user resolution
 * - Zero raw JSON / snake_case SQL leakage
 */

const CURRENCY_EXACT_KEYS = new Set([
  "amount_vnd",
  "amount",
  "estimated_budget",
  "estimated_price",
  "estimated_cost",
  "refund_amount",
  "max_budget",
  "contract_value",
  "deal_value_vnd",
  "salary_budget_vnd",
  "residual_value_vnd",
  "daily_limit_minor",
  "amount_minor",
  "total_amount",
  "unit_price",
  "advance_amount",
  "reimbursement_amount",
]);

export function isCurrencyField(name) {
  if (!name) return false;
  const key = String(name).toLowerCase();
  if (CURRENCY_EXACT_KEYS.has(key)) return true;
  return (
    key.endsWith("_vnd") ||
    key.endsWith("_budget") ||
    key.endsWith("_price") ||
    key.endsWith("_cost") ||
    key.endsWith("_amount")
  );
}

export function parseDigits(raw) {
  if (raw === null || raw === undefined) return "";
  const str = String(raw).trim();
  if (!str) return "";
  // Handle numeric float strings like "50000000.0" safely
  if (/^\d+(\.0+)?$/.test(str)) {
    return str.split(".")[0];
  }
  return str.replace(/\D+/g, "");
}

export function formatThousandDots(raw) {
  const digits = parseDigits(raw).replace(/^0+(?=\d)/, "");
  if (!digits) return "";
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function formatVnd(value) {
  if (value === null || value === undefined || value === "") return "—";
  const num = typeof value === "number" ? Math.round(value) : Number(parseDigits(value));
  if (!Number.isFinite(num)) return String(value);
  return `${num.toLocaleString("vi-VN")} ₫`;
}

const DIGITS_VI = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"];
const SCALES_VI = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"];

function readThreeDigits(hundreds, tens, units, readZeroHundred) {
  const parts = [];
  if (hundreds > 0 || readZeroHundred) {
    parts.push(`${DIGITS_VI[hundreds]} trăm`);
  }
  if (tens > 1) {
    parts.push(`${DIGITS_VI[tens]} mươi`);
    if (units === 1) parts.push("mốt");
    else if (units === 4) parts.push("tư");
    else if (units === 5) parts.push("lăm");
    else if (units > 0) parts.push(DIGITS_VI[units]);
  } else if (tens === 1) {
    parts.push("mười");
    if (units === 5) parts.push("lăm");
    else if (units > 0) parts.push(DIGITS_VI[units]);
  } else if (tens === 0 && units > 0) {
    if (hundreds > 0 || readZeroHundred) {
      parts.push("lẻ");
    }
    parts.push(DIGITS_VI[units]);
  }
  return parts.join(" ");
}

/**
 * Convert integer VND amount into standard Vietnamese accounting words.
 * Example: 50000000 -> "Năm mươi triệu đồng"
 */
export function vndToVietnameseWords(raw) {
  const digits = parseDigits(raw).replace(/^0+(?=\d)/, "");
  if (!digits) return "";
  if (digits === "0") return "Không đồng";
  if (digits.length > 18) return "";

  const groups = [];
  for (let i = digits.length; i > 0; i -= 3) {
    const chunk = digits.slice(Math.max(0, i - 3), i);
    groups.unshift(Number(chunk));
  }

  const words = [];
  for (let idx = 0; idx < groups.length; idx++) {
    const val = groups[idx];
    if (val === 0) continue;
    const h = Math.floor(val / 100);
    const t = Math.floor((val % 100) / 10);
    const u = val % 10;
    const readZeroHundred = idx > 0;
    const chunkWords = readThreeDigits(h, t, u, readZeroHundred);
    const scale = SCALES_VI[groups.length - 1 - idx] || "";
    words.push(scale ? `${chunkWords} ${scale}` : chunkWords);
  }

  if (!words.length) return "Không đồng";
  const sentence = `${words.join(" ").replace(/\s+/g, " ").trim()} đồng`;
  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ISO_DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const ISO_DATETIME_RE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/;

export function isUuid(value) {
  return typeof value === "string" && UUID_RE.test(value.trim());
}

export function formatIsoDateOnly(value) {
  const match = typeof value === "string" ? ISO_DATE_ONLY_RE.exec(value.trim()) : null;
  if (!match) return null;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

export function formatScalarDisplay(name, value, { enumMap = {}, resolvedUsers = {}, technical = false } = {}) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Có" : "Không";

  if (isCurrencyField(name) && (typeof value === "number" || /^\d+(\.0+)?$/.test(String(value).trim()))) {
    return formatVnd(value);
  }

  if (typeof value === "number") {
    if (String(name || "").endsWith("_percent")) return `${value}%`;
    return value.toLocaleString("vi-VN");
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "—";
    if (isUuid(trimmed)) {
      if (resolvedUsers && resolvedUsers[trimmed]) {
        return resolvedUsers[trimmed];
      }
      return technical ? trimmed : "Nhân sự trên hệ thống";
    }
    if (enumMap[trimmed]) {
      return enumMap[trimmed];
    }
    const dateOnly = formatIsoDateOnly(trimmed);
    if (dateOnly) return dateOnly;
    if (ISO_DATETIME_RE.test(trimmed)) {
      const parsed = Date.parse(trimmed);
      if (!Number.isNaN(parsed)) {
        return new Date(parsed).toLocaleString("vi-VN");
      }
    }
    return trimmed;
  }

  return String(value);
}

