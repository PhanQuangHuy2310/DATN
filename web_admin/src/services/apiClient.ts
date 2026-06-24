import axios from 'axios';
import { ensureAdminToken, refreshAdminToken } from './adminAuth';

const API_BASE_URL = 'http://localhost:8088/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Tự đính kèm token ADMIN (lấy ngầm, không cần đăng nhập).
apiClient.interceptors.request.use(async (config) => {
  const token = await ensureAdminToken();
  config.headers.Authorization = `Bearer ${token}`;
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Token hết hạn -> lấy token mới rồi thử lại 1 lần.
apiClient.interceptors.response.use((response) => response, async (error) => {
  const original = error.config;
  if (error.response?.status === 401 && original && !original._retried) {
    original._retried = true;
    const token = await refreshAdminToken();
    original.headers.Authorization = `Bearer ${token}`;
    return apiClient(original);
  }
  return Promise.reject(error);
});

export default apiClient;
