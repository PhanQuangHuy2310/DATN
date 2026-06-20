import { STORAGE_KEYS } from "@/shared/config";

export const tokenStorage = {
  getAccess: () => localStorage.getItem(STORAGE_KEYS.accessToken),
  getRefresh: () => localStorage.getItem(STORAGE_KEYS.refreshToken),
  set(accessToken: string, refreshToken?: string) {
    localStorage.setItem(STORAGE_KEYS.accessToken, accessToken);
    if (refreshToken)
      localStorage.setItem(STORAGE_KEYS.refreshToken, refreshToken);
  },
  clear() {
    localStorage.removeItem(STORAGE_KEYS.accessToken);
    localStorage.removeItem(STORAGE_KEYS.refreshToken);
    localStorage.removeItem(STORAGE_KEYS.user);
  },
};

/** Broadcast a forced logout (e.g. refresh failed) so the auth store can react. */
export const AUTH_LOGOUT_EVENT = "ntr:auth-logout";
export const emitLogout = () =>
  window.dispatchEvent(new CustomEvent(AUTH_LOGOUT_EVENT));
