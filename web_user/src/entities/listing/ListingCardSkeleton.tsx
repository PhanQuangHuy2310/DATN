import { Skeleton } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

export function ListingCardSkeleton({ layout = "grid" }: { layout?: "grid" | "list" }) {
  const horizontal = layout === "list";
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[8.8px] border border-line bg-white",
        horizontal ? "flex gap-3" : "",
      )}
    >
      <Skeleton className={horizontal ? "h-28 w-40 shrink-0 rounded-none" : "aspect-[4/3] w-full rounded-none"} />
      <div className={cn("flex flex-1 flex-col gap-2", horizontal ? "py-3 pr-3" : "p-3")}>
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-5 w-1/3" />
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  );
}
