import { Activity, Bell, Send, Volume2, VolumeX } from "lucide-react";

export default function Header({
  connected,
  running,
  health,
  soundEnabled,
  onToggleSound,
  onTestTelegram,
}) {
  const statusText = running
    ? "Поток данных"
    : connected
      ? "Подключено"
      : "Ожидание";

  return (
    <header className="header">
      <div className="brand">
        <div className="brand-mark">
          <Activity size={22} />
        </div>
        <div>
          <h1>AnomaLens</h1>
          <p>Мониторинг промышленного насоса · SKAB replay</p>
        </div>
      </div>

      <div className="header-actions">
        <span
          className={`status-pill ${running ? "live" : connected ? "connected" : "idle"}`}
        >
          <span className="status-dot" />
          {statusText}
        </span>
        <span
          className={`status-pill ${health?.telegram_configured ? "connected" : "idle"}`}
          title="Telegram-уведомления"
        >
          <Bell size={14} />
          {health?.telegram_configured ? "Telegram" : "TG off"}
        </span>
        <button
          type="button"
          className="icon-button"
          onClick={onToggleSound}
          title={soundEnabled ? "Выключить звук" : "Включить звук"}
        >
          {soundEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
        </button>
        <button type="button" className="ghost-button" onClick={onTestTelegram}>
          <Send size={15} />
          Тест TG
        </button>
      </div>
    </header>
  );
}
