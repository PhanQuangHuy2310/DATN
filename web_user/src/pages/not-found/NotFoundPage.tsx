import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { Button } from "@/shared/ui";

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center justify-center gap-5 px-4 py-24 text-center">
      <div className="flex size-20 items-center justify-center rounded-full bg-cobalt-soft text-cobalt">
        <Compass className="size-9" />
      </div>
      <div className="space-y-1">
        <h1 className="text-cobalt">404</h1>
        <h2>Không tìm thấy trang</h2>
        <p className="text-sm text-fog">
          Trang bạn tìm có thể đã bị xóa hoặc đường dẫn không chính xác.
        </p>
      </div>
      <div className="flex gap-3">
        <Link to="/">
          <Button>Về trang chủ</Button>
        </Link>
        <Link to="/search">
          <Button variant="ghost">Tìm phòng trọ</Button>
        </Link>
      </div>
    </div>
  );
}
