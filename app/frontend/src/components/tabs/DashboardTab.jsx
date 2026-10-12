import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchDashboard, createTask } from '../../api'

const SEV_COLORS = { Severe: '#ef4444', Warning: '#f97316', Watch: '#fbbf24', Normal: '#4ade80' }
const FAC_ICONS = { hospital: '🏥', school: '🏫', shelter: '⛺' }

export default function DashboardTab({ horizon, wardId }) {
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', horizon, wardId],
    queryFn: () => fetchDashboard(horizon, wardId),
    refetchInterval: 60_000,
  })

  const taskMutation = useMutation({
    mutationFn: (payload) => createTask(payload),
    onSuccess: () => qc.invalidateQueries(['tasks']),
  })

  if (isLoading) return <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Loading dashboard…</div>

  const topCells = data?.top_risk_cells || []
  const facilities = data?.flagged_facilities || []
  const reports = data?.report_counts || {}
  const sensorAlerts = data?.active_sensor_alerts || []

  return (
    <div>
      {/* Disclaimer */}
      <div style={{
        background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)',
        borderRadius: 8, padding: '8px 12px', marginBottom: 14, fontSize: '0.6rem',
        color: 'var(--text-muted)', lineHeight: 1.4,
      }}>
        {data?.disclaimer}
      </div>

      {/* Quick stats */}
      <div className="metric-grid" style={{ marginBottom: 14 }}>
        <div className="metric-tile">
          <div className="metric-val" style={{ color: '#ef4444' }}>
            {topCells.filter(c => c.severity === 'Severe').length}
          </div>
          <div className="metric-label">Severe Cells</div>
        </div>
        <div className="metric-tile">
          <div className="metric-val" style={{ color: '#f97316' }}>
            {topCells.filter(c => c.severity === 'Warning').length}
          </div>
          <div className="metric-label">Warning Cells</div>
        </div>
        <div className="metric-tile">
          <div className="metric-val" style={{ color: '#ef4444', fontSize: '1.1rem' }}>
            {sensorAlerts.length}
          </div>
          <div className="metric-label">Sensor Overrides</div>
        </div>
        <div className="metric-tile">
          <div className="metric-val" style={{ color: '#4ade80', fontSize: '1.1rem' }}>
            {facilities.length}
          </div>
          <div className="metric-label">At-Risk Facilities</div>
        </div>
      </div>

      {/* Flagged facilities */}
      {facilities.length > 0 && (
        <div>
          <div className="card-title">⚠️ At-Risk Critical Facilities (SEED data)</div>
          {facilities.map((f, i) => (
            <div key={i} className="facility-chip">
              <span className="facility-icon">{FAC_ICONS[f.type] || '📍'}</span>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 600 }}>{f.name}</div>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>
                  Capacity: {f.capacity} · Risk: <span style={{ color: SEV_COLORS[f.severity] }}>{f.severity}</span> ({f.risk_score?.toFixed(0)})
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sensor alerts */}
      {sensorAlerts.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="card-title">⚡ Active Sensor Override Alerts</div>
          {sensorAlerts.map((s, i) => (
            <div key={i} className="card" style={{ borderColor: 'rgba(239,68,68,0.4)', padding: '10px 12px' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--sev-severe-fg)' }}>
                {s.device_id} <span className="simulated-tag">{s.data_source}</span>
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>
                Level: {s.last_level?.toFixed(1)} cm · Rise: {s.rate_of_rise?.toFixed(1)} cm/5min
              </div>
              <button
                className="btn btn-sm btn-danger"
                style={{ marginTop: 6 }}
                onClick={() => taskMutation.mutate({
                  title: `URGENT: Sensor ${s.device_id} override – check water level`,
                  location: `Sensor ${s.device_id}`,
                  priority: 'high',
                  source_type: 'sensor',
                })}
              >
                → Create Task
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Top risk cells with actions */}
      <div style={{ marginTop: 12 }}>
        <div className="card-title">Ranked Risk Locations · {horizon}min Horizon</div>
        {topCells.length === 0 ? (
          <div style={{ color: 'var(--sev-normal-fg)', fontSize: '0.75rem', textAlign: 'center', padding: 12 }}>
            ✅ No high-risk cells at this horizon
          </div>
        ) : (
          topCells.map((cell, i) => (
            <div key={cell.cell_id} className="card" style={{ padding: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', minWidth: 16 }}>#{i + 1}</span>
                  <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', fontWeight: 700, color: SEV_COLORS[cell.severity] }}>
                    {cell.score.toFixed(0)}
                  </span>
                  <span className={`sev-badge sev-${cell.severity.toLowerCase()}`}>{cell.severity}</span>
                </div>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>
                  Conf: {cell.confidence}
                </div>
              </div>

              <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: 6 }}>
                Onset: <strong>{cell.onset_window}</strong>
                {cell.nearby_sensor && <span> · Sensor: {cell.nearby_sensor}</span>}
              </div>

              {/* Actions */}
              <div style={{ marginBottom: 8 }}>
                {cell.actions?.map((action, ai) => (
                  <div key={ai} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                    padding: '4px 0', borderBottom: '1px solid var(--border)',
                    fontSize: '0.6rem', color: 'var(--text-secondary)', gap: 8,
                  }}>
                    <span>▶ {action}</span>
                    <button
                      className="btn btn-sm btn-ghost"
                      style={{ fontSize: '0.55rem', padding: '2px 6px', flexShrink: 0 }}
                      onClick={() => taskMutation.mutate({
                        title: action,
                        location: cell.cell_id,
                        priority: cell.severity === 'Severe' ? 'high' : 'medium',
                        source_type: 'risk',
                        source_id: i,
                      })}
                    >
                      + Task
                    </button>
                  </div>
                ))}
              </div>

              {/* Report count */}
              {reports.pending > 0 && (
                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>
                  Reports: {reports.pending || 0} pending · {reports.corroborated || 0} corroborated
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Report counts */}
      <div style={{ marginTop: 12 }}>
        <div className="card-title">Citizen Report Summary</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {Object.entries(reports).map(([status, cnt]) => (
            <div key={status} style={{
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '6px 12px', textAlign: 'center',
            }}>
              <div style={{ fontSize: '1rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{cnt}</div>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{status}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
