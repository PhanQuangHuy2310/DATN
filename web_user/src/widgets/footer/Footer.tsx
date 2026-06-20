import { Link } from "react-router-dom";
import { config } from "@/shared/config";

// Computed once at module load — a client-only SPA has no hydration step,
// and the year is constant for the session.
const CURRENT_YEAR = new Date().getFullYear();

const COLUMNS = [
  {
    title: "Khám phá",
    links: [
      { to: "/search", label: "Tìm phòng trọ" },
      { to: "/search?type=ROOMMATE", label: "Tìm bạn ở ghép" },
      { to: "/listings/create", label: "Đăng tin" },
    ],
  },
  {
    title: "Hỗ trợ",
    links: [
      { to: "#", label: "Câu hỏi thường gặp" },
      { to: "#", label: "Hướng dẫn sử dụng" },
      { to: "#", label: "Báo cáo vi phạm" },
    ],
  },
  {
    title: "Về chúng tôi",
    links: [
      { to: "#", label: "Giới thiệu" },
      { to: "#", label: "Điều khoản" },
      { to: "#", label: "Bảo mật" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-chalk/40">
      <div className="mx-auto grid max-w-[1280px] gap-8 px-4 py-12 sm:px-6 md:grid-cols-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="size-6 rounded-full bg-cobalt" />
            <span className="text-base font-semibold text-ink">{config.brandName}</span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-fog">
            Tìm kiếm không gian sống minh bạch — không qua môi giới.
          </p>
        </div>
        {COLUMNS.map((col) => (
          <div key={col.title}>
            <h4 className="text-sm font-semibold text-ink">{col.title}</h4>
            <ul className="mt-3 space-y-2">
              {col.links.map((l) => (
                <li key={l.label}>
                  <Link to={l.to} className="text-sm text-fog transition-colors hover:text-cobalt">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-line py-5 text-center text-xs text-fog">
        © {CURRENT_YEAR} {config.brandName}. Đồ án tốt nghiệp.
      </div>
    </footer>
  );
}
