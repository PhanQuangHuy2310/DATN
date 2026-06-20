import { Link } from "react-router-dom";
import { Trash2, BellRing } from "lucide-react";
import { Button, Switch, EmptyState, Skeleton, useToast } from "@/shared/ui";
import { getErrorMessage } from "@/shared/api";
import { formatCurrency } from "@/shared/lib";
import { filtersToParams } from "@/features/search-listings";
import { useSavedFilters, useUpdateSavedFilter, useDeleteSavedFilter } from "../hooks";

export function SavedFiltersPanel() {
  const { data, isLoading } = useSavedFilters();
  const updateFilter = useUpdateSavedFilter();
  const removeFilter = useDeleteSavedFilter();
  const toast = useToast();
  const items = data ?? [];

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        icon={<BellRing className="size-7" />}
        title="Chưa lưu bộ lọc nào"
        description="Lưu bộ lọc tìm kiếm để nhận thông báo khi có phòng mới phù hợp."
        action={
          <Link to="/search">
            <Button>Tạo bộ lọc</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {items.map((f) => {
        const c = f.criteria;
        const summary = [
          c.district,
          c.priceMin != null || c.priceMax != null
            ? `${formatCurrency(c.priceMin ?? 0)} - ${formatCurrency(c.priceMax ?? 0)}`
            : null,
          c.type === "ROOMMATE" ? "Ở ghép" : null,
        ]
          .filter(Boolean)
          .join(" · ");

        return (
          <div key={f.id} className="rounded-[8.8px] border border-line bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <Link
                  to={`/search?${filtersToParams(c)}`}
                  className="font-medium text-ink hover:text-cobalt"
                >
                  {f.name}
                </Link>
                <p className="mt-0.5 text-xs text-fog">{summary || "Tất cả phòng trọ"}</p>
              </div>
              <button
                type="button"
                onClick={() =>
                  removeFilter.mutate(f.id, {
                    onSuccess: () => toast.success("Đã xóa bộ lọc."),
                    onError: (e) => toast.error(getErrorMessage(e)),
                  })
                }
                aria-label="Xóa bộ lọc"
                className="rounded-[8.8px] p-2 text-fog transition-colors hover:bg-error-soft hover:text-error"
              >
                <Trash2 className="size-4" />
              </button>
            </div>

            <div className="mt-3 flex flex-wrap gap-5 border-t border-line pt-3">
              <Switch
                id={`email-${f.id}`}
                label="Thông báo qua Email"
                checked={f.notifyEmail}
                onChange={(v) => updateFilter.mutate({ id: f.id, notifyEmail: v })}
              />
              <Switch
                id={`inapp-${f.id}`}
                label="Thông báo trong ứng dụng"
                checked={f.notifyInApp}
                onChange={(v) => updateFilter.mutate({ id: f.id, notifyInApp: v })}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
