import type { UserSummary } from "@/entities/user";

export type MessageStatus = "SENDING" | "SENT" | "DELIVERED" | "READ" | "FAILED";

export interface Message {
  id: number | string;
  conversationId: number;
  senderId: number;
  content: string;
  imageUrl?: string | null;
  createdAt: string;
  status?: MessageStatus;
}

export interface ConversationListingRef {
  id: number;
  title: string;
  price?: number;
  coverUrl?: string | null;
}

export interface Conversation {
  id: number;
  partner: UserSummary;
  listing?: ConversationListingRef;
  lastMessage?: string;
  lastMessageAt?: string;
  unreadCount?: number;
  online?: boolean;
}
