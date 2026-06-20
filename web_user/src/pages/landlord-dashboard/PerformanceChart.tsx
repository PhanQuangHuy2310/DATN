import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { DailyStat } from "./hooks";

export default function PerformanceChart({ data }: { data: DailyStat[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e6e3e2" />
        <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#78716b" }} />
        <YAxis tick={{ fontSize: 12, fill: "#78716b" }} />
        <RTooltip />
        <Legend wrapperStyle={{ fontSize: 13 }} />
        <Line type="monotone" dataKey="views" name="Lượt xem" stroke="#165dfb" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="contacts" name="Lượt liên hệ" stroke="#b4690e" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="bookings" name="Lượt đặt lịch" stroke="#1f8a5b" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
