import { useRef, useState } from "react";
import { ImagePlus, SendHorizontal, X, Loader2 } from "lucide-react";
import { useToast } from "@/shared/ui";
import { getErrorMessage, uploadToStorage } from "@/shared/api";

interface Props {
  disabled?: boolean;
  onSend: (payload: { content: string; imageUrl?: string }) => void;
}

export function MessageComposer({ disabled, onSend }: Props) {
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const attach = async (file: File) => {
    setUploading(true);
    try {
      const url = await uploadToStorage(file, "chat");
      setImage(url);
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  const send = () => {
    const content = text.trim();
    if (!content && !image) return;
    onSend({ content, imageUrl: image ?? undefined });
    setText("");
    setImage(null);
  };

  return (
    <div className="border-t border-line bg-paper p-3">
      {image && (
        <div className="relative mb-2 inline-block">
          <img src={image} alt="Ảnh đính kèm" className="h-20 rounded-[8.8px] object-cover" />
          <button
            type="button"
            onClick={() => setImage(null)}
            aria-label="Bỏ ảnh"
            className="absolute -right-2 -top-2 rounded-full bg-ink/70 p-1 text-white"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
      <div className="flex items-end gap-2">
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={disabled || uploading}
          aria-label="Đính kèm ảnh"
          className="rounded-[8.8px] p-2.5 text-fog transition-colors hover:bg-white hover:text-cobalt disabled:opacity-50"
        >
          {uploading ? <Loader2 className="size-5 animate-spin" /> : <ImagePlus className="size-5" />}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          hidden
          aria-label="Chọn ảnh để đính kèm"
          onChange={(e) => e.target.files?.[0] && attach(e.target.files[0])}
        />
        <textarea
          rows={1}
          value={text}
          disabled={disabled}
          aria-label="Nhập tin nhắn"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Nhập tin nhắn…"
          className="max-h-32 flex-1 resize-none rounded-[8.8px] border border-line bg-white px-3 py-2.5 text-sm text-ink placeholder:text-fog/70 focus:border-cobalt focus:outline-none focus:ring-2 focus:ring-cobalt/15"
        />
        <button
          type="button"
          onClick={send}
          disabled={disabled || (!text.trim() && !image)}
          aria-label="Gửi tin nhắn"
          className="rounded-[8.8px] bg-cobalt p-2.5 text-white transition-colors hover:bg-cobalt-hover disabled:opacity-50"
        >
          <SendHorizontal className="size-5" />
        </button>
      </div>
    </div>
  );
}
