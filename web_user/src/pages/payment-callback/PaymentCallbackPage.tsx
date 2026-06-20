import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { PartyPopper, XCircle } from "lucide-react";
import { Button, Spinner } from "@/shared/ui";
import { apiClient, endpoints, getErrorMessage } from "@/shared/api";
import { useAuthStore } from "@/features/auth/authStore";
import type { User } from "@/entities/user";

type Phase = "verifying" | "success" | "failed";

/**
 * Landing route after the MoMo/ZaloPay sandbox redirects back
 * (`/payment/callback?status=success&transaction_id=...`).
 * We confirm the transaction with the backend, then flip the local user to PRO.
 */
export function PaymentCallbackPage() {
  const [params] = useSearchParams();
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);
  const [phase, setPhase] = useState<Phase>("verifying");
  const [message, setMessage] = useState("");
  const ran = useRef(false);

  const status = params.get("status");
  const transactionId = params.get("transaction_id") ?? params.get("transactionId");

  const verify = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<{ user: User }>(endpoints.payments.verify, {
        transactionId,
        status,
      });
      return res.data;
    },
  });

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    if (status !== "success" || !transactionId) {
      setPhase("failed");
      setMessage("Giao dịch chưa hoàn tất hoặc đã bị hủy.");
      return;
    }

    verify.mutate(undefined, {
      onSuccess: (data) => {
        if (data.user) setUser(data.user);
        else if (user) setUser({ ...user, plan: "PRO" });
        setPhase("success");
      },
      onError: (e) => {
        setPhase("failed");
        setMessage(getErrorMessage(e, "Không xác minh được giao dịch."));
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto flex max-w-md flex-col items-center justify-center gap-5 px-4 py-24 text-center">
      {phase === "verifying" && (
        <>
          <Spinner className="size-9" />
          <p className="text-sm text-fog">Đang xác minh giao dịch của bạn…</p>
        </>
      )}

      {phase === "success" && (
        <>
          <div className="flex size-20 items-center justify-center rounded-full bg-success-soft text-success">
            <PartyPopper className="size-9" />
          </div>
          <div className="space-y-1">
            <h2>Nâng cấp PRO thành công!</h2>
            <p className="text-sm text-fog">
              Tài khoản của bạn đã chuyển sang gói PRO — đăng tin không giới hạn.
            </p>
          </div>
          <div className="flex gap-3">
            <Link to="/landlord/dashboard">
              <Button>Về Dashboard</Button>
            </Link>
            <Link to="/listings/create">
              <Button variant="ghost">Đăng tin mới</Button>
            </Link>
          </div>
        </>
      )}

      {phase === "failed" && (
        <>
          <div className="flex size-20 items-center justify-center rounded-full bg-error-soft text-error">
            <XCircle className="size-9" />
          </div>
          <div className="space-y-1">
            <h2>Thanh toán không thành công</h2>
            <p className="text-sm text-fog">{message}</p>
          </div>
          <div className="flex gap-3">
            <Link to="/landlord/dashboard">
              <Button>Thử lại</Button>
            </Link>
            <Link to="/">
              <Button variant="ghost">Về trang chủ</Button>
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
