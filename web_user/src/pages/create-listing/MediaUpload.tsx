import { useRef, useState } from "react";
import { UploadCloud, X, Film, Loader2 } from "lucide-react";
import { useToast } from "@/shared/ui";
import { uploadToStorage, getErrorMessage } from "@/shared/api";
import { cn } from "@/shared/lib/cn";

const MAX_VIDEO_MB = 30;

interface Props {
  images: string[];
  videoUrl: string | null;
  onImagesChange: (urls: string[]) => void;
  onVideoChange: (url: string | null) => void;
}

export function MediaUpload({ images, videoUrl, onImagesChange, onVideoChange }: Props) {
  const toast = useToast();
  const imgInput = useRef<HTMLInputElement>(null);
  const vidInput = useRef<HTMLInputElement>(null);
  const [uploadingImg, setUploadingImg] = useState(false);
  const [uploadingVid, setUploadingVid] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const uploadImages = async (files: FileList | File[]) => {
    const list = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (list.length === 0) return;
    setUploadingImg(true);
    try {
      const urls = await Promise.all(list.map((f) => uploadToStorage(f, "listings/images")));
      onImagesChange([...images, ...urls]);
    } catch (e) {
      toast.error(getErrorMessage(e, "Tải ảnh thất bại."));
    } finally {
      setUploadingImg(false);
    }
  };

  const uploadVideo = async (file: File) => {
    if (file.size > MAX_VIDEO_MB * 1024 * 1024) {
      toast.error(`Video vượt quá ${MAX_VIDEO_MB}MB.`);
      return;
    }
    setUploadingVid(true);
    try {
      const url = await uploadToStorage(file, "listings/videos");
      onVideoChange(url);
    } catch (e) {
      toast.error(getErrorMessage(e, "Tải video thất bại."));
    } finally {
      setUploadingVid(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Image drag & drop — a <label> natively forwards click/keyboard to its
          nested file input, so no role/tabIndex/key handlers are needed. */}
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          uploadImages(e.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[8.8px] border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragOver ? "border-cobalt bg-cobalt-soft/40" : "border-line hover:border-cobalt",
        )}
      >
        {uploadingImg ? (
          <Loader2 className="size-7 animate-spin text-cobalt" />
        ) : (
          <UploadCloud className="size-7 text-fog" />
        )}
        <p className="text-sm font-medium text-ink">Kéo thả hoặc bấm để tải ảnh thực tế</p>
        <p className="text-xs text-fog">Tối thiểu 3 ảnh — JPG, PNG</p>
        <input
          ref={imgInput}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          aria-label="Chọn ảnh thực tế để tải lên"
          onChange={(e) => e.target.files && uploadImages(e.target.files)}
        />
      </label>

      {images.length > 0 && (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {images.map((url, i) => (
            <div key={url} className="group relative aspect-square overflow-hidden rounded-[8.8px] border border-line">
              <img src={url} alt={`Ảnh ${i + 1}`} className="size-full object-cover" />
              <button
                type="button"
                onClick={() => onImagesChange(images.filter((u) => u !== url))}
                aria-label="Xóa ảnh"
                className="absolute right-1 top-1 rounded-full bg-ink/70 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100"
              >
                <X className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Video */}
      <div>
        <p className="mb-2 text-[13px] font-medium text-graphite">Video lộ trình (tùy chọn, tối đa {MAX_VIDEO_MB}MB)</p>
        {videoUrl ? (
          <div className="flex items-center gap-3 rounded-[8.8px] border border-line bg-white p-3">
            <Film className="size-5 text-cobalt" />
            <span className="flex-1 truncate text-sm text-graphite">Đã tải video lộ trình</span>
            <button type="button" onClick={() => onVideoChange(null)} aria-label="Xóa video" className="text-fog hover:text-error">
              <X className="size-4" />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => vidInput.current?.click()}
            className="inline-flex items-center gap-2 rounded-[8.8px] border border-line px-4 py-2 text-sm text-graphite transition-colors hover:border-cobalt"
          >
            {uploadingVid ? <Loader2 className="size-4 animate-spin" /> : <Film className="size-4" />}
            Tải video lộ trình (MP4)
          </button>
        )}
        <input
          ref={vidInput}
          type="file"
          accept="video/mp4"
          hidden
          aria-label="Chọn video lộ trình để tải lên"
          onChange={(e) => e.target.files?.[0] && uploadVideo(e.target.files[0])}
        />
      </div>
    </div>
  );
}
