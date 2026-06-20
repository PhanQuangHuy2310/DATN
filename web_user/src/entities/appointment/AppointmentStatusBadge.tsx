import { Badge } from "@/shared/ui";
import {
  APPOINTMENT_STATUS_LABEL,
  type AppointmentStatus,
} from "./model";

const TONE: Record<AppointmentStatus, "warning" | "cobalt" | "error" | "success"> = {
  PENDING: "warning",
  CONFIRMED: "cobalt",
  CANCELLED: "error",
  SUCCESS: "success",
};

export function AppointmentStatusBadge({ status }: { status: AppointmentStatus }) {
  return (
    <Badge tone={TONE[status]} dot>
      {APPOINTMENT_STATUS_LABEL[status]}
    </Badge>
  );
}
