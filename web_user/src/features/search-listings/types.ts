import type {
  ListingType,
  AlleyType,
  AlleyWidth,
  AlleyDepth,
} from "@/entities/listing";

export interface ListingFilters {
  q?: string;
  type?: ListingType;
  priceMin?: number;
  priceMax?: number;
  areaMin?: number;
  areaMax?: number;
  alleyType?: AlleyType;
  alleyWidth?: AlleyWidth;
  alleyDepth?: AlleyDepth;
  maxMotorbikes?: number;
  amenityIds?: string[];
  district?: string;
  page?: number;
}

export const EMPTY_FILTERS: ListingFilters = { type: "RENTAL", page: 0 };
