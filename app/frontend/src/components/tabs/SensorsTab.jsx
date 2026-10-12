import { useQuery } from '@tanstack/react-query'
import { fetchSensors } from '../../api'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

function StatusDot({ status }) {
  return <span className={`status-dot status-${status}`} />
}

function Sparkline({ data }) {
  if (!data || data.length < 2) return null
  return (
    <div className="sparkline-wrap">
      <ResponsiveContainer width="100%" height={36}>
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="level"
            stroke="#00d4ff"
            strokeWidth={1.5}
            dot={false}
          />
          <Tooltip
            contentStyle={{ background: '#0f2040', border: 'none', fontSize: 10 }}
            formatter={v => [`${v.toFixed(1)} cm`, 'Level']}
            labelFormatter={() => ''}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function SensorsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['sensors'],
    queryFn: fetchSensors,
    refetchInterval: 10_000,
  })

  if (isLoading) return <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Loading sensors…</div>

  const devices = data?.devices || []

  return (
    <div>
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">IoT Water-Level Nodes</div>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>
          {devices.filter(d => d.status === 'online').length} online · 
          {devices.filter(d => d.data_source === 'SIMULATED').length} SIMULATED ·
          Data source shown on each card
        </div>
      </div>

      {devices.length === 0 && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', padding: 20 }}>
          No sensors registered. Run simulate_sensors.py to populate.
        </div>
      )}

      {devices.map(s => (
        <div key={s.device_id} className={`sensor-card ${s.alert_active ? 'alert-active' : ''}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div className="sensor-name">
                <StatusDot status={s.status} />
                {s.device_id}
              </div>
              <div className="sensor-meta" style={{ display: 'flex', gap: 6 }}>
                <span className="simulated-tag">{s.data_source}</span>
                <span>{s.status} · {s.age_min?.toFixed(0)}min ago</span>
              </div>
            </div>
            {s.alert_active && (
              <div style={{ fontSize: '0.6rem', fontWeight: 700, color: 'var(--sev-severe-fg)', animation: 'pulse-severe 1.5s infinite' }}>
                ⚠️ OVERRIDE
              </div>
            )}
          </div>

          <div className="sensor-level">{(s.last_level ?? 0).toFixed(1)}<span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>cm</span></div>
          <div className="sensor-ror">
            Rate of rise: <strong style={{ color: s.rate_of_rise > 4 ? 'var(--sev-severe-fg)' : 'var(--text-primary)' }}>
              {(s.rate_of_rise ?? 0).toFixed(1)} cm/5min
            </strong>
          </div>

          <Sparkline data={s.sparkline} />

          <div style={{ display: 'flex', gap: 12, fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: 4 }}>
            {s.battery_pct !== null && s.battery_pct !== undefined && (
              <span>🔋 {s.battery_pct?.toFixed(0)}%</span>
            )}
            {s.rssi && <span>📶 {s.rssi} dBm</span>}
          </div>

          {s.alert_reason && (
            <div style={{
              marginTop: 8, padding: '6px 8px',
              background: 'rgba(239,68,68,0.1)', borderRadius: 6,
              fontSize: '0.6rem', color: 'var(--sev-severe-fg)', lineHeight: 1.4,
            }}>
              ⚠️ {s.alert_reason}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
