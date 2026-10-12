import { useQuery } from '@tanstack/react-query'
import { fetchRisk } from '../../api'

const SEV_ORDER = { Severe: 0, Warning: 1, Watch: 2, Normal: 3 }

export default function RiskTab({ selectedCell, horizon, wardId }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['risk', horizon, wardId],
    queryFn: () => fetchRisk(horizon, wardId),
    refetchInterval: 60_000,
  })

  if (isLoading) return <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Computing risk grid…</div>
  if (error) return <div style={{ color: 'var(--text-danger)', fontSize: '0.75rem' }}>Error fetching risk data. Check backend.</div>

  const cells = (data?.features || [])
    .filter(f => f.properties.severity !== 'Normal')
    .sort((a, b) => (SEV_ORDER[a.properties.severity] ?? 9) - (SEV_ORDER[b.properties.severity] ?? 9) || b.properties.score - a.properties.score)
    .slice(0, 15)

  const meta = data?.metadata

  return (
    <div>
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">Risk Summary · {horizon}min Horizon</div>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: 8 }}>
          {meta?.cell_count} cells · Mode: <strong>{meta?.mode}</strong>
        </div>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', lineHeight: 1.4, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          {meta?.disclaimer}
        </div>
      </div>

      {selectedCell && (
        <div className="card" style={{ borderColor: 'rgba(45,139,255,0.35)', marginBottom: 14 }}>
          <div className="card-title">Selected Cell · {selectedCell.severity}</div>
          <div style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
            Score: {selectedCell.score?.toFixed(0)}/100
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: 6 }}>
            Onset: <strong>{selectedCell.onset_window}</strong>
          </div>
          <div className="reasons-list" style={{ marginTop: 8 }}>
            {(selectedCell.reasons || []).map((r, i) => (
              <div key={i} className="reason-chip">{r}</div>
            ))}
          </div>
        </div>
      )}

      <div className="card-title">High-Risk Cells</div>
      {cells.length === 0 ? (
        <div style={{ color: 'var(--sev-normal-fg)', fontSize: '0.75rem', padding: 12, textAlign: 'center' }}>
          ✅ No cells above Watch threshold at {horizon}min horizon
        </div>
      ) : (
        cells.map(f => {
          const p = f.properties
          const sevClass = `sev-${(p.severity || 'normal').toLowerCase()}`
          return (
            <div key={p.cell_id} className="card" style={{ padding: '10px 12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className={`sev-badge ${sevClass}`}>{p.severity}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.9rem', color: 'var(--accent-cyan)' }}>
                  {p.score.toFixed(0)}
                </span>
              </div>
              <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Onset: {p.onset_window} · Conf: {p.confidence}
              </div>
              <div style={{ fontSize: '0.6rem', color: 'var(--text-secondary)', marginTop: 3 }}>
                Rain {p.rain_intensity_mm_3h} mm/3h · {p.forecast_source}
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}
