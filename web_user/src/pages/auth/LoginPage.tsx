import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Mail, Lock } from "lucide-react";
import { Button, Input, useToast, Tabs } from "@/shared/ui";
import { getErrorMessage } from "@/shared/api";
import { useLogin } from "@/features/auth";
import type { UserRole } from "@/shared/types";
import { AuthShell } from "./AuthShell";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("TENANT");

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    login.mutate(
      { email, password, role },
      {
        onSuccess: () => {
          toast.success("Đăng nhập thành công!");
          navigate(from, { replace: true });
        },
        onError: (err) => toast.error(getErrorMessage(err, "Sai tài khoản hoặc mật khẩu.")),
      },
    );
  };

  return (
    <AuthShell
      title="Đăng nhập"
      subtitle="Chào mừng bạn quay lại Nhà Trọ 360."
      footer={
        <>
          Chưa có tài khoản?{" "}
          <Link to="/register" className="font-medium text-cobalt hover:underline">
            Đăng ký ngay
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Tabs
          items={[
            { value: "TENANT", label: "Người Thuê" },
            { value: "LANDLORD", label: "Chủ Trọ" },
          ]}
          value={role}
          onChange={(v) => setRole(v as UserRole)}
          className="w-full flex"
        />
        <Input
          name="email"
          label="Email"
          placeholder="you@example.com"
          leftIcon={<Mail className="size-4" />}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          name="password"
          type="password"
          label="Mật khẩu"
          placeholder="••••••••"
          leftIcon={<Lock className="size-4" />}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <div className="flex justify-end">
          <Link to="#" className="text-sm text-cobalt hover:underline">
            Quên mật khẩu?
          </Link>
        </div>
        <Button type="submit" block size="lg" loading={login.isPending}>
          Đăng nhập
        </Button>
      </form>
    </AuthShell>
  );
}
