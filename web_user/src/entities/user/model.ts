import type { UserRole } from "@/shared/types";

export type UserPlan = "FREE" | "PRO";

export interface User {
  id: number;
  name: string;
  email: string;
  phone?: string;
  role: UserRole;
  avatarUrl?: string | null;
  reputationScore?: number;
  verified?: boolean;
  plan?: UserPlan;
  createdAt?: string;
}

/** Lightweight shape embedded inside listings, reviews, conversations. */
export interface UserSummary {
  id: number;
  name: string;
  avatarUrl?: string | null;
  reputationScore?: number;
  verified?: boolean;
}

export const isLandlord = (u?: User | null) => u?.role === "LANDLORD";
export const isTenant = (u?: User | null) => u?.role === "TENANT";
