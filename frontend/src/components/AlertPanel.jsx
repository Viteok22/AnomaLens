import {
  BookOpen,
  Bot,
  CheckCircle2,
  Clock,
  ShieldAlert,
  Wrench,
  X,
} from "lucide-react";
import { formatNumber, formatTime, riskLabel } from "../utils";

export default function AlertPanel({ alert, status, latest, onAck, onClose }) {
  if (!alert) {
    return (
      <section className="card alert-panel normal">
        <div className="alert-normal-icon">
          <CheckCircle2 size={28} />
        </div>
        <div>
          <h2>Норма</h2>
          <p>
            Отклонений не обнаружено. Система следит за 8 датчиками и
            сравнивает их поведение с нормальным профилем.
          </p>
        </div>
      </section>
    );
  }

  const isActive = status === "active";
  const fault =
    isActive && latest?.fault
      ? latest.fault
      : {
          type: alert.fault_type,
          label: alert.fault_label,
          confidence: alert.confidence,
        };
  const riskLevel = isActive
    ? latest?.risk_level || alert.risk_level
    : alert.risk_level;
  const riskScore = isActive
    ? latest?.risk_score ?? alert.risk_score
    : alert.risk_score;
  const topSensors =
    isActive && latest?.top_sensors ? latest.top_sensors : alert.top_sensors || [];
  const confidence = Math.round((fault.confidence ?? 0) * 1000) / 10;
  const source = alert.recommendation_source || "Правила";
  const chipClass = !isActive
    ? "resolved"
    : alert.acknowledged
      ? "acknowledged"
      : "active";
  const chipText = !isActive
    ? "Закрыт"
    : alert.acknowledged
      ? "Принят"
      : "Активен";
  const normalSeconds = latest?.normal_seconds ?? 0;
  const autoCloseSeconds = latest?.auto_close_seconds ?? 300;
  const waitingAck =
    isActive && !alert.acknowledged && normalSeconds >= autoCloseSeconds;
  const autoClosing =
    isActive && alert.acknowledged && normalSeconds >= autoCloseSeconds;

  return (
    <section className={`card alert-panel ${isActive ? "active" : "resolved"}`}>
      <div className="alert-header">
        <div className="alert-title">
          <ShieldAlert size={22} />
          <div>
            <h2>{isActive ? "Обнаружена аномалия" : "Тревога закрыта"}</h2>
            <p>{formatTime(alert.created_at)}</p>
          </div>
        </div>
        <div className="alert-badges">
          <span className={`risk-badge risk-${riskLevel}`}>
            {riskLabel(riskLevel)}
          </span>
          <span className={`status-chip ${chipClass}`}>{chipText}</span>
        </div>
      </div>

      <div className="fault-block">
        <div>
          <span className="eyebrow">Тип неисправности</span>
          <h3>{fault.label || alert.fault_label}</h3>
          <span className="muted">
            код: {fault.type || alert.fault_type} · уверенность {confidence}%
          </span>
        </div>
        <Wrench size={26} className="fault-icon" />
      </div>

      <div className="risk-block">
        <div className="risk-row">
          <span>Уровень риска</span>
          <b>{formatNumber(riskScore, 0)} / 100</b>
        </div>
        <div className="risk-track">
          <div
            className={`risk-fill risk-${riskLevel}`}
            style={{ width: `${Math.min(100, Number(riskScore) || 0)}%` }}
          />
        </div>
      </div>

      <div className="top-sensors">
        <span className="eyebrow">Наибольшее отклонение</span>
        <ul>
          {topSensors.map((sensor) => (
            <li key={sensor.name}>
              <span>{sensor.label}</span>
              <span className="mono">
                {formatNumber(sensor.value)} {sensor.unit}
              </span>
              <span
                className={`z-badge ${Math.abs(sensor.z) > 4 ? "critical" : ""}`}
              >
                {Math.abs(sensor.z) >= 24.9
                  ? `z ${sensor.z > 0 ? "≥" : "≤"} ${sensor.z > 0 ? "25" : "-25"}`
                  : `z ${sensor.z > 0 ? "+" : ""}${sensor.z}`}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="recommendation">
        <div className="recommendation-header">
          <span className="eyebrow">Что делать</span>
          <span className={`source-badge ${source === "DeepSeek" ? "llm" : ""}`}>
            {source === "DeepSeek" ? <Bot size={13} /> : <BookOpen size={13} />}
            {source}
          </span>
        </div>
        <p>{alert.recommendation}</p>
      </div>

      {isActive && (
        <div className={`lifecycle-hint ${waitingAck ? "attention" : ""}`}>
          {autoClosing
            ? "Сигнал в норме 5 минут. Тревога закрывается автоматически."
            : waitingAck
              ? "Сигнал в норме 5 минут. Подтвердите тревогу, чтобы закрыть."
              : "Автозакрытие: 5 минут нормы + подтверждение оператором."}
        </div>
      )}

      <div className="alert-footer">
        <span className="muted">
          <Clock size={13} /> создан {formatTime(alert.created_at)}
        </span>
        {isActive ? (
          alert.acknowledged ? (
            <button
              type="button"
              className="button secondary small"
              onClick={onClose}
            >
              <X size={15} />
              Закрыть
            </button>
          ) : (
            <button
              type="button"
              className="button secondary small"
              onClick={onAck}
            >
              <CheckCircle2 size={15} />
              Подтвердить
            </button>
          )
        ) : (
          <span className="muted">Закрыта</span>
        )}
      </div>

      <p className="disclaimer">
        Рекомендация носит справочный характер и не заменяет регламент
        технического обслуживания.
      </p>
    </section>
  );
}
