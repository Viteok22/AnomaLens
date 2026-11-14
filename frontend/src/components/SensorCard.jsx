import { AlertTriangle } from "lucide-react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
} from "recharts";
import { formatNumber } from "../utils";

function statusFor(zscore) {
  const absolute = Math.abs(zscore);
  if (absolute > 4) return "critical";
  if (absolute > 2.5) return "warning";
  return "normal";
}

const COLORS = {
  critical: "#dc2626",
  warning: "#f59e0b",
  normal: "#16a34a",
};

export default function SensorCard({ sensor, latest, history }) {
  const value = latest?.sensors?.[sensor.name];
  const zscore = latest?.zscores?.[sensor.name] ?? 0;
  const status = statusFor(zscore);
  const color = COLORS[status];
  const data = history.slice(-60).map((tick, index) => ({
    index,
    value: tick.sensors?.[sensor.name] ?? null,
  }));

  return (
    <div className={`sensor-card ${status}`}>
      <div className="sensor-top">
        <span className="sensor-label">{sensor.label}</span>
        <span className={`sensor-dot ${status}`} />
      </div>

      <div className="sensor-value">
        {value === null || value === undefined ? "—" : formatNumber(value)}
        <span className="sensor-unit">{sensor.unit}</span>
      </div>

      <div className="sensor-spark">
        <ResponsiveContainer width="100%" height={44}>
          <LineChart data={data}>
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="sensor-footer">
        <span className="muted">z = {zscore.toFixed(1)}</span>
        {status !== "normal" && (
          <span className={`sensor-warning ${status}`}>
            <AlertTriangle size={12} />
            отклонение
          </span>
        )}
      </div>
    </div>
  );
}
