import { Link } from "react-router-dom";
import { Heart } from "lucide-react";
import { Button, EmptyState } from "@/shared/ui";
import { ListingCard, ListingCardSkeleton } from "@/entities/listing";
import { useWishlist, useToggleWishlist } from "@/features/wishlist";

export function WishlistPanel() {
  const { data, isLoading } = useWishlist();
  const toggle = useToggleWishlist();
  const items = data ?? [];

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => <ListingCardSkeleton key={i} />)}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        icon={<Heart className="size-7" />}
        title="Chưa có tin yêu thích"
        description="Thả tim các tin đăng để lưu lại xem nhanh sau này."
        action={
          <Link to="/search">
            <Button>Khám phá phòng trọ</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
      {items.map((l) => (
        <ListingCard
          key={l.id}
          listing={{ ...l, favorite: true }}
          onToggleFavorite={(id) => toggle.mutate(id)}
        />
      ))}
    </div>
  );
}
