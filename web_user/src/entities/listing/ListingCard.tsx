import { Link } from "react-router-dom";
import { Heart, MapPin, Ruler, Bike, BadgeCheck, Star } from "lucide-react";
import { Badge } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import {
  formatCurrency,
  formatArea,
  formatDistance,
  ALLEY_WIDTHS,
} from "@/shared/lib";
import type { Listing } from "./model";

export interface ListingCardProps {
  listing: Listing;
  layout?: "grid" | "list" | "map";
  onToggleFavorite?: (id: number) => void;
  active?: boolean;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
}

const GENDER_LABEL: Record<string, string> = {
  MALE: "Nam",
  FEMALE: "Nữ",
  ANY: "Nam/Nữ",
};

export function ListingCard({
  listing,
  layout = "grid",
  onToggleFavorite,
  active,
  onMouseEnter,
  onMouseLeave,
}: ListingCardProps) {
  const cover = listing.mediaUrls?.[0];
  const alleyWidth = ALLEY_WIDTHS.find((a) => a.value === listing.alleyWidth)?.label;
  const horizontal = layout === "list" || layout === "map";

  return (
    <Link
      to={`/listings/${listing.id}`}
      id={`listing-card-${listing.id}`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={cn(
        "card-hover group relative block overflow-hidden rounded-[8.8px] border bg-white",
        active ? "border-cobalt" : "border-line",
        horizontal && "flex gap-3",
      )}
    >
      {/* Cover */}
      <div
        className={cn(
          "relative shrink-0 overflow-hidden bg-chalk",
          horizontal ? "w-32 sm:w-40" : "aspect-[4/3] w-full",
        )}
      >
        {cover ? (
          <img
            src={cover}
            alt={listing.title}
            loading="lazy"
            className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex size-full items-center justify-center text-fog">
            <MapPin className="size-7" />
          </div>
        )}

        <div className="absolute left-2 top-2 flex flex-wrap gap-1.5">
          {listing.isPro && <Badge tone="warning">PRO</Badge>}
          {listing.status === "RENTED" && <Badge tone="neutral">Đã cho thuê</Badge>}
          {listing.status === "PENDING" && <Badge tone="warning">Chờ duyệt</Badge>}
        </div>

        {onToggleFavorite && (
          <button
            type="button"
            aria-label="Lưu tin yêu thích"
            onClick={(e) => {
              e.preventDefault();
              onToggleFavorite(listing.id);
            }}
            className="absolute right-2 top-2 rounded-full bg-white/90 p-1.5 text-fog transition-colors hover:text-error"
          >
            <Heart className={cn("size-4", listing.favorite && "fill-error text-error")} />
          </button>
        )}
      </div>

      {/* Body */}
      <div className={cn("flex min-w-0 flex-col gap-1.5", horizontal ? "flex-1 py-2.5 pr-3" : "p-3")}>
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-2 text-[15px] font-medium leading-snug text-ink">
            {listing.title}
          </h3>
          {listing.verified && <BadgeCheck className="mt-0.5 size-4 shrink-0 text-cobalt" />}
        </div>

        <p className="text-base font-semibold text-cobalt">
          {formatCurrency(listing.price)}
          <span className="text-xs font-normal text-fog">/tháng</span>
        </p>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fog">
          <span className="inline-flex items-center gap-1">
            <Ruler className="size-3.5" />
            {formatArea(listing.area)}
          </span>
          {alleyWidth && (
            <span className="inline-flex items-center gap-1">
              <Bike className="size-3.5" />
              {alleyWidth}
            </span>
          )}
          {listing.maxMotorbikes != null && <span>Tối đa {listing.maxMotorbikes} xe</span>}
        </div>

        <div className="mt-auto flex items-center justify-between gap-2 pt-1">
          <span className="truncate text-xs text-fog">
            {listing.district ?? listing.address ?? listing.ward ?? ""}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {listing.type === "ROOMMATE" && listing.gender && (
              <Badge tone="cobalt">{GENDER_LABEL[listing.gender]}</Badge>
            )}
            {listing.ratingAvg != null && (
              <span className="inline-flex items-center gap-0.5 text-xs text-graphite">
                <Star className="size-3.5 fill-warning text-warning" />
                {listing.ratingAvg.toFixed(1)}
              </span>
            )}
            {listing.distance != null && (
              <span className="text-xs text-cobalt">{formatDistance(listing.distance)}</span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
