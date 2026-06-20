import { Check, CheckCheck, Clock, AlertCircle } from "lucide-react";
import { cn } from "@/shared/lib/cn";
import type { Message } from "./model";

export function ChatBubble({ message, mine }: { message: Message; mine: boolean }) {
  const time = new Date(message.createdAt).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={cn("flex w-full", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] rounded-[14px] px-3.5 py-2 text-sm",
          mine
            ? "rounded-br-sm bg-cobalt text-white"
            : "rounded-bl-sm border border-line bg-white text-ink",
        )}
      >
        {message.imageUrl && (
          <img
            src={message.imageUrl}
            alt="Ảnh đính kèm"
            className="mb-1.5 max-h-56 rounded-[8.8px] object-cover"
          />
        )}
        {message.content && <p className="whitespace-pre-wrap break-words">{message.content}</p>}
        <span
          className={cn(
            "mt-1 flex items-center justify-end gap-1 text-[10px]",
            mine ? "text-white/70" : "text-fog",
          )}
        >
          {time}
          {mine && <StatusIcon status={message.status} />}
        </span>
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status?: Message["status"] }) {
  switch (status) {
    case "SENDING":
      return <Clock className="size-3" />;
    case "READ":
      return <CheckCheck className="size-3" />;
    case "DELIVERED":
      return <CheckCheck className="size-3 opacity-70" />;
    case "FAILED":
      return <AlertCircle className="size-3 text-error" />;
    default:
      return <Check className="size-3" />;
  }
}
