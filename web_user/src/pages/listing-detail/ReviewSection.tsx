import { useState } from "react";
import { Avatar, Button, Textarea, useToast } from "@/shared/ui";
import { StarRating } from "@/entities/review";
import { getErrorMessage } from "@/shared/api";
import { formatRelative } from "@/shared/lib";
import { useAuthStore } from "@/features/auth";
import type { Review } from "@/entities/review";
import { useSubmitReview } from "./hooks";

/** Lightweight client-side anti-toxic guard (backend re-checks authoritatively). */
const TOXIC_WORDS = ["đm", "dm", "vcl", "vl", "đụ", "lồn", "cặc", "địt", "ngu", "óc chó"];
const isToxic = (text: string) => {
  const lower = text.toLowerCase();
  return TOXIC_WORDS.some((w) => lower.includes(w));
};

export function ReviewSection({ listingId, reviews }: { listingId: number; reviews: Review[] }) {
  const { isAuthenticated, user } = useAuthStore();
  const toast = useToast();
  const submit = useSubmitReview(listingId);

  const [rating, setRating] = useState(5);
  const [content, setContent] = useState("");
  const [shake, setShake] = useState(false);

  const toxic = content.length > 0 && isToxic(content);

  const onSubmit = () => {
    if (toxic) {
      setShake(true);
      window.setTimeout(() => setShake(false), 400);
      return;
    }
    if (!content.trim()) return;
    submit.mutate(
      { rating, content: content.trim() },
      {
        onSuccess: () => {
          toast.success("Cảm ơn đánh giá của bạn!");
          setContent("");
          setRating(5);
        },
        onError: (e) => toast.error(getErrorMessage(e, "Chỉ khách đã xem phòng mới được đánh giá.")),
      },
    );
  };

  return (
    <div className="space-y-5">
      {isAuthenticated && user?.role === "TENANT" && (
        <div className="rounded-[8.8px] border border-line bg-white p-4">
          <p className="mb-2 text-sm font-medium text-graphite">Viết đánh giá của bạn</p>
          <StarRating value={rating} onChange={setRating} />
          <div className="mt-3">
            <Textarea
              name="review"
              placeholder="Chia sẻ trải nghiệm thực tế của bạn về phòng trọ này…"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              shake={shake}
              error={toxic ? "Đánh giá chứa từ ngữ chưa chuẩn mực, vui lòng chỉnh sửa trước khi gửi." : undefined}
            />
          </div>
          <div className="mt-3 flex justify-end">
            <Button onClick={onSubmit} loading={submit.isPending} disabled={!content.trim() || toxic}>
              Gửi đánh giá
            </Button>
          </div>
        </div>
      )}

      {reviews.length === 0 ? (
        <p className="text-sm text-fog">Chưa có đánh giá nào cho phòng trọ này.</p>
      ) : (
        <div className="space-y-4">
          {reviews.map((r) => (
            <div key={r.id} className="rounded-[8.8px] border border-line bg-white p-4">
              <div className="flex items-start gap-3">
                <Avatar src={r.author.avatarUrl} name={r.author.name} size={40} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-ink">{r.author.name}</p>
                    <span className="text-xs text-fog">{formatRelative(r.createdAt)}</span>
                  </div>
                  <StarRating value={r.rating} readOnly size={14} className="mt-0.5" />
                  <p className="mt-2 whitespace-pre-wrap text-sm text-graphite">{r.content}</p>
                </div>
              </div>

              {r.landlordReply && (
                <div className="mt-3 ml-12 rounded-[8.8px] border-l-2 border-cobalt bg-paper px-3 py-2">
                  <p className="text-xs font-medium text-cobalt">Phản hồi từ chủ trọ</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-graphite">{r.landlordReply.content}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
