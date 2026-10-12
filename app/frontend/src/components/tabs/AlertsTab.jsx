import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchAlerts, generateAlert } from '../../api'

const STAGES = ['WATCH', 'WARNING', 'URGENT']
const STAGE_COLORS = { WATCH: 'var(--sev-watch-fg)', WARNING: 'var(--sev-warning-fg)', URGENT: 'var(--sev-severe-fg)' }

function PhoneCard({ content, channel, stage }) {
  return (
    <div className="phone-card" data-channel={channel} style={{
      borderLeftColor: STAGE_COLORS[stage],
      borderLeftWidth: 3,
      borderLeftStyle: 'solid',
    }}>
      <div style={{ position: 'absolute', top: -8, right: 12 }}>
        <span className="simulated-tag">SIMULATED {channel}</span>
      </div>
      <div style={{ marginTop: 8 }}>{content}</div>
      <div style={{
        marginTop: 10, padding: '6px 8px',
        background: 'rgba(239,68,68,0.06)', borderRadius: 4,
        fontSize: '0.55rem', color: 'var(--text-muted)',
      }}>
        ⚠️ Complements official NDMA SACHET warnings; follow government-authorised alerts.
        No real message sent.
      </div>
    </div>
  )
}

export default function AlertsTab({ ward }) {
  const qc = useQueryClient()
  const [stage, setStage] = useState('WATCH')
  const [area, setArea] = useState('Kotturpuram Main Road')
  const [generatedAlerts, setGeneratedAlerts] = useState([])
  const [showCap, setShowCap] = useState(false)

  const { data: alertLog } = useQuery({
    queryKey: ['alerts'],
    queryFn: fetchAlerts,
    refetchInterval: 15_000,
  })

  const mutation = useMutation({
    mutationFn: (payload) => generateAlert(payload),
    onSuccess: (data) => {
      setGeneratedAlerts(data.alerts || [])
      qc.invalidateQueries(['alerts'])
    },
  })

  const generate = () => {
    mutation.mutate({
      area,
      stage,
      onset_window: stage === 'URGENT' ? 'Imminent' : stage === 'WARNING' ? '30–60 min' : '60–120 min',
      confidence: 'Medium',
      reasons: ['High rainfall forecast', 'Near historical hotspot (SEED)', 'Low-capacity drain nearby (SEED)'],
      drain_name: 'Kotturpuram Main Road Storm Drain',
      street: 'Kotturpuram Main Road',
      shelter_name: 'MRTS Kotturpuram Evacuation Point',
      trigger_reason: stage === 'URGENT' ? 'Ground sensor override: rapid water rise' : '',
      data_sources: 'Open-Meteo (LIVE), terrain (SEED), hotspots (SEED), sensors (SIMULATED)',
      languages: ['en', 'ta'],
      audiences: ['resident', 'official'],
      channels: ['SMS', 'WhatsApp'],
    })
  }

  const enResident = generatedAlerts.find(a => a.language === 'en' && a.audience === 'resident')
  const taResident = generatedAlerts.find(a => a.language === 'ta' && a.audience === 'resident')
  const enOfficial = generatedAlerts.find(a => a.language === 'en' && a.audience === 'official')
  const capAlert = generatedAlerts.find(a => a.cap_xml)

  return (
    <div>
      <div className="card">
        <div className="card-title">Generate Alert Preview</div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
          {STAGES.map(s => (
            <button
              key={s}
              id={`alert-stage-${s.toLowerCase()}`}
              onClick={() => setStage(s)}
              className="btn btn-sm"
              style={{
                flex: 1,
                background: stage === s ? (s === 'URGENT' ? 'rgba(239,68,68,0.25)' : s === 'WARNING' ? 'rgba(249,115,22,0.25)' : 'rgba(251,191,36,0.25)') : 'var(--bg-surface)',
                border: `1px solid ${stage === s ? STAGE_COLORS[s] : 'var(--border)'}`,
                color: stage === s ? STAGE_COLORS[s] : 'var(--text-muted)',
              }}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="form-group" style={{ marginBottom: 10 }}>
          <label className="form-label">Area</label>
          <input className="form-control" value={area} onChange={e => setArea(e.target.value)} />
        </div>
        <button id="generate-alert-btn" className="btn btn-primary" style={{ width: '100%' }} onClick={generate} disabled={mutation.isPending}>
          {mutation.isPending ? 'Generating…' : `Generate ${stage} Alert`}
        </button>
      </div>

      {/* Phone previews */}
      {generatedAlerts.length > 0 && (
        <div>
          <div className="card-title" style={{ marginBottom: 10 }}>📱 Simulated Message Previews</div>

          {enResident && (
            <>
              <PhoneCard content={enResident.content} channel="SMS" stage={stage} />
              <PhoneCard content={enResident.content} channel="WhatsApp" stage={stage} />
            </>
          )}

          {taResident && (
            <div>
              <div style={{ fontSize: '0.6rem', color: 'var(--accent-cyan)', marginBottom: 6, marginTop: 8 }}>
                Tamil / தமிழ்
                <span style={{ color: 'var(--sev-watch-fg)', marginLeft: 8 }}>
                  ⚠️ Needs review by native speaker before real use
                </span>
              </div>
              <PhoneCard content={taResident.content} channel="SMS" stage={stage} />
            </div>
          )}

          {enOfficial && (
            <div>
              <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: 6, marginTop: 8, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
                Official Channel
              </div>
              <div className="card" style={{ fontSize: '0.65rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {enOfficial.content}
              </div>
            </div>
          )}

          {/* CAP XML */}
          {capAlert?.cap_xml && (
            <div>
              <button className="btn btn-ghost btn-sm" style={{ marginBottom: 6 }} onClick={() => setShowCap(!showCap)}>
                {showCap ? 'Hide' : 'Show'} CAP 1.2 XML (format demo)
              </button>
              {showCap && (
                <pre style={{
                  background: 'var(--bg-surface)', borderRadius: 6, padding: 10,
                  fontSize: '0.6rem', color: 'var(--text-muted)', overflow: 'auto',
                  maxHeight: 200, lineHeight: 1.4,
                }}>
                  {capAlert.cap_xml}
                </pre>
              )}
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>
                Format demo only — not transmitted to SACHET
              </div>
            </div>
          )}
        </div>
      )}

      {/* Alert log */}
      <div className="card-title" style={{ marginTop: 16, marginBottom: 8 }}>Alert Log</div>
      {(alertLog?.alerts || []).length === 0 ? (
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'center', padding: 12 }}>No alerts generated yet</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="alert-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Stage</th>
                <th>Area</th>
                <th>Lang</th>
                <th>Audience</th>
              </tr>
            </thead>
            <tbody>
              {(alertLog?.alerts || []).slice(0, 20).map(a => (
                <tr key={a.id}>
                  <td className="mono">{a.created_at?.slice(11, 19)}</td>
                  <td><span style={{ color: STAGE_COLORS[a.stage] || 'inherit', fontWeight: 700, fontSize: '0.6rem' }}>{a.stage}</span></td>
                  <td>{a.area}</td>
                  <td>{a.language?.toUpperCase()}</td>
                  <td>{a.audience}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
