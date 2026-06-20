import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { apiClient, endpoints } from "@/shared/api";
import { useClickOutside, formatRelative } from "@/shared/lib";
import { cn } from "@/shared/lib/cn";

interface AppNotification {
  id: number;
  title: string;
  body?: string;
  read: boolean;
  createdAt: string;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      const res = await apiClient.get<AppNotification[]>(endpoints.notifications.base);
      return res.data;
    },
  });

  const items = data ?? [];
  const unread = items.filter((n) => !n.read).length;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        id="notification-bell"
        aria-label="Thông báo"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-[8.8px] p-2 text-graphite transition-colors hover:bg-paper"
      >
        <Bell className="size-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="panel-float absolute right-0 mt-2 w-80 rounded-[8.8px] p-1">
          <p className="px-3 py-2 text-sm font-semibold text-ink">Thông báo</p>
          <div className="scroll-area max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-fog">Chưa có thông báo nào.</p>
            ) : (
              items.map((n) => (
                <div
                  key={n.id}
                  className={cn(
                    "rounded-[6px] px-3 py-2.5 text-sm transition-colors hover:bg-paper",
                    !n.read && "bg-cobalt-soft/40",
                  )}
                >
                  <p className="font-medium text-ink">{n.title}</p>
                  {n.body && <p className="text-fog">{n.body}</p>}
                  <p className="mt-0.5 text-xs text-fog">{formatRelative(n.createdAt)}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
