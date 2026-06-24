import { useState } from "react";
import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  Plus,
  Menu,
  X,
  MessageCircle,
  CalendarDays,
  Heart,
  LayoutDashboard,
  LogOut,
  UserRound,
  ChevronDown,
} from "lucide-react";
import { Avatar, Button } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { useClickOutside } from "@/shared/lib";
import { useAuthStore } from "@/features/auth/authStore";
import { isLandlord } from "@/entities/user";
import { NotificationBell } from "./NotificationBell";
import { PillNav } from "./PillNav";

const logoSvg = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36"><circle cx="18" cy="18" r="18" fill="%230066FF"/><text x="18" y="23" font-size="16" text-anchor="middle" fill="white" font-weight="bold" font-family="sans-serif">NT</text></svg>`;

const NAV = [
  { to: "/", label: "Trang chủ", end: true },
  { to: "/search", label: "Tìm phòng" },
  { to: "/roommates", label: "Ở ghép" },
];

export function Header() {
  const { isAuthenticated, user } = useAuthStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center gap-4 px-4 sm:px-6">
        <PillNav
          logo={logoSvg}
          logoAlt="Nhà Trọ 360"
          items={NAV.map((n) => ({ label: n.label, href: n.to }))}
          activeHref={location.pathname + location.search}
          baseColor="transparent"
          pillColor="#ffffff"
          hoveredPillTextColor="#ffffff"
          pillTextColor="#120F17"
        />

        <div className="ml-auto flex items-center gap-2">
          <Link to="/listings/create" className="hidden sm:block">
            <Button size="sm">
              <Plus className="size-4" /> Đăng tin
            </Button>
          </Link>

          {isAuthenticated && user ? (
            <>
              <NotificationBell />
              <UserMenu />
            </>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  Đăng nhập
                </Button>
              </Link>
              <Link to="/register">
                <Button variant="secondary" size="sm">
                  Đăng ký
                </Button>
              </Link>
            </div>
          )}

          <button
            type="button"
            className="rounded-[8.8px] p-2 text-graphite hover:bg-white md:hidden"
            aria-label="Mở menu"
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {mobileOpen && <MobileMenu onClose={() => setMobileOpen(false)} />}
    </header>
  );
}

function UserMenu() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));
  if (!user) return null;

  const links = [
    { to: "/profile", label: "Hồ sơ cá nhân", icon: UserRound },
    { to: "/appointments", label: "Lịch hẹn", icon: CalendarDays },
    { to: "/chat", label: "Tin nhắn", icon: MessageCircle },
    { to: "/profile?tab=wishlist", label: "Tin yêu thích", icon: Heart },
  ];
  if (isLandlord(user))
    links.push({ to: "/landlord/dashboard", label: "Dashboard", icon: LayoutDashboard });

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        id="user-menu"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-full p-0.5 transition-colors hover:bg-white"
      >
        <Avatar src={user.avatarUrl} name={user.name} size={34} />
        <ChevronDown className="size-4 text-fog" />
      </button>

      {open && (
        <div className="panel-float absolute right-0 mt-2 w-56 rounded-[8.8px] p-1">
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium text-ink">{user.name}</p>
            <p className="truncate text-xs text-fog">{user.email}</p>
          </div>
          <div className="my-1 border-t border-line" />
          {links.map(({ to, label, icon: Icon }) => (
            <Link
              key={label}
              to={to}
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 rounded-[6px] px-3 py-2 text-sm text-graphite transition-colors hover:bg-paper"
            >
              <Icon className="size-4 text-fog" /> {label}
            </Link>
          ))}
          <div className="my-1 border-t border-line" />
          <button
            type="button"
            onClick={() => {
              logout();
              setOpen(false);
              navigate("/");
            }}
            className="flex w-full items-center gap-2.5 rounded-[6px] px-3 py-2 text-sm text-error transition-colors hover:bg-error-soft"
          >
            <LogOut className="size-4" /> Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}

function MobileMenu({ onClose }: { onClose: () => void }) {
  const { isAuthenticated } = useAuthStore();
  return (
    <div className="border-t border-line bg-paper px-4 py-3 md:hidden">
      <nav className="flex flex-col gap-1">
        {NAV.map((n) => (
          <NavLink
            key={n.label}
            to={n.to}
            end={n.end}
            onClick={onClose}
            className={({ isActive }) =>
              cn(
                "rounded-[8.8px] px-3 py-2.5 text-sm font-medium",
                isActive ? "bg-white text-cobalt" : "text-graphite",
              )
            }
          >
            {n.label}
          </NavLink>
        ))}
        <Link to="/listings/create" onClick={onClose} className="mt-1">
          <Button block size="sm">
            <Plus className="size-4" /> Đăng tin
          </Button>
        </Link>
        {!isAuthenticated && (
          <div className="mt-1 grid grid-cols-2 gap-2">
            <Link to="/login" onClick={onClose}>
              <Button block variant="ghost" size="sm">
                Đăng nhập
              </Button>
            </Link>
            <Link to="/register" onClick={onClose}>
              <Button block variant="secondary" size="sm">
                Đăng ký
              </Button>
            </Link>
          </div>
        )}
      </nav>
    </div>
  );
}
