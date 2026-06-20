import { useCallback, useEffect, useRef, useState } from "react";
import type { Client, StompSubscription } from "@stomp/stompjs";
import { createStompClient, type IMessage } from "@/shared/api";
import type { Message } from "@/entities/conversation";

export interface OutgoingMessage {
  content: string;
  imageUrl?: string;
  receiverId: string;
}

/**
 * Manages a single STOMP connection (spec §4.2): subscribes to the active
 * conversation topic and publishes outgoing messages. Re-subscribes whenever
 * the active conversation or connection state changes.
 */
export function useChatSocket(activeId: number | null, onMessage: (msg: Message) => void) {
  const clientRef = useRef<Client | null>(null);
  const subRef = useRef<StompSubscription | null>(null);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const client = createStompClient({
      onConnect: () => setConnected(true),
      onDisconnect: () => setConnected(false),
    });
    client.activate();
    clientRef.current = client;
    return () => {
      subRef.current?.unsubscribe();
      void client.deactivate();
      clientRef.current = null;
    };
  }, []);

  useEffect(() => {
    const client = clientRef.current;
    if (!client || !connected || activeId == null) return;
    const sub = client.subscribe(`/user/queue/messages`, (frame: IMessage) => {
      try {
        handlerRef.current(JSON.parse(frame.body) as Message);
      } catch {
        /* ignore malformed frame */
      }
    });
    subRef.current = sub;
    return () => sub.unsubscribe();
  }, [activeId, connected]);

  const send = useCallback((body: OutgoingMessage) => {
    const client = clientRef.current;
    if (!client?.connected) return false;
    client.publish({
      destination: `/app/chat.send`,
      body: JSON.stringify(body),
    });
    return true;
  }, []);

  return { connected, send };
}
