import { useState } from "react";
import { Plus, Trash2, Sparkles, X } from "lucide-react";
import { Button } from "@/shared/ui";
import type { LatLng } from "@/shared/types";
import { useToast } from "@/shared/ui";
import { getErrorMessage } from "@/shared/api";
import { AddressAutocomplete } from "./AddressAutocomplete";
import { useMidpointSearch, type MidpointResult } from "./hooks";

export type MidpointPoint = LatLng & { label: string };

interface Props {
  onResult: (result: MidpointResult, points: MidpointPoint[]) => void;
  onClose: () => void;
}

export function MidpointPanel({ onResult, onClose }: Props) {
  const [slots, setSlots] = useState<(MidpointPoint | null)[]>([null, null]);
  const search = useMidpointSearch();
  const toast = useToast();

  const picked = slots.filter(Boolean) as MidpointPoint[];

  const setSlot = (i: number, p: MidpointPoint) =>
    setSlots((s) => s.map((v, idx) => (idx === i ? p : v)));

  const removeSlot = (i: number) =>
    setSlots((s) => (s.length <= 2 ? s : s.filter((_, idx) => idx !== i)));

  const run = () => {
    if (picked.length < 2) {
      toast.info("Hãy chọn ít nhất 2 địa điểm.");
      return;
    }
    search.mutate(
      picked.map((p) => ({ lat: p.lat, lng: p.lng })),
      {
        onSuccess: (res) => onResult(res, picked),
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );
  };

  return (
    <div className="panel-float absolute left-3 top-3 z-[500] w-80 rounded-[8.8px] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <Sparkles className="size-4 text-cobalt" /> Tìm phòng điểm giữa
        </h4>
        <button type="button" onClick={onClose} aria-label="Đóng" className="text-fog hover:text-ink">
          <X className="size-4" />
        </button>
      </div>
      <p className="mb-3 text-xs text-fog">
        Nhập 2–4 địa điểm (nơi học, nơi làm…). Hệ thống tính điểm trung vị và xếp hạng phòng quanh đó.
      </p>

      <div className="space-y-2">
        {slots.map((_, i) => (
          <div key={i} className="flex items-start gap-1.5">
            <div className="flex-1">
              <AddressAutocomplete index={i} onPick={(p) => setSlot(i, p)} />
            </div>
            {slots.length > 2 && (
              <button
                type="button"
                onClick={() => removeSlot(i)}
                aria-label="Xóa địa điểm"
                className="mt-2 text-fog hover:text-error"
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-col gap-2">
        {slots.length < 4 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSlots((s) => [...s, null])}
          >
            <Plus className="size-4" /> Thêm địa điểm
          </Button>
        )}
        <Button block onClick={run} loading={search.isPending} disabled={picked.length < 2}>
          Tìm điểm giữa
        </Button>
      </div>
    </div>
  );
}
