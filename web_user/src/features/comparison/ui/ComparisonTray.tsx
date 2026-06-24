import { useComparisonStore } from "../useComparisonStore";
import { Button } from "@/shared/ui";
import { Scale } from "lucide-react";

export function ComparisonTray() {
  const { selectedListingIds, clear, setIsOpen } = useComparisonStore();

  if (selectedListingIds.length === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-4 rounded-[15px] border border-line bg-white px-5 py-3 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
      <div className="flex items-center gap-2">
        <Scale className="size-5 text-cobalt" />
        <span className="text-sm font-medium text-ink">Đã chọn {selectedListingIds.length}/3</span>
      </div>
      
      <div className="h-6 w-px bg-line" />
      
      <div className="flex gap-2">
        <Button size="sm" onClick={() => setIsOpen(true)} disabled={selectedListingIds.length < 2}>
          So sánh
        </Button>
        <Button size="sm" variant="secondary" onClick={clear}>
          Xóa
        </Button>
      </div>
    </div>
  );
}
