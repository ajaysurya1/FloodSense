import { useQuery } from '@tanstack/react-query'
import { fetchSensors, fetchCctvStatus } from '../../api'
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

/** Badge colouring for CCTV depth labels */
function depthBadgeColor(label) {
  if (!label) return 'var(--text-muted)'
  if (label.includes('knee') || label.includes('deeper')) return 'var(--sev-severe-fg)'
  if (label.includes('ankle')) return '#f59e0b'
  if (label.includes('light')) return '#60a5fa'
  return 'var(--text-muted)'
}

function CctvCameraCard({ cam }) {
  const isOnline = cam.status === 'online'
  return (
    <div className="sensor-card" style={{ borderLeft: `3px solid ${isOnline ? '#3b82f6' : '#6b7280'}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div className="sensor-name">
            <StatusDot status={cam.status} />
            {cam.camera_label || cam.camera_id || '(unknown)'}
          </div>
          <div className="sensor-meta" style={{ display: 'flex', gap: 6 }}>
            <span className="simulated-tag" style={{ background: 'rgba(59,130,246,0.2)', color: '#60a5fa' }}>
              CCTV
            </span>
            <span>{cam.status}</span>
            {cam.ward_id && <span>· {cam.ward_id}</span>}
          </div>
        </div>
      </div>

      {isOnline ? (
        <>
          <div style={{ marginTop: 8, fontSize: '0.7rem' }}>
            <span style={{ color: depthBadgeColor(cam.last_label), fontWeight: 600 }}>
              {cam.last_label || '—'}
            </span>
            {cam.last_label_score !== undefined && cam.last_label_score !== null && (
              <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                ({(cam.last_label_score * 100).toFixed(0)}% confidence)
              </span>
            )}
          </div>
          {cam.last_level_cm !== null && cam.last_level_cm !== undefined ? (
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Visual proxy depth: <strong style={{ color: 'var(--text-primary)' }}>
                ~{cam.last_level_cm} cm
              </strong>{' '}
              <span style={{ color: '#f59e0b' }}>⚠️ UNCALIBRATED ESTIMATE</span>
            </div>
          ) : (
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 4 }}>
              View obstructed – no depth estimate posted.
            </div>
          )}
          {cam.last_seen && (
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Last frame: {new Date(cam.last_seen).toLocaleTimeString()}
            </div>
          )}
        </>
      ) : (
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 6 }}>
          {cam.error || 'Camera offline – retrying…'}
        </div>
      )}
    </div>
  )
}

export default function SensorsTab({ wardId }) {
  const { data, isLoading } = useQuery({
    queryKey: ['sensors', wardId],
    queryFn: () => fetchSensors(wardId),
    refetchInterval: 10_000,
  })

  const { data: cctvData, isLoading: cctvLoading } = useQuery({
    queryKey: ['cctv-status'],
    queryFn: fetchCctvStatus,
    refetchInterval: 20_000,
  })

  const devices = (data?.devices || []).filter(d => d.data_source !== 'CCTV')
  const cameras = cctvData?.cameras ? Object.entries(cctvData.cameras).map(([id, cam]) => ({ ...cam, camera_id: id })) : []
  const wardCameras = wardId ? cameras.filter(c => !c.ward_id || c.ward_id === wardId) : cameras

  return (
    <div>
      {/* ── IoT nodes ─────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">IoT Water-Level Nodes</div>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>
          {isLoading ? 'Loading…' : (
            <>
              {devices.filter(d => d.status === 'online').length} online ·{' '}
              {devices.filter(d => d.data_source === 'SIMULATED').length} SIMULATED ·{' '}
              Data source shown on each card
            </>
          )}
        </div>
      </div>

      {!isLoading && devices.length === 0 && (
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

      {/* ── CCTV Cameras ──────────────────────────────────────── */}
      <div className="card" style={{ margin: '18px 0 14px' }}>
        <div className="card-title">📷 CCTV Virtual Sensors</div>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
          {cctvLoading ? 'Loading…' : (
            <>
              {wardCameras.filter(c => c.status === 'online').length} online ·{' '}
              {wardCameras.length} configured
            </>
          )}
        </div>
        <div style={{ fontSize: '0.55rem', color: '#f59e0b', marginTop: 4 }}>
          ⚠️ Depth values are UNCALIBRATED VISUAL PROXIES — not measured depths.
          They feed the same sensor override logic as physical nodes (tagged CCTV).
        </div>
      </div>

      {!cctvLoading && wardCameras.length === 0 && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', padding: 12 }}>
          No cameras configured for this ward. Add entries to cameras.json.
        </div>
      )}

      {wardCameras.map(cam => (
        <CctvCameraCard key={cam.camera_id} cam={cam} />
      ))}

      {cctvData?.disclaimer && (
        <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: 12, lineHeight: 1.5 }}>
          {cctvData.disclaimer}
        </div>
      )}
    </div>
  )
}
