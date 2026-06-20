import type { UserSummary } from "@/entities/user";

export interface ReviewReply {
  content: string;
  createdAt: string;
}

export interface Review {
  id: number;
  listingId: number;
  author: UserSummary;
  rating: number;
  content: string;
  createdAt: string;
  landlordReply?: ReviewReply | null;
}
