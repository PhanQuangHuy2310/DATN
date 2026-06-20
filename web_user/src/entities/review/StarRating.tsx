import { useState } from "react";
import { Star } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export interface StarRatingProps {
  value: number;
  onChange?: (value: number) => void;
  size?: number;
  readOnly?: boolean;
  className?: string;
}

export function StarRating({ value, onChange, size = 20, readOnly, className }: StarRatingProps) {
  const [hover, setHover] = useState(0);
  const interactive = !readOnly && !!onChange;
  const display = hover || value;

  return (
    <div className={cn("inline-flex items-center gap-0.5", className)} role="radiogroup">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={!interactive}
          aria-label={`${star} sao`}
          onMouseEnter={() => interactive && setHover(star)}
          onMouseLeave={() => interactive && setHover(0)}
          onClick={() => onChange?.(star)}
          className={cn("transition-transform", interactive && "hover:scale-110")}
        >
          <Star
            style={{ width: size, height: size }}
            className={cn(
              star <= display ? "fill-warning text-warning" : "fill-transparent text-ash",
            )}
          />
        </button>
      ))}
    </div>
  );
}
