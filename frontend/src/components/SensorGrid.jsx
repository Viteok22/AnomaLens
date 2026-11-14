import SensorCard from "./SensorCard";
import { formatDateTime } from "../utils";

export default function SensorGrid({ sensors, latest, history }) {
  return (
    <section className="card sensor-section">
      <div className="section-header">
        <div>
          <h2>Датчики</h2>
          <p>8 каналов · обновление в реальном времени</p>
        </div>
        <span className="muted">
          {latest ? formatDateTime(latest.timestamp) : "нет данных"}
        </span>
      </div>

      {sensors.length === 0 ? (
        <div className="empty-state">Загрузка списка датчиков…</div>
      ) : (
        <div className="sensor-grid">
          {sensors.map((sensor) => (
            <SensorCard
              key={sensor.name}
              sensor={sensor}
              latest={latest}
              history={history}
            />
          ))}
        </div>
      )}
    </section>
  );
}
