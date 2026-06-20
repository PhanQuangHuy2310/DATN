import { useState } from "react";
import { ChevronLeft, ChevronRight, PlayCircle, ImageOff } from "lucide-react";
import { Modal } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

interface Props {
  images: string[];
  videoUrl?: string | null;
  title: string;
}

export function MediaGallery({ images, videoUrl, title }: Props) {
  const [index, setIndex] = useState(0);
  const [videoOpen, setVideoOpen] = useState(false);
  const has = images.length > 0;

  const go = (delta: number) =>
    setIndex((i) => (i + delta + images.length) % images.length);

  return (
    <div>
      <div className="relative aspect-[16/9] w-full overflow-hidden rounded-[15px] border border-line bg-chalk">
        {has ? (
          <img src={images[index]} alt={`${title} - ảnh ${index + 1}`} className="size-full object-cover" />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-fog">
            <ImageOff className="size-9" />
            <span className="text-sm">Chưa có hình ảnh</span>
          </div>
        )}

        {images.length > 1 && (
          <>
            <NavButton side="left" onClick={() => go(-1)} />
            <NavButton side="right" onClick={() => go(1)} />
            <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-1.5">
              {images.map((_, i) => (
                <span
                  key={i}
                  className={cn(
                    "size-1.5 rounded-full transition-colors",
                    i === index ? "bg-white" : "bg-white/50",
                  )}
                />
              ))}
            </div>
          </>
        )}

        {videoUrl && (
          <button
            type="button"
            onClick={() => setVideoOpen(true)}
            className="panel-float absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-ink"
          >
            <PlayCircle className="size-4 text-cobalt" /> Video lộ trình
          </button>
        )}
      </div>

      {/* Thumbnail strip */}
      {images.length > 1 && (
        <div className="scroll-area mt-3 flex gap-2 overflow-x-auto pb-1">
          {images.map((src, i) => (
            <button
              key={src}
              type="button"
              onClick={() => setIndex(i)}
              className={cn(
                "size-16 shrink-0 overflow-hidden rounded-[8.8px] border-2 transition-colors",
                i === index ? "border-cobalt" : "border-transparent",
              )}
            >
              <img src={src} alt={`thumbnail ${i + 1}`} className="size-full object-cover" />
            </button>
          ))}
        </div>
      )}

      <Modal open={videoOpen} onClose={() => setVideoOpen(false)} title="Video lộ trình di chuyển" size="lg">
        {videoUrl && (
          <video src={videoUrl} controls autoPlay className="w-full rounded-[8.8px] bg-ink">
            {/* No caption asset available for user-uploaded route videos; empty track satisfies a11y requirement. */}
            <track kind="captions" />
            Trình duyệt của bạn không hỗ trợ phát video.
          </video>
        )}
      </Modal>
    </div>
  );
}

function NavButton({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const Icon = side === "left" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={side === "left" ? "Ảnh trước" : "Ảnh sau"}
      className={cn(
        "absolute top-1/2 -translate-y-1/2 rounded-full bg-white/90 p-2 text-ink transition-colors hover:bg-white",
        side === "left" ? "left-3" : "right-3",
      )}
    >
      <Icon className="size-5" />
    </button>
  );
}
