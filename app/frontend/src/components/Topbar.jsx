export default function Topbar({ mode, ward, wards, wardId, setWardId }) {
  return (
    <header className="topbar">
      <div className="logo">
        <span className="logo-icon">🌊</span>
        FloodSense
      </div>

      {/* Ward selector – switches instantly via React Query key invalidation */}
      <div className="ward-selector">
        <label htmlFor="ward-select" style={{
          fontSize: '0.6rem', color: 'var(--text-muted)',
          marginRight: 6, textTransform: 'uppercase', letterSpacing: '0.06em',
        }}>Ward</label>
        <select
          id="ward-select"
          value={wardId || ''}
          onChange={e => setWardId(e.target.value)}
          className="ward-select"
        >
          {wards.map(w => (
            <option key={w.ward_id} value={w.ward_id}>
              {w.name} {w.ward_no ? `(#${w.ward_no})` : ''}
            </option>
          ))}
        </select>
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
