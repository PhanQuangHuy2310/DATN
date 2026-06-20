import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Modal, Button, Textarea, Select } from "@/shared/ui";
import { useToast } from "@/shared/ui";
import { apiClient, endpoints, getErrorMessage } from "@/shared/api";
import { REPORT_REASONS } from "@/shared/lib";

interface Props {
  open: boolean;
  onClose: () => void;
  listingId: number;
}

export function ReportListingModal({ open, onClose, listingId }: Props) {
  const toast = useToast();
  const [reasonCode, setReasonCode] = useState("");
  const [description, setDescription] = useState("");

  const report = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post(endpoints.reports.base, {
        listingId,
        reasonCode,
        description: description.trim() || undefined,
      });
      return res.data;
    },
    onSuccess: () => {
      toast.success("Đã gửi báo cáo. Cảm ơn bạn đã góp phần làm sạch nền tảng!");
      onClose();
      setReasonCode("");
      setDescription("");
    },
    onError: (e) => toast.error(getErrorMessage(e)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Báo cáo tin đăng vi phạm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Hủy
          </Button>
          <Button variant="danger" onClick={() => report.mutate()} loading={report.isPending} disabled={!reasonCode}>
            Gửi báo cáo
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Select
          label="Lý do báo cáo"
          name="reasonCode"
          placeholder="Chọn lý do…"
          value={reasonCode}
          onChange={(e) => setReasonCode(e.target.value)}
          options={REPORT_REASONS.map((r) => ({ value: r.value, label: r.label }))}
        />
        <Textarea
          label="Mô tả chi tiết (tùy chọn)"
          name="description"
          placeholder="Mô tả cụ thể vấn đề bạn gặp với tin đăng này…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
    </Modal>
  );
}
