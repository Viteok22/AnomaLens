import { useCallback, useEffect, useRef, useState } from "react";
import Header from "./components/Header";
import ControlBar from "./components/ControlBar";
import SensorGrid from "./components/SensorGrid";
import ScoreChart from "./components/ScoreChart";
import AlertPanel from "./components/AlertPanel";
import MetricsPanel from "./components/MetricsPanel";
import HistoryTable from "./components/HistoryTable";
import Footer from "./components/Footer";
import {
  ackAlert,
  closeAlert,
  fetchAlerts,
  fetchHealth,
  fetchMetrics,
  fetchScenarios,
  fetchSensors,
  streamUrl,
  testTelegram,
  uploadCsv,
} from "./api";

const MAX_POINTS = 180;

export default function App() {
  const [scenarios, setScenarios] = useState([]);
  const [sensors, setSensors] = useState([]);
  const [scenarioId, setScenarioId] = useState("valve_in");
  const [speed, setSpeed] = useState(10);
  const [running, setRunning] = useState(false);
  const [connected, setConnected] = useState(false);
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [currentAlert, setCurrentAlert] = useState(null);
  const [alertStatus, setAlertStatus] = useState("none");
  const [alerts, setAlerts] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [health, setHealth] = useState(null);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [tour, setTour] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const wsRef = useRef(null);
  const audioRef = useRef(null);
  const tourRef = useRef(false);
  const scenariosRef = useRef([]);
  const speedRef = useRef(speed);
  const scenarioIdRef = useRef(scenarioId);
  const startScenarioRef = useRef(null);

  useEffect(() => {
    scenariosRef.current = scenarios;
  }, [scenarios]);

  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  useEffect(() => {
    scenarioIdRef.current = scenarioId;
  }, [scenarioId]);

  const refreshAlerts = useCallback(async () => {
    try {
      const [alertsData, metricsData] = await Promise.all([
        fetchAlerts(),
        fetchMetrics(),
      ]);
      setAlerts(alertsData);
      setMetrics(metricsData);
    } catch {
      // backend may be unavailable during startup
    }
  }, []);

  useEffect(() => {
    fetchSensors().then(setSensors).catch(() => {});
    fetchScenarios()
      .then((items) => {
        setScenarios(items);
        if (items.length) {
          setScenarioId((current) =>
            items.some((item) => item.id === current) ? current : items[0].id,
          );
        }
      })
      .catch(() => setError("Не удалось загрузить сценарии. Проверьте backend."));
    fetchHealth().then(setHealth).catch(() => {});
    refreshAlerts();
    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [refreshAlerts]);

  useEffect(() => {
    if (!running) return undefined;
    const timer = window.setInterval(() => {
      refreshAlerts();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [running, refreshAlerts]);

  const playBeep = useCallback(() => {
    if (!soundEnabled) return;
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = audioRef.current || new AudioContext();
      audioRef.current = ctx;
      const now = ctx.currentTime;
      [880, 660].forEach((frequency, index) => {
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = "sine";
        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, now + index * 0.18);
        gain.gain.exponentialRampToValueAtTime(0.16, now + index * 0.18 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + index * 0.18 + 0.16);
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start(now + index * 0.18);
        oscillator.stop(now + index * 0.18 + 0.18);
      });
    } catch {
      // audio may be blocked until a user gesture
    }
  }, [soundEnabled]);

  const stopStream = useCallback((silent = false) => {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setRunning(false);
    setConnected(false);
    if (!silent) {
      tourRef.current = false;
      setTour(false);
    }
  }, []);

  const startScenario = useCallback(
    (id) => {
      stopStream(true);
      setError(null);
      setLatest(null);
      setHistory([]);
      setCurrentAlert(null);
      setAlertStatus("none");
      setRunning(true);
      setConnected(true);

      const ws = new WebSocket(streamUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            scenario: id,
            speed: speedRef.current,
            jump: true,
          }),
        );
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);

        if (message.type === "started") {
          setConnected(true);
          setRunning(true);
        } else if (message.type === "tick") {
          setLatest(message);
          setHistory((previous) => [
            ...previous.slice(-(MAX_POINTS - 1)),
            message,
          ]);
        } else if (message.type === "alert") {
          setCurrentAlert(message.alert);
          setAlertStatus("active");
          playBeep();
          refreshAlerts();
        } else if (message.type === "recommendation") {
          setCurrentAlert((previous) =>
            previous && previous.id === message.alert_id
              ? {
                  ...previous,
                  recommendation: message.recommendation,
                  recommendation_source: message.source,
                }
              : previous,
          );
        } else if (message.type === "resolved") {
          setAlertStatus("resolved");
          refreshAlerts();
        } else if (message.type === "finished") {
          setRunning(false);
          setConnected(false);
          ws.close();
          wsRef.current = null;

          if (tourRef.current) {
            const items = scenariosRef.current;
            const index = items.findIndex((item) => item.id === id);
            const next = items[index + 1];
            if (next) {
              window.setTimeout(() => {
                setScenarioId(next.id);
                startScenarioRef.current?.(next.id);
              }, 1500);
            } else {
              tourRef.current = false;
              setTour(false);
            }
          }
        } else if (message.type === "error") {
          setError(message.message || "Ошибка потока");
          stopStream(true);
        }
      };

      ws.onerror = () => {
        setError("Ошибка WebSocket. Проверьте, что backend запущен.");
      };

      ws.onclose = () => {
        setConnected(false);
        setRunning(false);
      };
    },
    [playBeep, refreshAlerts, stopStream],
  );

  useEffect(() => {
    startScenarioRef.current = startScenario;
  }, [startScenario]);

  const start = () => startScenario(scenarioId);
  const stop = () => stopStream(false);
  const reset = () => {
    stopStream(false);
    setLatest(null);
    setHistory([]);
    setCurrentAlert(null);
    setAlertStatus("none");
    setError(null);
  };

  const nextScenario = () => {
    if (!scenarios.length) return;
    const index = scenarios.findIndex((item) => item.id === scenarioIdRef.current);
    const next = scenarios[(index + 1) % scenarios.length];
    tourRef.current = false;
    setTour(false);
    setScenarioId(next.id);
    startScenario(next.id);
  };

  const startTour = () => {
    if (!scenarios.length) return;
    tourRef.current = true;
    setTour(true);
    const first = scenarios[0].id;
    setScenarioId(first);
    startScenario(first);
  };

  const acknowledge = async () => {
    if (!currentAlert) return;
    try {
      await ackAlert(currentAlert.id);
      setCurrentAlert((previous) =>
        previous ? { ...previous, acknowledged: 1 } : previous,
      );
      refreshAlerts();
    } catch {
      setToast("Не удалось подтвердить тревогу");
      window.setTimeout(() => setToast(null), 4000);
    }
  };

  const acknowledgeFromHistory = async (id) => {
    try {
      await ackAlert(id);
      refreshAlerts();
    } catch {
      setToast("Не удалось подтвердить тревогу");
      window.setTimeout(() => setToast(null), 4000);
    }
  };

  const closeCurrentAlert = async () => {
    if (!currentAlert) return;
    try {
      await closeAlert(currentAlert.id);
      setCurrentAlert((previous) =>
        previous
          ? {
              ...previous,
              acknowledged: 1,
              resolved_at: new Date().toISOString(),
              risk_level: latest?.risk_level ?? previous.risk_level,
              risk_score: latest?.risk_score ?? previous.risk_score,
              fault_type: latest?.fault?.type ?? previous.fault_type,
              fault_label: latest?.fault?.label ?? previous.fault_label,
              confidence: latest?.fault?.confidence ?? previous.confidence,
              top_sensors: latest?.top_sensors ?? previous.top_sensors,
            }
          : previous,
      );
      setAlertStatus("resolved");
      refreshAlerts();
    } catch {
      setToast("Не удалось закрыть тревогу");
      window.setTimeout(() => setToast(null), 4000);
    }
  };

  const closeFromHistory = async (id) => {
    try {
      await closeAlert(id);
      setCurrentAlert((previous) =>
        previous && previous.id === id
          ? {
              ...previous,
              acknowledged: 1,
              resolved_at: new Date().toISOString(),
              risk_level: latest?.risk_level ?? previous.risk_level,
              risk_score: latest?.risk_score ?? previous.risk_score,
              fault_type: latest?.fault?.type ?? previous.fault_type,
              fault_label: latest?.fault?.label ?? previous.fault_label,
              confidence: latest?.fault?.confidence ?? previous.confidence,
              top_sensors: latest?.top_sensors ?? previous.top_sensors,
            }
          : previous,
      );
      if (currentAlert?.id === id) {
        setAlertStatus("resolved");
      }
      refreshAlerts();
    } catch {
      setToast("Не удалось закрыть тревогу");
      window.setTimeout(() => setToast(null), 4000);
    }
  };

  const handleUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadCsv(file);
      const items = await fetchScenarios();
      setScenarios(items);
      setScenarioId(result.scenario.id);
      const message =
        result.first_alarm !== null && result.first_alarm !== undefined
          ? `Файл загружен. Модель нашла аномалию на ${result.first_alarm} с.`
          : "Файл загружен. Аномалия не найдена — поток начнётся с 100-й секунды.";
      setToast(message);
      window.setTimeout(() => setToast(null), 7000);
    } catch (uploadError) {
      setToast(`Не удалось загрузить CSV: ${uploadError.message}`);
      window.setTimeout(() => setToast(null), 7000);
    } finally {
      setUploading(false);
    }
  };

  const handleTestTelegram = async () => {
    try {
      const result = await testTelegram();
      setToast(
        result.sent
          ? "Тестовое сообщение отправлено в Telegram"
          : "Telegram не настроен: добавьте токен и chat_id в backend/.env",
      );
    } catch {
      setToast("Не удалось проверить Telegram");
    }
    window.setTimeout(() => setToast(null), 5000);
  };

  const selectedScenario = scenarios.find((item) => item.id === scenarioId);

  return (
    <div className="app">
      <Header
        connected={connected}
        running={running}
        health={health}
        soundEnabled={soundEnabled}
        onToggleSound={() => setSoundEnabled((value) => !value)}
        onTestTelegram={handleTestTelegram}
      />

      <ControlBar
        scenarios={scenarios}
        scenarioId={scenarioId}
        onScenarioChange={setScenarioId}
        speed={speed}
        onSpeedChange={setSpeed}
        running={running}
        tour={tour}
        onStart={start}
        onStop={stop}
        onNext={nextScenario}
        onUpload={handleUpload}
        uploading={uploading}
        onReset={reset}
        selectedScenario={selectedScenario}
      />

      {error && <div className="error-banner">{error}</div>}
      {toast && <div className="toast">{toast}</div>}

      <main className="layout">
        <section className="main-column">
          <SensorGrid
            sensors={sensors}
            latest={latest}
            history={history}
          />
          <ScoreChart history={history} latest={latest} />
        </section>

        <aside className="side-column">
          <AlertPanel
            alert={currentAlert}
            status={alertStatus}
            latest={latest}
            onAck={acknowledge}
            onClose={closeCurrentAlert}
          />
          <MetricsPanel metrics={metrics} />
        </aside>
      </main>

      <HistoryTable
        alerts={alerts}
        scenarios={scenarios}
        onAck={acknowledgeFromHistory}
        onClose={closeFromHistory}
      />
      <Footer />
    </div>
  );
}
