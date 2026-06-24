import { useState, useEffect, useRef } from "react";
import { RadarChart, LifestyleData } from "@/shared/ui/RadarChart";
import { Button, Badge } from "@/shared/ui";
import { apiClient } from "@/shared/api";
import { MapPin, Wallet, Users } from "lucide-react";
import { formatVnd } from "@/shared/lib";
import gsap from "gsap";

interface RoommatePost {
  id: string;
  user: { fullName: string; avatarUrl?: string };
  lifestyle: LifestyleData;
  postType: "HAVE_ROOM" | "NEED_ROOM";
  title: string;
  description: string;
  budget: number;
}

export function RoommatePage() {
  const [posts, setPosts] = useState<RoommatePost[]>([]);
  const [myLifestyle, setMyLifestyle] = useState<LifestyleData>();
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([
      apiClient.get<LifestyleData>("/api/roommates/lifestyle").catch(() => ({ data: undefined })),
      apiClient.get<{content: RoommatePost[]}>("/api/roommates/posts").catch(() => ({ data: { content: [] } }))
    ]).then(([lifeRes, postRes]) => {
      if (lifeRes.data) setMyLifestyle(lifeRes.data);
      if (postRes.data) setPosts(postRes.data.content);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!loading && posts.length > 0 && containerRef.current) {
      gsap.fromTo(
        containerRef.current.children,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, stagger: 0.1, duration: 0.6, ease: "power2.out" }
      );
    }
  }, [loading, posts]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between mb-8 border-b border-line pb-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">Tìm người ở ghép</h1>
          <p className="text-fog mt-1">Khám phá các mảnh ghép phù hợp với thói quen sinh hoạt của bạn.</p>
        </div>
        <Button className="shadow-sm hover:shadow-md transition-shadow"><Users className="w-4 h-4 mr-2" /> Đăng tin tìm người</Button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Array.from({length: 4}).map((_, i) => (
            <div key={i} className="h-64 rounded-xl skeleton" />
          ))}
        </div>
      ) : (
        <div ref={containerRef} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {posts.map((post) => (
            <div key={post.id} className="border border-line rounded-[12px] p-6 bg-white/80 backdrop-blur-sm card-hover flex flex-col">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <img src={post.user.avatarUrl || "/avatar-placeholder.png"} alt="" className="w-10 h-10 rounded-full object-cover" />
                <div>
                  <h3 className="font-medium">{post.user.fullName}</h3>
                  <Badge tone={post.postType === "HAVE_ROOM" ? "success" : "neutral"} className="mt-1">
                    {post.postType === "HAVE_ROOM" ? "Đã có phòng" : "Đang tìm phòng"}
                  </Badge>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500 flex items-center gap-1 justify-end"><Wallet className="w-4 h-4"/> Ngân sách</p>
                <p className="font-semibold text-blue-600">{formatVnd(post.budget)}</p>
              </div>
            </div>

            <h4 className="font-medium text-lg mb-2">{post.title}</h4>
            <p className="text-sm text-gray-600 line-clamp-2 mb-4">{post.description}</p>

            <div className="mt-auto pt-4 border-t border-gray-100 flex items-center gap-4">
              <div className="w-32 h-32 shrink-0">
                <RadarChart myLifestyle={myLifestyle} otherLifestyle={post.lifestyle} />
              </div>
              <div className="flex-1 text-sm text-gray-500">
                <p>Biểu đồ so sánh thói quen sinh hoạt giữa bạn (Tím) và {post.user.fullName} (Xanh).</p>
                <Button variant="outline" className="mt-3 w-full">Nhắn tin ngay</Button>
              </div>
            </div>
          </div>
        ))}

        {posts.length === 0 && (
          <div className="col-span-full py-16 flex flex-col items-center justify-center text-center">
            <div className="size-16 bg-cobalt-soft text-cobalt rounded-full flex items-center justify-center mb-4">
              <Users className="size-8" />
            </div>
            <h3 className="text-lg font-medium text-ink">Chưa có tin đăng nào</h3>
            <p className="text-fog mt-1 max-w-sm">Hãy là người đầu tiên đăng tin tìm người ở ghép để tìm được bạn chung phòng ưng ý nhé.</p>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
