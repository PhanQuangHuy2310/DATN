export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8088",
  wsUrl: import.meta.env.VITE_WS_URL ?? "ws://localhost:8088/ws",
  brandName: import.meta.env.VITE_BRAND_NAME ?? "Nhà Trọ 360",
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? "",
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? "",
  supabaseBucket: import.meta.env.VITE_SUPABASE_BUCKET ?? "rental-media",
} as const;

/** Hanoi default map center — used before the user moves the map. */
export const DEFAULT_MAP_CENTER: [number, number] = [21.0285, 105.8542];
export const DEFAULT_MAP_ZOOM = 13;

export const STORAGE_KEYS = {
  accessToken: "ntr_access_token",
  refreshToken: "ntr_refresh_token",
  user: "ntr_user",
} as const;
