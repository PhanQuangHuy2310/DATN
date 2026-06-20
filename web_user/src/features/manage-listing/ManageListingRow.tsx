import { Link } from "react-router-dom";
import { Copy, Pencil, Trash2, Eye, Loader2 } from "lucide-react";
import { Switch, Badge, Avatar } from "@/shared/ui";
import { useToast } from "@/shared/ui";
import { getErrorMessage } from "@/shared/api";
import { formatCurrency } from "@/shared/lib";
import type { Listing } from "@/entities/listing";
import {
  useToggleListingStatus,
  useCloneListing,
  useDeleteListing,
} from "./hooks";

export function ManageListingRow({ listing }: { listing: Listing }) {
  const toast = useToast();
  const toggle = useToggleListingStatus();
  const clone = useCloneListing();
  const remove = useDeleteListing();
  const pending = listing.status === "PENDING";

  const onToggle = (next: boolean) =>
    toggle.mutate(
      { id: listing.id, status: next ? "AVAILABLE" : "RENTED" },
      { onError: (e) => toast.error(getErrorMessage(e)) },
    );

  return (
    <div className="flex flex-col gap-3 rounded-[8.8px] border border-line bg-white p-3 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar src={listing.mediaUrls?.[0]} name={listing.title} size={52} className="rounded-[8.8px]" />
        <div className="min-w-0">
          <Link to={`/listings/${listing.id}`} className="line-clamp-1 font-medium text-ink hover:text-cobalt">
            {listing.title}
          </Link>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-fog">
            <span className="font-semibold text-cobalt">{formatCurrency(listing.price)}/tháng</span>
            <span className="inline-flex items-center gap-1">
              <Eye className="size-3.5" /> {listing.viewCount ?? 0}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 sm:justify-end">
        {pending ? (
          <Badge tone="warning">
            <Loader2 className="size-3 animate-spin" /> Đang chờ duyệt
          </Badge>
        ) : (
          <Switch
            checked={listing.status === "AVAILABLE"}
            onChange={onToggle}
            disabled={toggle.isPending}
            label={listing.status === "AVAILABLE" ? "Còn trống" : "Đã thuê"}
          />
        )}

        <div className="flex items-center gap-1">
          <Link
            to={`/listings/${listing.id}/edit`}
            aria-label="Sửa tin"
            className="rounded-[8.8px] p-2 text-fog transition-colors hover:bg-paper hover:text-cobalt"
          >
            <Pencil className="size-4" />
          </Link>
          <button
            type="button"
            aria-label="Nhân bản tin"
            onClick={() =>
              clone.mutate(listing.id, {
                onSuccess: () => toast.success("Đã nhân bản tin đăng."),
                onError: (e) => toast.error(getErrorMessage(e)),
              })
            }
            className="rounded-[8.8px] p-2 text-fog transition-colors hover:bg-paper hover:text-cobalt"
          >
            <Copy className="size-4" />
          </button>
          <button
            type="button"
            aria-label="Xóa tin"
            onClick={() => {
              if (!confirm("Xóa tin đăng này?")) return;
              remove.mutate(listing.id, {
                onSuccess: () => toast.success("Đã xóa tin đăng."),
                onError: (e) => toast.error(getErrorMessage(e)),
              });
            }}
            className="rounded-[8.8px] p-2 text-fog transition-colors hover:bg-error-soft hover:text-error"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
