import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { User, Users, Lock, ShieldCheck } from "lucide-react";
import { cn } from "@/shared/lib/cn";
import { useAuthStore } from "@/features/auth";
import { isLandlord } from "@/entities/user";
import { PersonalInfoPanel } from "./panels/PersonalInfoPanel";
import { WishlistPanel } from "./panels/WishlistPanel";
import { SavedFiltersPanel } from "./panels/SavedFiltersPanel";
import { VerificationPanel } from "./panels/VerificationPanel";
import { LifestylePanel } from "./panels/LifestylePanel";
import { SecurityPanel } from "./panels/SecurityPanel";

const TABS = [
  { id: "personal", label: "Thông tin cá nhân", icon: User },
  { id: "verification", label: "Xác minh chính chủ", icon: ShieldCheck, landlordOnly: true },
  { id: "lifestyle", label: "Hồ sơ thói quen (Ở ghép)", icon: Users },
  { id: "security", label: "Bảo mật", icon: Lock },
] as const;

export function ProfilePage() {
  const { user } = useAuthStore();
  const [params, setParams] = useSearchParams();
  const initial = params.get("tab") ?? "personal";
  const [tab, setTab] = useState(initial);

  const tabs = TABS.filter((t) => !("landlordOnly" in t && t.landlordOnly) || isLandlord(user));

  const select = (id: string) => {
    setTab(id);
    setParams({ tab: id }, { replace: true });
  };

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 sm:px-6">
      <h1 className="mb-6">Hồ sơ & tiện ích cá nhân</h1>

      <div className="grid gap-6 md:grid-cols-[220px_1fr]">
        {/* Sidebar */}
        <nav className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
          {tabs.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => select(t.id)}
                className={cn(
                  "inline-flex shrink-0 items-center gap-2.5 rounded-[8.8px] px-3.5 py-2.5 text-left text-sm font-medium transition-colors",
                  tab === t.id ? "bg-cobalt text-white" : "text-graphite hover:bg-white",
                )}
              >
                <Icon className="size-4" /> {t.label}
              </button>
            );
          })}
        </nav>

        {/* Content */}
        <div className="min-w-0">
          {tab === "personal" && <PersonalInfoPanel />}
          {tab === "verification" && <VerificationPanel />}
          {tab === "lifestyle" && <LifestylePanel />}
          {tab === "security" && <SecurityPanel />}
        </div>
      </div>
    </div>
  );
}
