export type UserRole = "TENANT" | "LANDLORD" | "ADMIN";

export type LatLng = { lat: number; lng: number };

/** Spring Data pageable response shape. */
export interface Page<T> {
  content: T[];
  pageNumber: number;
  pageSize: number;
  totalElements: number;
  totalPages: number;
}

export interface ApiErrorBody {
  status?: string;
  message?: string;
  errors?: Record<string, string>;
}

export type AsyncStatus = "idle" | "loading" | "success" | "error";
