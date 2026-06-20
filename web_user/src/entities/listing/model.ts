import type { UserSummary } from "@/entities/user";

export type ListingStatus = "AVAILABLE" | "RENTED" | "PENDING" | "REJECTED";
export type ListingType = "RENTAL" | "ROOMMATE";
export type AlleyType = "THROUGH" | "DEAD_END";
export type AlleyWidth = "CAR" | "TRICYCLE" | "MOTORBIKE";
export type AlleyDepth = "UNDER_50" | "50_100" | "OVER_100";
export type RoommateGender = "MALE" | "FEMALE" | "ANY";

export interface ListingCosts {
  electric?: number;
  water?: number;
  wifi?: number;
  cleaning?: number;
  parking?: number;
}

export interface Listing {
  id: number;
  title: string;
  description?: string;
  price: number;
  area: number;
  lat: number;
  lng: number;
  province?: string;
  district?: string;
  ward?: string;
  address?: string;
  type: ListingType;
  status: ListingStatus;
  alleyType?: AlleyType;
  alleyWidth?: AlleyWidth;
  alleyDepth?: AlleyDepth;
  maxMotorbikes?: number;
  costs?: ListingCosts;
  amenityIds?: string[];
  mediaUrls?: string[];
  videoUrl?: string | null;
  verified?: boolean;
  isPro?: boolean;
  gender?: RoommateGender;
  landlord?: UserSummary;
  ratingAvg?: number;
  reviewCount?: number;
  viewCount?: number;
  createdAt?: string;
  /** Distance in metres from the search anchor (map / midpoint). */
  distance?: number;
  favorite?: boolean;
}

/** Card props on the map/list use a thinner subset; keep it permissive. */
export type ListingPin = Pick<Listing, "id" | "title" | "price" | "lat" | "lng"> &
  Partial<Listing>;
