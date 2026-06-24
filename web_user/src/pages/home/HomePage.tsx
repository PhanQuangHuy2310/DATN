import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShieldCheck, MapPinned, Users } from "lucide-react";
import { ListingCard, ListingCardSkeleton } from "@/entities/listing";
import { EmptyState, SplitText } from "@/shared/ui";
import { config } from "@/shared/config";
import gsap from "gsap";
import {
  QuickSearchForm,
  DistrictQuickLinks,
} from "@/features/search-listings";
import { useLatestListings, useRoommateListings } from "./hooks";

export function HomePage() {
  useEffect(() => {
    document.title = `${config.brandName} — Tìm phòng trọ minh bạch, không qua môi giới`;
  }, []);

  return (
    <div>
      <Hero />
      <RoommateSection />
      <LatestSection />
    </div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-line bg-gradient-to-b from-cobalt-soft/60 to-paper">
      <div className="mx-auto max-w-[1280px] px-4 py-16 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-balance">
            Tìm kiếm không gian sống{" "}
            <span className="text-cobalt">minh bạch</span> — không qua môi giới
          </h1>
          <SplitText
            text="Kết nối trực tiếp với chủ trọ. Lọc theo giá, diện tích, ngõ ngách và tìm phòng quanh điểm giữa nơi học và nơi làm của bạn."
            className="mx-auto mt-4 max-w-xl text-fog text-base"
            delay={20}
            duration={1}
            splitType="words"
          />
        </div>

        <div className="mx-auto mt-8 max-w-3xl">
          <QuickSearchForm />
          <div className="mt-4 flex flex-col items-center gap-3">
            <span className="text-xs text-fog">Khu vực phổ biến</span>
            <DistrictQuickLinks />
          </div>
        </div>

        <div className="mx-auto mt-12 grid max-w-3xl gap-4 sm:grid-cols-3">
          <Highlight icon={<ShieldCheck className="size-5" />} title="Chủ trọ xác minh" desc="Huy hiệu chính chủ, hạn chế tin ảo." />
          <Highlight icon={<MapPinned className="size-5" />} title="Tìm theo điểm giữa" desc="Cân bằng quãng đường tới mọi nơi bạn cần." />
          <Highlight icon={<Users className="size-5" />} title="Ở ghép dễ dàng" desc="Tìm bạn cùng phòng phù hợp ngân sách." />
        </div>
      </div>
    </section>
  );
}

function Highlight({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="flex items-start gap-3 rounded-[8.8px] border border-line bg-white/70 p-4">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-[8.8px] bg-cobalt-soft text-cobalt">
        {icon}
      </span>
      <div>
        <p className="text-sm font-medium text-ink">{title}</p>
        <p className="text-xs text-fog">{desc}</p>
      </div>
    </div>
  );
}

function SectionHeader({ title, to, cta }: { title: string; to: string; cta: string }) {
  return (
    <div className="mb-5 flex items-end justify-between gap-4">
      <h2>{title}</h2>
      <Link to={to} className="inline-flex items-center gap-1 text-sm font-medium text-cobalt hover:underline">
        {cta} <ArrowRight className="size-4" />
      </Link>
    </div>
  );
}

function RoommateSection() {
  const { data, isLoading } = useRoommateListings();
  const items = data ?? [];
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoading && items.length > 0 && containerRef.current) {
      gsap.fromTo(
        containerRef.current.children,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, stagger: 0.1, duration: 0.5, ease: "power2.out", scrollTrigger: containerRef.current }
      );
    }
  }, [isLoading, items]);

  if (!isLoading && items.length === 0) return null;

  return (
    <section className="mx-auto max-w-[1280px] px-4 py-12 sm:px-6">
      <SectionHeader title="Chuyên mục ở ghép" to="/search?type=ROOMMATE" cta="Xem tất cả" />
      <div ref={containerRef} className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => <ListingCardSkeleton key={i} />)
          : items.slice(0, 4).map((l) => <ListingCard key={l.id} listing={l} />)}
      </div>
    </section>
  );
}

function LatestSection() {
  const { data, isLoading } = useLatestListings();
  const items = data ?? [];
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoading && items.length > 0 && containerRef.current) {
      gsap.fromTo(
        containerRef.current.children,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, stagger: 0.1, duration: 0.5, ease: "power2.out", scrollTrigger: containerRef.current }
      );
    }
  }, [isLoading, items]);

  return (
    <section className="mx-auto max-w-[1280px] px-4 pb-16 sm:px-6">
      <SectionHeader title="Tin đăng mới nhất" to="/search" cta="Khám phá bản đồ" />
      {!isLoading && items.length === 0 ? (
        <EmptyState
          title="Chưa có tin đăng nào"
          description="Hãy là người đầu tiên đăng tin phòng trọ trên nền tảng!"
        />
      ) : (
        <div ref={containerRef} className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {isLoading
            ? Array.from({ length: 8 }).map((_, i) => <ListingCardSkeleton key={i} />)
            : items.map((l) => <ListingCard key={l.id} listing={l} />)}
        </div>
      )}
    </section>
  );
}
