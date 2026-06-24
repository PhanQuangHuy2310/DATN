import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  MessageCircle,
  CalendarDays,
  Flag,
  BadgeCheck,
  Heart,
  Check,
  MapPin,
  Ruler,
  Bike,
  Scale,
} from "lucide-react";
import { Badge, Button, Skeleton, EmptyState, useToast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { getErrorMessage } from "@/shared/api";
import {
  formatVnd,
  formatArea,
  formatCurrency,
  amenityLabel,
  ALLEY_TYPES,
  ALLEY_WIDTHS,
  ALLEY_DEPTHS,
} from "@/shared/lib";
import { config } from "@/shared/config";
import { LandlordSummaryCard } from "@/entities/user";
import { StarRating } from "@/entities/review";
import { useAuthStore } from "@/features/auth";
import { useToggleWishlist } from "@/features/wishlist";
import { BookAppointmentModal } from "@/features/book-appointment";
import { ReportListingModal } from "@/features/report-listing";
import { MediaGallery } from "./MediaGallery";
import { PoiRadar } from "./PoiRadar";
import { ReviewSection } from "./ReviewSection";
import {
  useListing,
  useListingPoi,
  useListingReviews,
  useStartChat,
  useSimilarListings,
} from "./hooks";
import { ListingCard, ListingCardSkeleton } from "@/entities/listing";
import { useComparisonStore } from "@/features/comparison/useComparisonStore";

export function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const { isAuthenticated } = useAuthStore();

  const listingQuery = useListing(id!);
  const reviewsQuery = useListingReviews(id!);
  const poiQuery = useListingPoi(id!);
  const similarQuery = useSimilarListings(id!);
  const startChat = useStartChat();
  const toggleFav = useToggleWishlist();

  const [bookOpen, setBookOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);

  const listing = listingQuery.data;

  useEffect(() => {
    if (listing) {
      document.title = `${listing.title} - Thuê ngay tại ${config.brandName}`;
    }
    return () => {
      document.title = config.brandName;
    };
  }, [listing]);

  const requireAuth = (action: () => void) => {
    if (!isAuthenticated) {
      navigate("/login", { state: { from: `/listings/${id}` } });
      return;
    }
    action();
  };

  const onChat = () =>
    requireAuth(() =>
      startChat.mutate(listing!.id, {
        onSuccess: (res) => navigate(`/chat?c=${res.conversationId}`),
        onError: (e) => toast.error(getErrorMessage(e)),
      }),
    );

  if (listingQuery.isLoading) return <DetailSkeleton />;
  if (listingQuery.isError || !listing) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <EmptyState
          title="Không tìm thấy tin đăng"
          description="Tin đăng có thể đã bị gỡ hoặc đường dẫn không đúng."
          action={<Button onClick={() => navigate("/search")}>Tìm phòng khác</Button>}
        />
      </div>
    );
  }

  const alleyType = ALLEY_TYPES.find((a) => a.value === listing.alleyType)?.label;
  const alleyWidth = ALLEY_WIDTHS.find((a) => a.value === listing.alleyWidth)?.label;
  const alleyDepth = ALLEY_DEPTHS.find((a) => a.value === listing.alleyDepth)?.label;
  const costs = listing.costs ?? {};

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6">
      <MediaGallery images={listing.mediaUrls ?? []} videoUrl={listing.videoUrl} title={listing.title} />

      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_360px]">
        {/* LEFT column */}
        <div className="min-w-0 space-y-8">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              {listing.status === "AVAILABLE" ? (
                <Badge tone="success" dot>Còn trống</Badge>
              ) : listing.status === "RENTED" ? (
                <Badge tone="neutral" dot>Đã cho thuê</Badge>
              ) : (
                <Badge tone="warning" dot>Chờ duyệt</Badge>
              )}
              {listing.verified && (
                <Badge tone="cobalt">
                  <BadgeCheck className="size-3.5" /> Đã xác minh chính chủ
                </Badge>
              )}
              {listing.type === "ROOMMATE" && <Badge tone="cobalt">Ở ghép</Badge>}
            </div>

            <h1 className="mt-3 text-balance">{listing.title}</h1>

            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fog">
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-4" />
                {[listing.address, listing.ward, listing.district, listing.province]
                  .filter(Boolean)
                  .join(", ") || "—"}
              </span>
              {listing.ratingAvg != null && (
                <span className="inline-flex items-center gap-1">
                  <StarRating value={listing.ratingAvg} readOnly size={14} />
                  {listing.ratingAvg.toFixed(1)} ({listing.reviewCount ?? 0})
                </span>
              )}
            </div>
          </div>

          {listing.description && (
            <Section title="Mô tả">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-graphite">{listing.description}</p>
            </Section>
          )}

          <Section title="Hạ tầng ngõ ngách">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Fact label="Loại ngõ" value={alleyType} />
              <Fact label="Độ rộng ngõ" value={alleyWidth} icon={<Bike className="size-4" />} />
              <Fact label="Độ sâu ngõ" value={alleyDepth} />
              <Fact
                label="Xe máy tối đa"
                value={listing.maxMotorbikes != null ? `${listing.maxMotorbikes} xe` : undefined}
              />
            </div>
          </Section>

          <Section title="Biểu giá dịch vụ">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <CostItem label="Điện" value={costs.electric} unit="/kWh" />
              <CostItem label="Nước" value={costs.water} unit="/người" />
              <CostItem label="Wifi" value={costs.wifi} unit="/phòng" />
              <CostItem label="Vệ sinh" value={costs.cleaning} unit="/tháng" />
              <CostItem label="Gửi xe" value={costs.parking} unit="/xe" />
            </div>
          </Section>

          {listing.amenityIds && listing.amenityIds.length > 0 && (
            <Section title="Tiện ích phòng">
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {listing.amenityIds.map((a) => (
                  <span key={a} className="inline-flex items-center gap-2 text-sm text-graphite">
                    <Check className="size-4 text-success" /> {amenityLabel(a)}
                  </span>
                ))}
              </div>
            </Section>
          )}

          <Section title="Tiện ích quanh đây (bán kính 500m)">
            <PoiRadar pois={poiQuery.data ?? []} loading={poiQuery.isLoading} />
          </Section>

          <Section title="Đánh giá & phản hồi">
            <ReviewSection listingId={listing.id} reviews={reviewsQuery.data ?? []} />
          </Section>

          <Section title="Phòng trọ tương tự">
            {similarQuery.isLoading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <ListingCardSkeleton />
                <ListingCardSkeleton />
              </div>
            ) : similarQuery.data && similarQuery.data.length > 0 ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {similarQuery.data.map((sim) => (
                  <ListingCard key={sim.id} listing={sim} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-fog">Không tìm thấy phòng trọ nào tương tự.</p>
            )}
          </Section>
        </div>

        {/* RIGHT sticky panel */}
        <aside className="lg:relative">
          <div className="space-y-4 lg:sticky lg:top-20">
            <div className="rounded-[15px] border border-line bg-white p-5">
              <div className="flex items-end justify-between gap-2">
                <div>
                  <p className="text-2xl font-semibold text-cobalt">
                    {formatCurrency(listing.price)}
                    <span className="text-sm font-normal text-fog">/tháng</span>
                  </p>
                  <p className="mt-0.5 inline-flex items-center gap-1 text-sm text-fog">
                    <Ruler className="size-4" /> {formatArea(listing.area)}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      useComparisonStore.getState().addListing(String(listing.id));
                      toast.success("Đã thêm vào danh sách so sánh");
                    }}
                    aria-label="So sánh"
                    title="Thêm vào so sánh"
                    className="rounded-full border border-line p-2 text-fog transition-colors hover:border-cobalt hover:text-cobalt"
                  >
                    <Scale className="size-5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => requireAuth(() => toggleFav.mutate(listing.id))}
                    aria-label="Lưu yêu thích"
                    className="rounded-full border border-line p-2 text-fog transition-colors hover:border-error hover:text-error"
                  >
                    <Heart className={cn("size-5", listing.favorite && "fill-error text-error")} />
                  </button>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <Button block onClick={onChat} loading={startChat.isPending}>
                  <MessageCircle className="size-4" /> Chat ngay
                </Button>
                <Button
                  block
                  variant="secondary"
                  onClick={() => requireAuth(() => setBookOpen(true))}
                  disabled={listing.status === "RENTED"}
                >
                  <CalendarDays className="size-4" /> Đặt lịch hẹn
                </Button>
              </div>
            </div>

            {listing.landlord && (
              <div className="rounded-[15px] border border-line bg-white p-5">
                <p className="mb-3 text-sm font-medium text-graphite">Thông tin chủ trọ</p>
                <LandlordSummaryCard landlord={listing.landlord} />
              </div>
            )}

            <button
              type="button"
              onClick={() => requireAuth(() => setReportOpen(true))}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-[8.8px] py-2 text-sm text-fog transition-colors hover:text-error"
            >
              <Flag className="size-4" /> Báo cáo tin này
            </button>
          </div>
        </aside>
      </div>

      <BookAppointmentModal
        open={bookOpen}
        onClose={() => setBookOpen(false)}
        listingId={listing.id}
        listingTitle={listing.title}
      />
      <ReportListingModal open={reportOpen} onClose={() => setReportOpen(false)} listingId={listing.id} />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-lg">{title}</h2>
      {children}
    </section>
  );
}

function Fact({ label, value, icon }: { label: string; value?: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-[8.8px] border border-line bg-white px-3 py-2.5">
      <p className="text-xs text-fog">{label}</p>
      <p className="mt-0.5 inline-flex items-center gap-1 text-sm font-medium text-ink">
        {icon} {value ?? "—"}
      </p>
    </div>
  );
}

function CostItem({ label, value, unit }: { label: string; value?: number; unit: string }) {
  return (
    <div className="rounded-[8.8px] border border-line bg-white px-3 py-2.5">
      <p className="text-xs text-fog">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-ink">
        {value != null ? (
          <>
            {formatVnd(value)}
            <span className="text-xs font-normal text-fog">{unit}</span>
          </>
        ) : (
          "—"
        )}
      </p>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6">
      <Skeleton className="aspect-[16/9] w-full rounded-[15px]" />
      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        <Skeleton className="h-64 w-full rounded-[15px]" />
      </div>
    </div>
  );
}
