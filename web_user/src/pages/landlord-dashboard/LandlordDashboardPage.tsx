import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Crown, Sparkles } from "lucide-react";
import { Badge, Button, Card, Modal, EmptyState, Skeleton, useToast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { getErrorMessage } from "@/shared/api";
import { useAuthStore } from "@/features/auth";
import { useMyListings, useCreatePayment } from "@/features/manage-listing/hooks";
import { ManageListingRow } from "@/features/manage-listing/ManageListingRow";
import { useLandlordStats } from "./hooks";

const PerformanceChart = lazy(() => import("./PerformanceChart"));

export function LandlordDashboardPage() {
  const { user } = useAuthStore();
  const stats = useLandlordStats();
  const listings = useMyListings();
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  const isPro = (stats.data?.plan ?? user?.plan) === "PRO";
  const active = stats.data?.activeCount ?? listings.data?.filter((l) => l.status === "AVAILABLE").length ?? 0;
  const quota = stats.data?.quota ?? 5;

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl">Dashboard quản lý chủ trọ</h1>
        <Link to="/listings/create">
          <Button>
            <Plus className="size-4" /> Đăng tin mới
          </Button>
        </Link>
      </div>

      {/* Quota block */}
      <Card padded className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <p className="text-sm text-fog">Gói hiện tại</p>
              <Badge tone={isPro ? "warning" : "neutral"}>
                {isPro ? <><Crown className="size-3.5" /> GÓI PRO</> : "GÓI THƯỜNG"}
              </Badge>
            </div>
            <p className="mt-1 text-lg font-semibold text-ink">
              {isPro ? "Đăng tin không giới hạn" : `Đăng tối đa ${quota} tin hoạt động`}
            </p>
            {!isPro && (
              <p className="mt-0.5 text-sm text-fog">
                Đã dùng <span className="font-semibold text-ink">{active}/{quota}</span> tin hoạt động.
              </p>
            )}
          </div>
          {!isPro && (
            <Button onClick={() => setUpgradeOpen(true)}>
              <Sparkles className="size-4" /> Nâng cấp PRO không giới hạn
            </Button>
          )}
        </div>

        {!isPro && (
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-chalk">
            <div
              className="h-full rounded-full bg-cobalt transition-all"
              style={{ width: `${Math.min(100, (active / Math.max(quota, 1)) * 100)}%` }}
            />
          </div>
        )}
      </Card>

      {/* Performance chart */}
      <Card padded className="mb-6">
        <h2 className="mb-4 text-lg">Phân tích hiệu năng tin đăng</h2>
        {stats.isLoading ? (
          <Skeleton className="h-72 w-full" />
        ) : (stats.data?.daily.length ?? 0) === 0 ? (
          <EmptyState title="Chưa có dữ liệu thống kê" description="Số liệu sẽ hiển thị khi tin đăng của bạn bắt đầu có lượt tương tác." />
        ) : (
          <div className="h-72 w-full">
            <Suspense fallback={<Skeleton className="h-72 w-full" />}>
              <PerformanceChart data={stats.data!.daily} />
            </Suspense>
          </div>
        )}
      </Card>

      {/* My listings */}
      <h2 className="mb-3 text-lg">Tin đăng của tôi</h2>
      {listings.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      ) : (listings.data?.length ?? 0) === 0 ? (
        <EmptyState
          title="Bạn chưa đăng tin nào"
          description="Đăng tin đầu tiên để bắt đầu cho thuê phòng trọ."
          action={
            <Link to="/listings/create">
              <Button>Đăng tin ngay</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {listings.data!.map((l) => (
            <ManageListingRow key={l.id} listing={l} />
          ))}
        </div>
      )}

      <UpgradeModal open={upgradeOpen} onClose={() => setUpgradeOpen(false)} />
    </div>
  );
}

function UpgradeModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const createPayment = useCreatePayment();
  const [provider, setProvider] = useState<"MOMO" | "ZALOPAY">("MOMO");

  const pay = () =>
    createPayment.mutate(
      { plan: "PRO", provider },
      {
        onSuccess: (res) => {
          // Redirect to the sandbox payment gateway.
          window.location.href = res.paymentUrl;
        },
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nâng cấp gói PRO"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Để sau</Button>
          <Button onClick={pay} loading={createPayment.isPending}>Thanh toán ngay</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="rounded-[8.8px] bg-cobalt-soft p-4">
          <p className="font-medium text-ink">Gói PRO — Đăng tin không giới hạn</p>
          <p className="mt-1 text-sm text-fog">Đăng không giới hạn tin hoạt động, ưu tiên hiển thị và đẩy tin miễn phí.</p>
        </div>
        <div>
          <p className="mb-2 text-[13px] font-medium text-graphite">Chọn cổng thanh toán (sandbox)</p>
          <div className="grid grid-cols-2 gap-2">
            {(["MOMO", "ZALOPAY"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setProvider(p)}
                className={cn(
                  "rounded-[8.8px] border px-4 py-3 text-sm font-medium transition-colors",
                  provider === p ? "border-cobalt bg-cobalt-soft text-cobalt" : "border-line text-graphite hover:border-cobalt",
                )}
              >
                {p === "MOMO" ? "MoMo" : "ZaloPay"}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}
