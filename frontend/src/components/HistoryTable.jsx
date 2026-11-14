import { CheckCircle2, X } from "lucide-react";
import { formatDateTime, riskLabel } from "../utils";

function statusLabel(alert) {
  if (alert.resolved_at) return "Закрыт";
  if (alert.acknowledged) return "Принят";
  return "Активен";
}

export default function HistoryTable({
  alerts,
  scenarios = [],
  onAck,
  onClose,
}) {
  return (
    <section className="card history-card">
      <div className="section-header">
        <div>
          <h2>История тревог</h2>
          <p>SQLite · последние события</p>
        </div>
        <span className="muted">{alerts.length} записей</span>
      </div>

      {alerts.length === 0 ? (
        <div className="empty-state">
          Пока нет тревог. Запустите сценарий, чтобы увидеть первое событие.
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Время</th>
                <th>Сценарий</th>
                <th>Тип</th>
                <th>Риск</th>
                <th>Статус</th>
                <th>Рекомендация</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => {
                const scenarioLabel =
                  scenarios.find((item) => item.id === alert.scenario)?.short ||
                  alert.scenario;
                const statusClass = alert.resolved_at
                  ? "resolved"
                  : alert.acknowledged
                    ? "acknowledged"
                    : "active";
                return (
                <tr key={alert.id}>
                  <td className="mono">{formatDateTime(alert.created_at)}</td>
                  <td>{scenarioLabel}</td>
                  <td>{alert.fault_label}</td>
                  <td>
                    <span className={`risk-badge risk-${alert.risk_level}`}>
                      {riskLabel(alert.risk_level)}
                    </span>
                  </td>
                  <td>
                    <span className={`status-chip ${statusClass}`}>
                      {statusLabel(alert)}
                    </span>
                  </td>
                  <td className="recommendation-cell" title={alert.recommendation}>
                    {(alert.recommendation || "").slice(0, 80)}
                    {(alert.recommendation || "").length > 80 ? "…" : ""}
                  </td>
                  <td>
                    <div className="row-actions">
                      {!alert.acknowledged && !alert.resolved_at && (
                        <button
                          type="button"
                          className="icon-button small"
                          title="Подтвердить"
                          onClick={() => onAck(alert.id)}
                        >
                          <CheckCircle2 size={15} />
                        </button>
                      )}
                      {!alert.resolved_at && (
                        <button
                          type="button"
                          className="icon-button small"
                          title="Закрыть тревогу"
                          onClick={() => onClose(alert.id)}
                        >
                          <X size={15} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
