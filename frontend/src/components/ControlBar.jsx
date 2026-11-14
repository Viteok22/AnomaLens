import { useRef } from "react";
import { Play, RotateCcw, SkipForward, Square, Upload } from "lucide-react";

const SPEEDS = [1, 5, 10, 20];

export default function ControlBar({
  scenarios,
  scenarioId,
  onScenarioChange,
  speed,
  onSpeedChange,
  running,
  onStart,
  onStop,
  onNext,
  onUpload,
  uploading,
  onReset,
  selectedScenario,
}) {
  const fileInputRef = useRef(null);

  return (
    <section className="control-bar card">
      <div className="control-main">
        <label className="field">
          <span>Сценарий</span>
          <select
            value={scenarioId}
            onChange={(event) => onScenarioChange(event.target.value)}
            disabled={running}
          >
            {scenarios.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {scenario.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field field-small">
          <span>Скорость</span>
          <select
            value={speed}
            onChange={(event) => onSpeedChange(Number(event.target.value))}
            disabled={running}
          >
            {SPEEDS.map((value) => (
              <option key={value} value={value}>
                {value}×
              </option>
            ))}
          </select>
        </label>

        <div className="control-buttons">
          {running ? (
            <button type="button" className="button danger" onClick={onStop}>
              <Square size={16} />
              Стоп
            </button>
          ) : (
            <button
              type="button"
              className="button primary"
              onClick={onStart}
              disabled={!scenarios.length}
            >
              <Play size={16} />
              Старт
            </button>
          )}

          <button type="button" className="button secondary" onClick={onNext}>
            <SkipForward size={16} />
            Следующий
          </button>

          <button
            type="button"
            className="button secondary"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            <Upload size={16} />
            {uploading ? "Загрузка..." : "Загрузить CSV"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            style={{ display: "none" }}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(file);
              event.target.value = "";
            }}
          />

          <button
            type="button"
            className="icon-button"
            onClick={onReset}
            title="Сбросить"
          >
            <RotateCcw size={17} />
          </button>
        </div>
      </div>

      {selectedScenario && (
        <div className="scenario-note">
          <span className="scenario-tag">Сценарий</span>
          <span>{selectedScenario.description}</span>
          <span className="muted">
            {selectedScenario.first_anomaly !== null &&
            selectedScenario.first_anomaly !== undefined
              ? `Аномалия с ${selectedScenario.first_anomaly} с`
              : selectedScenario.first_alarm !== null &&
                  selectedScenario.first_alarm !== undefined
                ? `Модель нашла аномалию на ${selectedScenario.first_alarm} с`
                : "Аномалия не найдена"}{" "}
            · старт с {selectedScenario.start_index} с
          </span>
        </div>
      )}
    </section>
  );
}
