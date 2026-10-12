export default function Topbar({ mode, ward }) {
  return (
    <header className="topbar">
      <div className="logo">
        <span className="logo-icon">🌊</span>
        FloodSense
        {ward && (
          <span style={{ fontSize: '0.65rem', fontWeight: 400, color: 'var(--text-muted)' }}>
            · {ward.name}, {ward.city}
          </span>
        )}
      </div>

      <div className={`mode-badge ${mode === 'LIVE' ? 'live' : 'scenario'}`}>
        <span className="pulse-dot" />
        {mode === 'LIVE' ? '🟢 LIVE MODE' : '🟡 SCENARIO MODE – SIMULATED STORM'}
      </div>

      <div className="disclaimer-banner">
        ⚠️ All risk outputs are <strong>heuristic, uncalibrated estimates</strong>.
        Complements NDMA SACHET; does not replace official warnings.
      </div>
    </header>
  )
}
