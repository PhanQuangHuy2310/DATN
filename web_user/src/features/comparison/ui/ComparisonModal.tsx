import { useQuery } from "@tanstack/react-query";
import { Modal, Skeleton } from "@/shared/ui";
import { apiClient, endpoints } from "@/shared/api";
import type { Listing } from "@/entities/listing";
import { useComparisonStore } from "../useComparisonStore";
import { formatCurrency, formatArea, ALLEY_WIDTHS } from "@/shared/lib";
import { X } from "lucide-react";

export function ComparisonModal() {
  const { selectedListingIds, isOpen, setIsOpen, removeListing } = useComparisonStore();

  const { data, isLoading } = useQuery({
    queryKey: ["compare", selectedListingIds],
    queryFn: async () => {
      const idsParam = selectedListingIds.join(",");
      const res = await apiClient.get<Listing[]>(`${endpoints.listings.compare}?ids=${idsParam}`);
      return res.data;
    },
    enabled: isOpen && selectedListingIds.length > 0,
  });

  return (
    <Modal open={isOpen} onClose={() => setIsOpen(false)} title="So sánh phòng trọ" size="xl">
      {isLoading ? (
        <div className="grid grid-cols-3 gap-4">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      ) : data && data.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                <th className="p-3 font-medium text-fog w-32 shrink-0">Tiêu chí</th>
                {data.map((l) => (
                  <th key={l.id} className="min-w-[200px] p-3 align-top font-medium text-ink relative">
                    <button
                      className="absolute right-2 top-2 z-10 rounded-full bg-white/90 p-1 text-fog hover:text-error shadow-sm"
                      onClick={() => removeListing(String(l.id))}
                      title="Bỏ khỏi so sánh"
                    >
                      <X className="size-4" />
                    </button>
                    {l.mediaUrls?.[0] ? (
                      <img src={l.mediaUrls[0]} alt="" className="mb-2 h-32 w-full rounded-[8.8px] object-cover" />
                    ) : (
                      <div className="mb-2 flex h-32 w-full items-center justify-center rounded-[8.8px] bg-paper text-fog">No Image</div>
                    )}
                    <div className="line-clamp-2">{l.title}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              <tr>
                <td className="p-3 font-medium text-fog">Giá thuê</td>
                {data.map((l) => (
                  <td key={l.id} className="p-3 text-cobalt font-semibold">{formatCurrency(l.price)}/tháng</td>
                ))}
              </tr>
              <tr>
                <td className="p-3 font-medium text-fog">Diện tích</td>
                {data.map((l) => (
                  <td key={l.id} className="p-3">{formatArea(l.area)}</td>
                ))}
              </tr>
              <tr>
                <td className="p-3 font-medium text-fog">Tối đa xe máy</td>
                {data.map((l) => (
                  <td key={l.id} className="p-3">{l.maxMotorbikes ?? "—"} xe</td>
                ))}
              </tr>
              <tr>
                <td className="p-3 font-medium text-fog">Đường vào</td>
                {data.map((l) => (
                  <td key={l.id} className="p-3">
                    {ALLEY_WIDTHS.find((a) => a.value === l.alleyWidth)?.label ?? "—"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3 font-medium text-fog">Địa chỉ</td>
                {data.map((l) => (
                  <td key={l.id} className="p-3">{[l.address, l.ward, l.district].filter(Boolean).join(", ") || "—"}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-center py-8 text-fog">Chưa có dữ liệu so sánh</p>
      )}
    </Modal>
  );
}
