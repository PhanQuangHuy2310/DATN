import { Client, type IMessage } from "@stomp/stompjs";
import { config } from "@/shared/config";
import { tokenStorage } from "./tokenStorage";

/**
 * Create a configured STOMP client over the native WebSocket.
 * Endpoints (see spec §4.2):
 *   subscribe  /topic/chat/{conversationId}
 *   publish    /app/chat/{conversationId}
 *   subscribe  /user/queue/notifications
 */
export function createStompClient(handlers: {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (msg: string) => void;
}): Client {
  const client = new Client({
    brokerURL: config.wsUrl,
    connectHeaders: {
      Authorization: `Bearer ${tokenStorage.getAccess() ?? ""}`,
    },
    reconnectDelay: 4000,
    heartbeatIncoming: 10000,
    heartbeatOutgoing: 10000,
    onConnect: () => handlers.onConnect?.(),
    onWebSocketClose: () => handlers.onDisconnect?.(),
    onStompError: (frame) =>
      handlers.onError?.(frame.headers["message"] ?? "STOMP error"),
  });
  return client;
}

export type { IMessage };
