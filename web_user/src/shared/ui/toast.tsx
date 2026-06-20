import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";
import { cn } from "@/shared/lib/cn";

type ToastTone = "success" | "error" | "info";
interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastApi {
  show: (message: string, tone?: ToastTone) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (message: string, tone: ToastTone = "info") => {
      const id = ++counter;
      setItems((prev) => [...prev, { id, tone, message }]);
      window.setTimeout(() => remove(id), 4000);
    },
    [remove],
  );

  const api: ToastApi = {
    show,
    success: (m) => show(m, "success"),
    error: (m) => show(m, "error"),
    info: (m) => show(m, "info"),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div className="fixed bottom-5 right-5 z-[100] flex w-80 flex-col gap-2">
          {items.map((t) => (
            <Toast key={t.id} item={t} onClose={() => remove(t.id)} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

const icons = {
  success: <CheckCircle2 className="size-5 text-success" />,
  error: <AlertCircle className="size-5 text-error" />,
  info: <Info className="size-5 text-cobalt" />,
};

function Toast({ item, onClose }: { item: ToastItem; onClose: () => void }) {
  return (
    <output
      className={cn(
        "flex items-start gap-3 rounded-[8.8px] border border-line bg-white px-3.5 py-3 text-sm text-ink",
        "shadow-[0_6px_20px_rgba(17,17,17,0.08)]",
      )}
    >
      {icons[item.tone]}
      <span className="flex-1 leading-snug">{item.message}</span>
      <button type="button" onClick={onClose} aria-label="Đóng" className="text-fog hover:text-ink">
        <X className="size-4" />
      </button>
    </output>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}
