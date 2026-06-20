import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, MapPin, Clock } from "lucide-react";
import { Avatar, Button, Tabs, EmptyState, Skeleton, useToast, type TabItem } from "@/shared/ui";
import { getErrorMessage } from "@/shared/api";
import { formatDateTime } from "@/shared/lib";
import { AppointmentStatusBadge } from "@/entities/appointment";
import type { Appointment, AppointmentStatus } from "@/entities/appointment";
import { useAuthStore } from "@/features/auth";
import { useAppointments, useUpdateAppointmentStatus } from "./hooks";

const TABS: TabItem[] = [
  { value: "ALL", label: "Tất cả" },
  { value: "PENDING", label: "Chờ duyệt" },
  { value: "CONFIRMED", label: "Đã xác nhận" },
  { value: "SUCCESS", label: "Đã xem" },
  { value: "CANCELLED", label: "Đã hủy" },
];

export function AppointmentsPage() {
  const { data, isLoading } = useAppointments();
  const [filter, setFilter] = useState("ALL");

  const items = data ?? [];
  const filtered = filter === "ALL" ? items : items.filter((a) => a.status === filter);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <div className="mb-5 flex items-center gap-2">
        <CalendarDays className="size-6 text-cobalt" />
        <h1 className="text-2xl">Quản lý lịch hẹn xem phòng</h1>
      </div>

      <div className="mb-5 overflow-x-auto">
        <Tabs items={TABS} value={filter} onChange={setFilter} />
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full" />)}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<CalendarDays className="size-7" />}
          title="Chưa có lịch hẹn nào"
          description="Đặt lịch xem phòng từ trang chi tiết tin đăng để quản lý tại đây."
          action={
            <Link to="/search">
              <Button>Tìm phòng ngay</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((a) => (
            <AppointmentRow key={a.id} appointment={a} />
          ))}
        </div>
      )}
    </div>
  );
}

function AppointmentRow({ appointment: a }: { appointment: Appointment }) {
  const { user } = useAuthStore();
  const toast = useToast();
  const update = useUpdateAppointmentStatus();
  const amLandlord = user?.id === a.landlord.id;
  const counterpart = amLandlord ? a.tenant : a.landlord;

  const act = (status: AppointmentStatus, reason?: string) =>
    update.mutate(
      { id: a.id, status, reason },
      { onError: (e) => toast.error(getErrorMessage(e)) },
    );

  const reject = () => {
    const reason = window.prompt("Lý do từ chối lịch hẹn:");
    if (reason === null) return;
    act("CANCELLED", reason || undefined);
  };

  const actions = useMemo<ReactActions>(() => {
    if (a.status === "PENDING") {
      return amLandlord
        ? [
            { label: "Chấp nhận", onClick: () => act("CONFIRMED"), variant: "primary" },
            { label: "Từ chối", onClick: reject, variant: "ghost" },
          ]
        : [{ label: "Hủy lịch hẹn", onClick: () => act("CANCELLED"), variant: "ghost" }];
    }
    if (a.status === "CONFIRMED") {
      return amLandlord
        ? [{ label: "Báo cáo xem thành công", onClick: () => act("SUCCESS"), variant: "primary" }]
        : [{ label: "Hủy lịch hẹn", onClick: () => act("CANCELLED"), variant: "ghost" }];
    }
    return [];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a.status, amLandlord]);

  return (
    <div className="rounded-[8.8px] border border-line bg-white p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <Avatar src={a.listing.coverUrl} name={a.listing.title} size={56} className="rounded-[8.8px]" />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <Link to={`/listings/${a.listing.id}`} className="line-clamp-1 font-medium text-ink hover:text-cobalt">
              {a.listing.title}
            </Link>
            <AppointmentStatusBadge status={a.status} />
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fog">
            {a.listing.district && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3.5" /> {a.listing.district}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3.5" /> {formatDateTime(a.appointmentTime)}
            </span>
          </div>

          <div className="mt-2 flex items-center gap-2 text-sm text-graphite">
            <span className="text-fog">{amLandlord ? "Khách thuê:" : "Chủ trọ:"}</span>
            <span className="font-medium">{counterpart.name}</span>
          </div>

          {a.note && <p className="mt-1 text-sm text-fog">Ghi chú: {a.note}</p>}
          {a.status === "CANCELLED" && a.cancelReason && (
            <p className="mt-1 text-sm text-error">Lý do hủy: {a.cancelReason}</p>
          )}

          {actions.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {actions.map((act) => (
                <Button
                  key={act.label}
                  size="sm"
                  variant={act.variant}
                  onClick={act.onClick}
                  loading={update.isPending}
                >
                  {act.label}
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

type ReactActions = { label: string; onClick: () => void; variant: "primary" | "ghost" }[];
