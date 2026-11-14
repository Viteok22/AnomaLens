import { AlertTriangle, Clock, Cpu, Target } from "lucide-react";
import { formatNumber } from "../utils";

export default function MetricsPanel({ metrics }) {
  if (!metrics) {
    return (
      <section className="card metrics-panel">
        <div className="section-header">
          <div>
            <h2>Качество системы</h2>
            <p>Загрузка метрик…</p>
          </div>
        </div>
      </section>
    );
  }

  const detector = metrics.detector || {};
  const fault = metrics.fault_classifier || {};

  return (
    <section className="card metrics-panel">
      <div className="section-header">
        <div>
          <h2>Качество системы</h2>
          <p>Детектор: PCA T²+Q · Тип: RandomForest · SKAB</p>
        </div>
        <span className="muted">
          тревог: {metrics.alerts?.total ?? 0}
        </span>
      </div>

      <div className="metric-grid">
        <div className="metric">
          <Target size={18} />
          <span className="metric-value">
            {detector.f1 !== undefined ? formatNumber(detector.f1, 3) : "—"}
          </span>
          <span className="metric-label">F1 детектора</span>
        </div>

        <div className="metric">
          <Cpu size={18} />
          <span className="metric-value">
            {fault.accuracy !== undefined
              ? `${(fault.accuracy * 100).toFixed(1)}%`
              : "—"}
          </span>
          <span className="metric-label">Тип неисправности</span>
        </div>

        <div className="metric">
          <Clock size={18} />
          <span className="metric-value">
            {detector.alert_confirmation_s !== undefined
              ? `${detector.alert_confirmation_s} с`
              : "—"}
          </span>
          <span className="metric-label">Создание тревоги</span>
        </div>

        <div className="metric">
          <AlertTriangle size={18} />
          <span className="metric-value">
            {detector.far_per_hour !== undefined
              ? `${formatNumber(detector.far_per_hour, 0)}/ч`
              : "—"}
          </span>
          <span className="metric-label">Ложные тревоги</span>
        </div>
      </div>

      <div className="metric-note">
        <span>
          macro F1 типа:{" "}
          <b>
            {fault.macro_f1 !== undefined
              ? formatNumber(fault.macro_f1, 3)
              : "—"}
          </b>
        </span>
        <span>
          выборка: <b>{fault.n_samples ?? "—"}</b> окон ·{" "}
          <b>{fault.n_files ?? "—"}</b> файлов
        </span>
        <span>
          автозакрытие: <b>5 мин нормы + подтверждение</b>
        </span>
      </div>
    </section>
  );
}
