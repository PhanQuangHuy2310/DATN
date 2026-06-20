import { useRef, useState } from "react";
import { Camera, BadgeCheck, Loader2 } from "lucide-react";
import { Avatar, Badge, Button, Input, Modal, useToast } from "@/shared/ui";
import { getErrorMessage, uploadToStorage } from "@/shared/api";
import { useAuthStore } from "@/features/auth";
import { useUpdateProfile, useChangePassword } from "../hooks";

export function PersonalInfoPanel() {
  const { user, setUser } = useAuthStore();
  const toast = useToast();
  const updateProfile = useUpdateProfile();
  const avatarInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);

  const [name, setName] = useState(user?.name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(user?.avatarUrl ?? null);

  if (!user) return null;

  const onAvatar = async (file: File) => {
    setUploading(true);
    try {
      const url = await uploadToStorage(file, "avatars");
      setAvatarUrl(url);
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  const save = () =>
    updateProfile.mutate(
      { name, phone, avatarUrl },
      {
        onSuccess: (u) => {
          setUser(u ?? { ...user, name, phone, avatarUrl });
          toast.success("Đã cập nhật hồ sơ.");
        },
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );

  return (
    <div className="space-y-5">
      <div className="rounded-[15px] border border-line bg-white p-6">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Avatar src={avatarUrl} name={name} size={72} />
            <button
              type="button"
              onClick={() => avatarInput.current?.click()}
              aria-label="Đổi ảnh đại diện"
              className="absolute -bottom-1 -right-1 rounded-full border border-line bg-white p-1.5 text-graphite hover:text-cobalt"
            >
              {uploading ? <Loader2 className="size-3.5 animate-spin" /> : <Camera className="size-3.5" />}
            </button>
            <input
              ref={avatarInput}
              type="file"
              accept="image/*"
              hidden
              aria-label="Tải ảnh đại diện"
              onChange={(e) => e.target.files?.[0] && onAvatar(e.target.files[0])}
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <p className="text-lg font-semibold text-ink">{user.name}</p>
              {user.verified && <BadgeCheck className="size-4 text-cobalt" />}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Badge tone={user.plan === "PRO" ? "warning" : "neutral"}>
                {user.plan === "PRO" ? "Gói PRO" : "Gói FREE"}
              </Badge>
              <span className="text-xs text-fog">{user.role === "LANDLORD" ? "Chủ trọ" : "Khách thuê"}</span>
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <Input label="Họ và tên" name="name" value={name} onChange={(e) => setName(e.target.value)} />
          <Input label="Số điện thoại" name="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <Input label="Email" name="email" value={user.email} disabled hint="Email không thể thay đổi" />
        </div>

        <div className="mt-5 flex items-center justify-between border-t border-line pt-4">
          <Button variant="ghost" onClick={() => setPwOpen(true)}>Đổi mật khẩu</Button>
          <Button onClick={save} loading={updateProfile.isPending}>Lưu thay đổi</Button>
        </div>
      </div>

      <ChangePasswordModal open={pwOpen} onClose={() => setPwOpen(false)} />
    </div>
  );
}

function ChangePasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const submit = () => {
    if (next !== confirm) {
      toast.error("Mật khẩu xác nhận không khớp.");
      return;
    }
    change.mutate(
      { currentPassword: current, newPassword: next },
      {
        onSuccess: () => {
          toast.success("Đã đổi mật khẩu.");
          onClose();
          setCurrent("");
          setNext("");
          setConfirm("");
        },
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Đổi mật khẩu"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Hủy</Button>
          <Button onClick={submit} loading={change.isPending} disabled={!current || !next}>Cập nhật</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input label="Mật khẩu hiện tại" name="current" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        <Input label="Mật khẩu mới" name="new" type="password" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} />
        <Input label="Xác nhận mật khẩu mới" name="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </div>
    </Modal>
  );
}
