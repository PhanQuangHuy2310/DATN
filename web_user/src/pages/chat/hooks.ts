import { useQuery } from "@tanstack/react-query";
import { apiClient, endpoints } from "@/shared/api";
import type { Conversation, Message } from "@/entities/conversation";

export function useConversations() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: async () => {
      const res = await apiClient.get<Conversation[]>(endpoints.conversations.base);
      return res.data;
    },
    refetchInterval: 30_000,
  });
}

export function useMessages(conversationId: number | null) {
  return useQuery({
    queryKey: ["messages", conversationId],
    enabled: conversationId != null,
    queryFn: async () => {
      const res = await apiClient.get<Message[]>(
        endpoints.conversations.messages(conversationId!),
      );
      return res.data;
    },
  });
}
