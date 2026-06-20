import { config } from "@/shared/config";

/**
 * Upload a file straight to the public Supabase Storage bucket and return its
 * public URL (see WebUser_UI_Prompt_Spec §3.5). The Spring backend only stores
 * the resulting URL — it never proxies the bytes.
 */
export async function uploadToStorage(file: File, folder = "listings"): Promise<string> {
  if (!config.supabaseUrl || !config.supabaseAnonKey) {
    throw new Error("Chưa cấu hình Supabase Storage (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY).");
  }

  const safeName = file.name.replace(/[^a-zA-Z0-9.\-_]/g, "_");
  const path = `${folder}/${Date.now()}-${Math.random().toString(36).slice(2, 8)}-${safeName}`;
  const endpoint = `${config.supabaseUrl}/storage/v1/object/${config.supabaseBucket}/${path}`;

  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      apikey: config.supabaseAnonKey,
      Authorization: `Bearer ${config.supabaseAnonKey}`,
      "x-upsert": "true",
      "Content-Type": file.type || "application/octet-stream",
    },
    body: file,
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Tải tệp lên thất bại (${res.status}). ${detail}`);
  }

  return `${config.supabaseUrl}/storage/v1/object/public/${config.supabaseBucket}/${path}`;
}
