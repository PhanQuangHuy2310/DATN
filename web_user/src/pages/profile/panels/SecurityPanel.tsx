import { Button, Input } from "@/shared/ui";
import { Lock } from "lucide-react";

export function SecurityPanel() {
  return (
    <div className="rounded-[12px] border border-line bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-center gap-3 border-b border-line pb-4">
        <div className="flex size-10 items-center justify-center rounded-full bg-cobalt-soft text-cobalt">
          <Lock className="size-5" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-ink">Bảo mật</h2>
          <p className="text-sm text-fog">Cập nhật mật khẩu để bảo vệ tài khoản</p>
        </div>
      </div>

      <form className="max-w-md space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-graphite">Mật khẩu hiện tại</label>
          <Input type="password" placeholder="Nhập mật khẩu hiện tại" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-graphite">Mật khẩu mới</label>
          <Input type="password" placeholder="Nhập mật khẩu mới" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-graphite">Nhập lại mật khẩu mới</label>
          <Input type="password" placeholder="Xác nhận mật khẩu mới" />
        </div>
        
        <div className="pt-2">
          <Button type="button">Cập nhật mật khẩu</Button>
        </div>
      </form>
    </div>
  );
}
