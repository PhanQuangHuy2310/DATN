import { cn } from "@/shared/lib/cn";

export interface AvatarProps {
  src?: string | null;
  name?: string;
  size?: number;
  className?: string;
}

function initials(name?: string): string {
  if (!name) return "?";
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}

export function Avatar({ src, name, size = 40, className }: AvatarProps) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-cobalt-soft text-cobalt font-medium",
        className,
      )}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {src ? (
        <img src={src} alt={name ?? "avatar"} className="size-full object-cover" />
      ) : (
        initials(name)
      )}
    </span>
  );
}
