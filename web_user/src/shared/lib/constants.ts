export const AMENITIES = [
  { id: "air_conditioner", label: "Điều hòa" },
  { id: "washing_machine", label: "Máy giặt" },
  { id: "fridge", label: "Tủ lạnh" },
  { id: "balcony", label: "Ban công" },
  { id: "elevator", label: "Thang máy" },
  { id: "fingerprint_lock", label: "Khóa vân tay" },
  { id: "free_hours", label: "Tự do đi lại" },
  { id: "water_heater", label: "Nóng lạnh" },
  { id: "wifi", label: "Wifi" },
  { id: "parking", label: "Chỗ để xe" },
  { id: "private_wc", label: "WC riêng" },
  { id: "kitchen", label: "Bếp riêng" },
] as const;

export const ALLEY_TYPES = [
  { value: "THROUGH", label: "Ngõ thông" },
  { value: "DEAD_END", label: "Ngõ cụt" },
] as const;

export const ALLEY_WIDTHS = [
  { value: "CAR", label: "Ô tô vào được" },
  { value: "TRICYCLE", label: "Xe ba gác" },
  { value: "MOTORBIKE", label: "Xe máy tránh nhau" },
] as const;

export const ALLEY_DEPTHS = [
  { value: "UNDER_50", label: "Dưới 50m" },
  { value: "50_100", label: "50 - 100m" },
  { value: "OVER_100", label: "Trên 100m" },
] as const;

export const LISTING_TYPES = [
  { value: "RENTAL", label: "Phòng cho thuê" },
  { value: "ROOMMATE", label: "Tìm bạn ở ghép" },
] as const;

export const REPORT_REASONS = [
  { value: "FAKE_PRICE", label: "Giá ảo / sai thực tế" },
  { value: "WRONG_LOCATION", label: "Sai vị trí / địa chỉ ma" },
  { value: "ALREADY_RENTED", label: "Đã cho thuê, không cập nhật" },
  { value: "BAD_ATTITUDE", label: "Chủ trọ thái độ xấu" },
  { value: "SCAM", label: "Có dấu hiệu lừa đảo" },
  { value: "OTHER", label: "Lý do khác" },
] as const;

export const QUICK_DISTRICTS = [
  "Cầu Giấy",
  "Đống Đa",
  "Bách Khoa",
  "Thanh Xuân",
  "Hai Bà Trưng",
  "Hà Đông",
] as const;

export const PRICE_RANGE = { min: 0, max: 15_000_000, step: 500_000 } as const;
export const AREA_RANGE = { min: 10, max: 100, step: 5 } as const;
export const RADIUS_OPTIONS = [1, 2, 5] as const;

export function amenityLabel(id: string): string {
  return AMENITIES.find((a) => a.id === id)?.label ?? id;
}
