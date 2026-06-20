import type { UserSummary } from "@/entities/user";

export type AppointmentStatus =
  | "PENDING"
  | "CONFIRMED"
  | "CANCELLED"
  | "SUCCESS";

export interface AppointmentListingRef {
  id: number;
  title: string;
  district?: string;
  coverUrl?: string | null;
}

export interface Appointment {
  id: number;
  listing: AppointmentListingRef;
  tenant: UserSummary;
  landlord: UserSummary;
  appointmentTime: string;
  note?: string;
  status: AppointmentStatus;
  cancelReason?: string;
  createdAt?: string;
}

export const APPOINTMENT_STATUS_LABEL: Record<AppointmentStatus, string> = {
  PENDING: "Chờ duyệt",
  CONFIRMED: "Đã xác nhận",
  CANCELLED: "Đã hủy",
  SUCCESS: "Đã xem phòng",
};
