import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Mail, Lock, User as UserIcon, Phone } from "lucide-react";
import { Button, Input, useToast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { getErrorMessage } from "@/shared/api";
import { useRegister, useVerifyOtp, useResendOtp } from "@/features/auth";
import type { UserRole } from "@/shared/types";
import { AuthShell } from "./AuthShell";
import { OtpInput } from "./OtpInput";

const OTP_SECONDS = 300;

export function RegisterPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const register = useRegister();
  const [step, setStep] = useState<"form" | "otp">("form");
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phone: "",
    password: "",
    role: "TENANT" as UserRole,
  });

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    register.mutate(form, {
      onSuccess: () => {
        toast.success("Đã gửi mã OTP tới email của bạn.");
        setStep("otp");
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    });
  };

  if (step === "otp") {
    return <OtpStep email={form.email} onDone={() => navigate("/", { replace: true })} />;
  }

  return (
    <AuthShell
      title="Tạo tài khoản"
      subtitle="Đăng ký miễn phí để bắt đầu tìm hoặc đăng tin phòng trọ."
      footer={
        <>
          Đã có tài khoản?{" "}
          <Link to="/login" className="font-medium text-cobalt hover:underline">
            Đăng nhập
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <p className="mb-1.5 text-[13px] font-medium text-graphite">Bạn là</p>
          <div className="grid grid-cols-2 gap-2">
            {([
              { value: "TENANT", label: "Khách thuê" },
              { value: "LANDLORD", label: "Chủ trọ" },
            ] as const).map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => set("role", r.value)}
                className={cn(
                  "rounded-[8.8px] border px-3 py-2.5 text-sm font-medium transition-colors",
                  form.role === r.value
                    ? "border-cobalt bg-cobalt-soft text-cobalt"
                    : "border-line text-graphite hover:border-cobalt",
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <Input
          name="fullName"
          label="Họ và tên"
          placeholder="Nguyễn Văn A"
          leftIcon={<UserIcon className="size-4" />}
          value={form.fullName}
          onChange={(e) => set("fullName", e.target.value)}
          required
        />
        <Input
          name="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          leftIcon={<Mail className="size-4" />}
          value={form.email}
          onChange={(e) => set("email", e.target.value)}
          required
        />
        <Input
          name="phone"
          label="Số điện thoại"
          placeholder="09xx xxx xxx"
          leftIcon={<Phone className="size-4" />}
          value={form.phone}
          onChange={(e) => set("phone", e.target.value)}
          required
        />
        <Input
          name="password"
          type="password"
          label="Mật khẩu"
          placeholder="Tối thiểu 8 ký tự"
          leftIcon={<Lock className="size-4" />}
          value={form.password}
          onChange={(e) => set("password", e.target.value)}
          minLength={8}
          required
        />
        <Button type="submit" block size="lg" loading={register.isPending}>
          Đăng ký
        </Button>
      </form>
    </AuthShell>
  );
}

function OtpStep({ email, onDone }: { email: string; onDone: () => void }) {
  const toast = useToast();
  const verify = useVerifyOtp();
  const resend = useResendOtp();
  const [code, setCode] = useState("");
  const [seconds, setSeconds] = useState(OTP_SECONDS);

  useEffect(() => {
    if (seconds <= 0) return;
    const id = window.setInterval(() => setSeconds((s) => s - 1), 1000);
    return () => window.clearInterval(id);
  }, [seconds]);

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");

  const submit = () => {
    if (code.length < 6) return;
    verify.mutate(
      { email, otpCode: code },
      {
        onSuccess: () => {
          toast.success("Xác thực tài khoản thành công!");
          onDone();
        },
        onError: (err) => toast.error(getErrorMessage(err, "Mã OTP không đúng.")),
      },
    );
  };

  const onResend = () =>
    resend.mutate(email, {
      onSuccess: () => {
        toast.success("Đã gửi lại mã OTP.");
        setSeconds(OTP_SECONDS);
        setCode("");
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    });

  return (
    <AuthShell
      title="Xác thực tài khoản"
      subtitle={`Nhập mã 6 chữ số đã gửi tới ${email}.`}
    >
      <div className="space-y-5">
        <OtpInput value={code} onChange={setCode} />

        <div className="text-center text-sm text-fog">
          {seconds > 0 ? (
            <span>
              Mã hết hạn sau <span className="font-semibold text-ink">{mm}:{ss}</span>
            </span>
          ) : (
            <button type="button" onClick={onResend} className="font-medium text-cobalt hover:underline" disabled={resend.isPending}>
              Gửi lại mã OTP
            </button>
          )}
        </div>

        <Button block size="lg" onClick={submit} loading={verify.isPending} disabled={code.length < 6}>
          Xác nhận
        </Button>
      </div>
    </AuthShell>
  );
}
