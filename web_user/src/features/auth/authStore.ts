import { create } from "zustand";
import { STORAGE_KEYS } from "@/shared/config";
import { tokenStorage } from "@/shared/api";
import type { User } from "@/entities/user";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  hydrated: boolean;
  setSession: (payload: {
    user: User;
    accessToken: string;
    refreshToken?: string;
  }) => void;
  setUser: (user: User) => void;
  logout: () => void;
  hydrate: () => void;
}

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.user);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  hydrated: false,

  setSession: ({ user, accessToken, refreshToken }) => {
    tokenStorage.set(accessToken, refreshToken);
    localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
    set({ user, isAuthenticated: true });
  },

  setUser: (user) => {
    localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
    set({ user });
  },

  logout: () => {
    tokenStorage.clear();
    set({ user: null, isAuthenticated: false });
  },

  hydrate: () => {
    const user = readStoredUser();
    const hasToken = !!tokenStorage.getAccess();
    set({ user, isAuthenticated: hasToken && !!user, hydrated: true });
  },
}));
