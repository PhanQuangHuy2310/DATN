import { BadgeCheck, Star } from "lucide-react";
import { Avatar } from "@/shared/ui";
import type { UserSummary } from "./model";

export function LandlordSummaryCard({ landlord }: { landlord: UserSummary }) {
  return (
    <div className="flex items-center gap-3">
      <Avatar src={landlord.avatarUrl} name={landlord.name} size={48} />
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="truncate font-medium text-ink">{landlord.name}</p>
          {landlord.verified && <BadgeCheck className="size-4 shrink-0 text-cobalt" />}
        </div>
        <div className="mt-0.5 flex items-center gap-3 text-xs text-fog">
          {landlord.reputationScore != null && (
            <span className="inline-flex items-center gap-1">
              <Star className="size-3.5 fill-warning text-warning" />
              {landlord.reputationScore.toFixed(1)}/5
            </span>
          )}
          {landlord.verified && <span className="text-success">Chủ trọ uy tín</span>}
        </div>
      </div>
    </div>
  );
}
