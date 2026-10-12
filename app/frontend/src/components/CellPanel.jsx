export default function CellPanel({ cell, onClose }) {
  const score = cell.score || 0
  const barColor = score >= 80 ? '#ef4444' : score >= 60 ? '#f97316' : score >= 35 ? '#fbbf24' : '#4ade80'
  const sevClass = `sev-${(cell.severity || 'normal').toLowerCase()}`

  return (
    <div className="cell-panel" id="cell-detail-panel">
      <button className="cell-panel-close" onClick={onClose} aria-label="Close">✕</button>

      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: 4 }}>
          CELL {cell.cell_id} · {cell.lat?.toFixed(4)}, {cell.lon?.toFixed(4)}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`sev-badge ${sevClass}`}>{cell.severity}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '1.4rem', fontWeight: 700, color: barColor }}>
            {score.toFixed(0)}
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 2 }}>/100</span>
          </span>
        </div>
      </div>

      {/* Score bar */}
      <div className="risk-bar-wrap">
        <div className="risk-bar" style={{ width: `${score}%`, background: barColor }} />
      </div>

      {/* Key metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
        {[
          ['Onset Window', cell.onset_window || '—'],
          ['Confidence', cell.confidence || '—'],
          ['Rain (3h)', `${cell.rain_intensity_mm_3h ?? '—'} mm`],
          ['Cumul. Rain', `${cell.cumulative_rain_mm ?? '—'} mm`],
          ['Elev. (m)', cell.elevation_m ?? '—'],
          ['Forecast', cell.forecast_source || '—'],
        ].map(([label, val]) => (
          <div key={label} style={{ background: 'var(--bg-surface)', borderRadius: 6, padding: '6px 8px' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-primary)', fontFamily: label === 'Onset Window' ? 'var(--font-mono)' : undefined }}>
              {val}
            </div>
          </div>
        ))}
      </div>

      {/* Confidence notes */}
      {cell.confidence_notes?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Why {cell.confidence} Confidence
          </div>
          {cell.confidence_notes.map((n, i) => (
            <div key={i} className="reason-chip" style={{ color: 'var(--sev-watch-fg)' }}>△ {n}</div>
          ))}
        </div>
      )}

      {/* Reasons */}
      <div>
        <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
          Risk Drivers
        </div>
        <div className="reasons-list">
          {(cell.reasons || []).map((r, i) => (
            <div key={i} className="reason-chip">{r}</div>
          ))}
        </div>
      </div>

      {/* Disclaimer */}
      <div style={{
        marginTop: 12, padding: '8px 10px',
        background: 'rgba(239,68,68,0.06)', borderRadius: 6,
        border: '1px solid rgba(239,68,68,0.15)',
        fontSize: '0.6rem', color: 'var(--text-muted)', lineHeight: 1.4,
      }}>
        {cell.disclaimer}
      </div>
    </div>
  )
}
