import { useMemo, useState } from "react";
import { Modal, Button, Textarea, Spinner, EmptyState } from "@/shared/ui";
import { useToast } from "@/shared/ui";
import { getErrorMessage } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { useListingSlots, useCreateAppointment } from "./hooks";

interface Props {
  open: boolean;
  onClose: () => void;
  listingId: number;
  listingTitle?: string;
}

export function BookAppointmentModal({ open, onClose, listingId, listingTitle }: Props) {
  const { data: slots, isLoading } = useListingSlots(listingId, open);
  const create = useCreateAppointment();
  const toast = useToast();
  const [selected, setSelected] = useState<string | null>(null);
  const [note, setNote] = useState("");

  // Group available slots by calendar day.
  const byDay = useMemo(() => {
    const map = new Map<string, { time: string }[]>();
    for (const s of slots ?? []) {
      if (!s.available) continue;
      const day = new Date(s.time).toLocaleDateString("vi-VN", {
        weekday: "long",
        day: "2-digit",
        month: "2-digit",
      });
      const arr = map.get(day) ?? [];
      arr.push({ time: s.time });
      map.set(day, arr);
    }
    return [...map.entries()];
  }, [slots]);

  const submit = () => {
    if (!selected) return;
    create.mutate(
      { listingId, appointmentTime: selected, note: note.trim() || undefined },
      {
        onSuccess: () => {
          toast.success("Đã gửi yêu cầu đặt lịch. Chờ chủ trọ xác nhận.");
          onClose();
          setSelected(null);
          setNote("");
        },
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Đặt lịch hẹn xem phòng"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Hủy
          </Button>
          <Button onClick={submit} loading={create.isPending} disabled={!selected}>
            Gửi yêu cầu
          </Button>
        </>
      }
    >
      {listingTitle && <p className="mb-3 text-sm text-fog">Phòng: {listingTitle}</p>}

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : byDay.length === 0 ? (
        <EmptyState
          title="Chưa có khung giờ trống"
          description="Chủ trọ chưa mở lịch. Bạn có thể nhắn tin để hỏi trực tiếp."
        />
      ) : (
        <div className="space-y-4">
          {byDay.map(([day, times]) => (
            <div key={day}>
              <p className="mb-2 text-sm font-medium capitalize text-graphite">{day}</p>
              <div className="flex flex-wrap gap-2">
                {times.map(({ time }) => {
                  const label = new Date(time).toLocaleTimeString("vi-VN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  return (
                    <button
                      key={time}
                      type="button"
                      onClick={() => setSelected(time)}
                      className={cn(
                        "rounded-[8.8px] border px-3.5 py-1.5 text-sm transition-colors",
                        selected === time
                          ? "border-cobalt bg-cobalt text-white"
                          : "border-line text-graphite hover:border-cobalt",
                      )}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <Textarea
            label="Ghi chú cho chủ trọ (tùy chọn)"
            name="note"
            placeholder="vd: Tôi muốn xem phòng vào buổi chiều, đi cùng 1 người…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
      )}
    </Modal>
  );
}
