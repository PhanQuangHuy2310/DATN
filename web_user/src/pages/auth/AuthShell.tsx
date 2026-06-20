import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { config } from "@/shared/config";

// Computed once at module load (client-only SPA, no hydration; constant per session).
const CURRENT_YEAR = new Date().getFullYear();

/** Shared two-pane shell for the standalone /login and /register screens. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* Brand / illustration pane */}
      <div className="relative hidden flex-col justify-between bg-cobalt p-12 text-white lg:flex">
        <Link to="/" className="flex items-center gap-2">
          <span className="size-7 rounded-full bg-white" />
          <span className="text-lg font-semibold">{config.brandName}</span>
        </Link>
        <div className="space-y-3">
          <h1 className="text-white">Tìm kiếm không gian sống minh bạch</h1>
          <p className="max-w-md text-white/80">
            Kết nối trực tiếp chủ trọ và khách thuê — không qua môi giới, không phí ẩn.
          </p>
        </div>
        <p className="text-sm text-white/60">© {CURRENT_YEAR} {config.brandName}</p>
      </div>

      {/* Form pane */}
      <div className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-8 flex items-center gap-2 lg:hidden">
            <span className="size-7 rounded-full bg-cobalt" />
            <span className="text-lg font-semibold text-ink">{config.brandName}</span>
          </Link>
          <h2 className="mb-1">{title}</h2>
          {subtitle && <p className="mb-6 text-sm text-fog">{subtitle}</p>}
          {children}
          {footer && <div className="mt-6 text-center text-sm text-fog">{footer}</div>}
        </div>
      </div>
    </div>
  );
}
