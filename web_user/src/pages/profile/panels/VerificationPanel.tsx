import { useRef, useState } from "react";
import { UploadCloud, Loader2, CheckCircle2, Clock, XCircle } from "lucide-react";
import { Badge, Button, useToast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { getErrorMessage, uploadToStorage } from "@/shared/api";
import {
  useVerificationRequests,
  useSubmitVerification,
  type VerificationStatus,
} from "../hooks";

const STATUS: Record<VerificationStatus, { label: string; tone: "warning" | "success" | "error"; icon: React.ReactNode }> = {
  PENDING: { label: "Đang chờ duyệt", tone: "warning", icon: <Clock className="size-4" /> },
  APPROVED: { label: "Đã xác minh", tone: "success", icon: <CheckCircle2 className="size-4" /> },
  REJECTED: { label: "Bị từ chối", tone: "error", icon: <XCircle className="size-4" /> },
};

export function VerificationPanel() {
  const toast = useToast();
  const { data } = useVerificationRequests();
  const submit = useSubmitVerification();
  const [idCardUrl, setIdCardUrl] = useState<string | null>(null);
  const [ownershipUrl, setOwnershipUrl] = useState<string | null>(null);

  const latest = data?.[0];

  const send = () => {
    if (!idCardUrl || !ownershipUrl) {
      toast.error("Vui lòng tải lên cả ảnh CCCD và giấy chứng nhận quyền sở hữu.");
      return;
    }
    submit.mutate(
      { idCardUrl, ownershipUrl },
      {
        onSuccess: () => {
          toast.success("Đã gửi yêu cầu xác minh. Vui lòng chờ Admin duyệt.");
          setIdCardUrl(null);
          setOwnershipUrl(null);
        },
        onError: (e) => toast.error(getErrorMessage(e)),
      },
    );
  };

  return (
    <div className="space-y-5">
      {latest && (
        <div className="flex items-center gap-3 rounded-[8.8px] border border-line bg-white p-4">
          <Badge tone={STATUS[latest.status].tone}>
            {STATUS[latest.status].icon} {STATUS[latest.status].label}
          </Badge>
          {latest.note && <span className="text-sm text-fog">{latest.note}</span>}
        </div>
      )}

      <div className="rounded-[15px] border border-line bg-white p-6">
        <h2 className="text-lg">Xác minh danh tính chính chủ</h2>
        <p className="mt-1 text-sm text-fog">
          Tải lên ảnh chụp CCCD và giấy chứng nhận quyền sở hữu nhà đất để nhận huy hiệu “Chủ trọ uy tín”.
        </p>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <UploadTile label="Ảnh chụp CCCD" folder="verification/idcard" value={idCardUrl} onChange={setIdCardUrl} />
          <UploadTile label="Giấy chứng nhận quyền sở hữu" folder="verification/ownership" value={ownershipUrl} onChange={setOwnershipUrl} />
        </div>

        <div className="mt-5 flex justify-end">
          <Button onClick={send} loading={submit.isPending} disabled={!idCardUrl || !ownershipUrl}>
            Gửi yêu cầu xác minh
          </Button>
        </div>
      </div>
    </div>
  );
}

function UploadTile({
  label,
  folder,
  value,
  onChange,
}: {
  label: string;
  folder: string;
  value: string | null;
  onChange: (url: string | null) => void;
}) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const upload = async (file: File) => {
    setUploading(true);
    try {
      const url = await uploadToStorage(file, folder);
      onChange(url);
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <p className="mb-1.5 text-[13px] font-medium text-graphite">{label}</p>
      <button
        type="button"
        onClick={() => input.current?.click()}
        className={cn(
          "flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 overflow-hidden rounded-[8.8px] border-2 border-dashed text-center transition-colors",
          value ? "border-cobalt" : "border-line hover:border-cobalt",
        )}
      >
        {value ? (
          <img src={value} alt={label} className="size-full object-cover" />
        ) : uploading ? (
          <Loader2 className="size-6 animate-spin text-cobalt" />
        ) : (
          <>
            <UploadCloud className="size-6 text-fog" />
            <span className="text-xs text-fog">Bấm để tải ảnh</span>
          </>
        )}
      </button>
      <input ref={input} type="file" accept="image/*" hidden aria-label={label} onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
    </div>
  );
}
