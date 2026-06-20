const vndNumberFormat = new Intl.NumberFormat("vi-VN");

const vndCurrencyFormat = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

/** Format a VND amount, e.g. 3500000 -> "3,5 triệu/tháng" friendly forms. */
export function formatCurrency(value?: number | null): string {
  if (value == null) return "—";
  if (value >= 1_000_000) {
    const m = value / 1_000_000;
    return `${trim(m)} triệu`;
  }
  if (value >= 1_000) return `${trim(value / 1_000)}k`;
  return vndNumberFormat.format(value);
}

export function formatVnd(value?: number | null): string {
  if (value == null) return "—";
  return vndCurrencyFormat.format(value);
}

function trim(n: number): string {
  return n
    .toFixed(1)
    .replace(/\.0$/, "")
    .replace(".", ",");
}

export function formatArea(value?: number | null): string {
  if (value == null) return "—";
  return `${value} m²`;
}

const WEEKDAYS = [
  "Chủ Nhật",
  "Thứ Hai",
  "Thứ Ba",
  "Thứ Tư",
  "Thứ Năm",
  "Thứ Sáu",
  "Thứ Bảy",
];

export function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const time = d.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${time} - ${WEEKDAYS[d.getDay()]}, ${formatDate(iso)}`;
}

export function formatRelative(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "";
  const diff = Date.now() - d;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "vừa xong";
  if (min < 60) return `${min} phút trước`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} giờ trước`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} ngày trước`;
  return formatDate(iso);
}

export function formatDistance(meters?: number | null): string {
  if (meters == null) return "";
  if (meters < 1000) return `${Math.round(meters)}m`;
  return `${(meters / 1000).toFixed(1).replace(".", ",")}km`;
}
