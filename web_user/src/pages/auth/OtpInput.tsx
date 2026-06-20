import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";
import { cn } from "@/shared/lib/cn";

interface Props {
  length?: number;
  value: string;
  onChange: (value: string) => void;
}

/** Six linked single-digit inputs with auto-advance + paste support. */
export function OtpInput({ length = 6, value, onChange }: Props) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = Array.from({ length }, (_, i) => value[i] ?? "");

  const setAt = (i: number, d: string) => {
    const next = digits.slice();
    next[i] = d;
    onChange(next.join("").slice(0, length));
  };

  const onInput = (i: number, raw: string) => {
    const d = raw.replace(/\D/g, "").slice(-1);
    setAt(i, d);
    if (d && i < length - 1) refs.current[i + 1]?.focus();
  };

  const onKeyDown = (i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) refs.current[i - 1]?.focus();
  };

  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (text) {
      onChange(text);
      refs.current[Math.min(text.length, length - 1)]?.focus();
    }
  };

  return (
    <div className="flex justify-between gap-2" onPaste={onPaste}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          inputMode="numeric"
          maxLength={1}
          aria-label={`Ô mã OTP ${i + 1}`}
          value={d}
          onChange={(e) => onInput(i, e.target.value)}
          onKeyDown={(e) => onKeyDown(i, e)}
          className={cn(
            "h-12 w-full rounded-[8.8px] border bg-white text-center text-lg font-semibold text-ink",
            "transition-colors focus:border-cobalt focus:outline-none focus:ring-2 focus:ring-cobalt/15",
            d ? "border-cobalt" : "border-line",
          )}
        />
      ))}
    </div>
  );
}
