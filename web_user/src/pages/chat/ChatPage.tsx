import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Search, MessageCircle, WifiOff, ArrowLeft } from "lucide-react";
import { Avatar, EmptyState, Spinner } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { formatRelative, formatCurrency } from "@/shared/lib";
import { ChatBubble } from "@/entities/conversation";
import type { Conversation, Message } from "@/entities/conversation";
import { useAuthStore } from "@/features/auth";
import { MessageComposer } from "@/features/send-message";
import { useConversations, useMessages } from "./hooks";
import { useChatSocket } from "./useChatSocket";

export function ChatPage() {
  const { user } = useAuthStore();
  const me = user?.id ?? 0;
  const [params, setParams] = useSearchParams();

  const { data: conversations, isLoading } = useConversations();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [query, setQuery] = useState("");

  // Resolve the active conversation from ?c= or the first one in the list.
  useEffect(() => {
    const fromUrl = params.get("c");
    if (fromUrl) setActiveId(Number(fromUrl));
    else if (conversations?.length && activeId == null) setActiveId(conversations[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversations, params]);

  const active = conversations?.find((c) => c.id === activeId) ?? null;
  const messagesQuery = useMessages(activeId);

  const [messages, setMessages] = useState<Message[]>([]);
  useEffect(() => {
    setMessages(messagesQuery.data ?? []);
  }, [messagesQuery.data]);

  const handleIncoming = (msg: Message) => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === msg.id)) return prev;
      const idx = prev.findIndex(
        (m) => m.status === "SENDING" && m.senderId === msg.senderId && m.content === msg.content,
      );
      if (idx >= 0) {
        const copy = prev.slice();
        copy[idx] = { ...msg, status: "SENT" };
        return copy;
      }
      return [...prev, msg];
    });
  };

  const { connected, send } = useChatSocket(activeId, handleIncoming);

  const onSend = ({ content, imageUrl }: { content: string; imageUrl?: string }) => {
    if (activeId == null) return;
    const temp: Message = {
      id: `temp-${Date.now()}`,
      conversationId: activeId,
      senderId: me,
      content,
      imageUrl: imageUrl ?? null,
      createdAt: new Date().toISOString(),
      status: "SENDING",
    };
    setMessages((prev) => [...prev, temp]);
    const receiverId = active?.partner.id != null ? String(active.partner.id) : "";
    send({ content, imageUrl, receiverId });
  };

  const filtered = useMemo(() => {
    const list = conversations ?? [];
    if (!query.trim()) return list;
    const q = query.toLowerCase();
    return list.filter((c) => c.partner.name.toLowerCase().includes(q));
  }, [conversations, query]);

  const selectConversation = (id: number) => {
    setActiveId(id);
    setParams({ c: String(id) }, { replace: true });
  };

  return (
    <div className="flex h-full">
      {/* LEFT: conversation list */}
      <aside
        className={cn(
          "flex w-full flex-col border-r border-line sm:w-80",
          active && "hidden sm:flex",
        )}
      >
        <div className="border-b border-line p-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fog" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm cuộc trò chuyện…"
              aria-label="Tìm cuộc trò chuyện"
              className="h-10 w-full rounded-[8.8px] border border-line bg-white pl-9 pr-3 text-sm focus:border-cobalt focus:outline-none focus:ring-2 focus:ring-cobalt/15"
            />
          </div>
        </div>

        <div className="scroll-area min-h-0 flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : filtered.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-fog">Chưa có cuộc trò chuyện nào.</p>
          ) : (
            filtered.map((c) => (
              <ConversationItem
                key={c.id}
                conversation={c}
                active={c.id === activeId}
                onClick={() => selectConversation(c.id)}
              />
            ))
          )}
        </div>
      </aside>

      {/* RIGHT: thread */}
      <section className={cn("flex min-w-0 flex-1 flex-col", !active && "hidden sm:flex")}>
        {!active ? (
          <div className="flex flex-1 items-center justify-center">
            <EmptyState
              icon={<MessageCircle className="size-7" />}
              title="Chọn một cuộc trò chuyện"
              description="Tin nhắn của bạn với chủ trọ và khách thuê sẽ hiển thị tại đây."
            />
          </div>
        ) : (
          <>
            {/* Thread header */}
            <div className="flex items-center gap-3 border-b border-line bg-paper px-4 py-3">
              <button type="button" onClick={() => setActiveId(null)} className="text-fog sm:hidden" aria-label="Quay lại">
                <ArrowLeft className="size-5" />
              </button>
              <Avatar src={active.partner.avatarUrl} name={active.partner.name} size={40} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-ink">{active.partner.name}</p>
                <p className="text-xs text-fog">
                  {active.online ? (
                    <span className="text-success">● Đang hoạt động</span>
                  ) : (
                    "Ngoại tuyến"
                  )}
                </p>
              </div>
            </div>

            {/* Pinned listing preview */}
            {active.listing && (
              <Link
                to={`/listings/${active.listing.id}`}
                className="flex items-center gap-3 border-b border-line bg-white px-4 py-2.5 hover:bg-paper"
              >
                {active.listing.coverUrl && (
                  <img src={active.listing.coverUrl} alt={active.listing.title} className="size-10 rounded-[6px] object-cover" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{active.listing.title}</p>
                  {active.listing.price != null && (
                    <p className="text-xs font-semibold text-cobalt">{formatCurrency(active.listing.price)}/tháng</p>
                  )}
                </div>
              </Link>
            )}

            {/* Disconnect banner */}
            {!connected && (
              <div className="flex items-center gap-2 bg-warning-soft px-4 py-2 text-xs text-warning">
                <WifiOff className="size-3.5" />
                Đang mất kết nối thời gian thực. Tin nhắn mới sẽ tự động đồng bộ khi mạng hoạt động trở lại.
              </div>
            )}

            {/* Messages */}
            <MessageList messages={messages} me={me} loading={messagesQuery.isLoading} />

            <MessageComposer disabled={activeId == null} onSend={onSend} />
          </>
        )}
      </section>
    </div>
  );
}

function ConversationItem({
  conversation: c,
  active,
  onClick,
}: {
  conversation: Conversation;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 border-b border-line px-4 py-3 text-left transition-colors",
        active ? "bg-cobalt-soft/50" : "hover:bg-paper",
      )}
    >
      <div className="relative">
        <Avatar src={c.partner.avatarUrl} name={c.partner.name} size={44} />
        {c.online && <span className="absolute bottom-0 right-0 size-3 rounded-full border-2 border-paper bg-success" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-sm font-medium text-ink">{c.partner.name}</p>
          <span className="shrink-0 text-[11px] text-fog">{formatRelative(c.lastMessageAt)}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-xs text-fog">{c.lastMessage ?? "Bắt đầu trò chuyện"}</p>
          {!!c.unreadCount && (
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-error text-[10px] font-semibold text-white">
              {c.unreadCount > 9 ? "9+" : c.unreadCount}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

function MessageList({ messages, me, loading }: { messages: Message[]; me: number; loading: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="scroll-area min-h-0 flex-1 space-y-2 overflow-y-auto bg-paper p-4">
      {messages.length === 0 ? (
        <p className="py-8 text-center text-sm text-fog">Chưa có tin nhắn. Hãy gửi lời chào!</p>
      ) : (
        messages.map((m) => <ChatBubble key={m.id} message={m} mine={m.senderId === me} />)
      )}
      <div ref={endRef} />
    </div>
  );
}
