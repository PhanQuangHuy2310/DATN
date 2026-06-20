import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const sizes = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

export function Modal({ open, onClose, title, children, footer, size = "md", className }: ModalProps) {
  const titleId = useId();
  const ref = useRef<HTMLDialogElement>(null);

  // Drive the native <dialog> as a modal: top-layer rendering, built-in
  // focus trap, background inert and ::backdrop all come for free.
  useEffect(() => {
    if (!open) return;
    const dlg = ref.current;
    dlg?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dlg?.close();
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={ref}
      aria-labelledby={title ? titleId : undefined}
      aria-label={title ? undefined : "Hộp thoại"}
      // Escape fires `cancel`; route it through onClose so parent state stays in sync.
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      // A click landing on the dialog element itself (not its content) is a backdrop click.
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cn(
        "m-auto max-h-[90vh] w-full flex-col rounded-[15px] border border-line bg-white p-0",
        "backdrop:bg-ink/40 backdrop:backdrop-blur-[2px]",
        sizes[size],
        className,
      )}
    >
      <div className="flex max-h-[90vh] flex-col">
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
          <h3 id={titleId} className="text-base font-semibold text-ink">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="rounded-[8.8px] p-1 text-fog transition-colors hover:bg-paper hover:text-ink"
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="scroll-area flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-3 border-t border-line px-5 py-4">
            {footer}
          </div>
        )}
      </div>
    </dialog>
  );
}
