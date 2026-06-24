import axios from 'axios';

const API_BASE_URL = 'http://localhost:8088/api';

// Web admin chỉ chạy trên máy của admin, không có màn đăng nhập.
// Token ADMIN được lấy ngầm bằng tài khoản admin mặc định (seed sẵn ở backend)
// để vẫn thỏa mãn @PreAuthorize("hasRole('ADMIN')") và ghi audit log đúng người.
const ADMIN_CREDENTIALS = {
  email: 'admin@timtro.com',
  password: 'admin123',
  role: 'ADMIN',
};

let loginPromise: Promise<string> | null = null;

async function requestNewToken(): Promise<string> {
  const { data } = await axios.post(`${API_BASE_URL}/auth/login`, ADMIN_CREDENTIALS);
  localStorage.setItem('admin_token', data.accessToken);
  return data.accessToken as string;
}

// Đảm bảo luôn có token ADMIN hợp lệ. Gọi nhiều lần đồng thời chỉ login 1 lần.
export function ensureAdminToken(): Promise<string> {
  const existing = localStorage.getItem('admin_token');
  if (existing) return Promise.resolve(existing);

  if (!loginPromise) {
    loginPromise = requestNewToken().finally(() => {
      loginPromise = null;
    });
  }
  return loginPromise;
}

// Buộc lấy token mới (dùng khi token cũ hết hạn -> 401).
export function refreshAdminToken(): Promise<string> {
  localStorage.removeItem('admin_token');
  return ensureAdminToken();
}
