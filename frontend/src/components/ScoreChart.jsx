import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { riskLabel } from "../utils";

const TOOLTIP_STYLE = {
  borderRadius: 10,
  border: "1px solid #e2e8f0",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.08)",
  fontSize: 12,
};

export default function ScoreChart({ history, latest }) {
  const data = history.map((tick) => ({
    time: tick.timestamp?.slice(11, 19),
    score: tick.score,
    threshold: tick.threshold,
  }));

  if (data.length === 0) {
    return (
      <section className="card chart-card">
        <div className="section-header">
          <div>
            <h2>Anomaly score</h2>
            <p>Чем выше, тем сильнее поведение отличается от нормы</p>
          </div>
        </div>
        <div className="empty-state">
          Нажмите «Старт», чтобы начать поток данных.
        </div>
      </section>
    );
  }

  return (
    <section className="card chart-card">
      <div className="section-header">
        <div>
          <h2>Anomaly score</h2>
          <p>Чем выше, тем сильнее поведение отличается от нормы</p>
        </div>
        <div className="chart-stats">
          <span>
            score <b>{latest?.score?.toFixed(2) ?? "—"}</b>
          </span>
          <span>
            порог <b>{latest?.threshold?.toFixed(2) ?? "—"}</b>
          </span>
          {latest?.risk_level && (
            <span className={`risk-badge risk-${latest.risk_level}`}>
              {riskLabel(latest.risk_level)}
            </span>
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 0, left: -16 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e8edf5" />
          <XAxis
            dataKey="time"
            minTickGap={28}
            tick={{ fontSize: 11, fill: "#64748b" }}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fontSize: 11, fill: "#64748b" }}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(value) => Number(value).toFixed(2)}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="score"
            name="score"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="threshold"
            name="порог"
            stroke="#dc2626"
            strokeWidth={1.5}
            strokeDasharray="5 5"
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}
