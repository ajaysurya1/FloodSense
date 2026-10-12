import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchReports, submitReport } from '../../api'
import { Camera, MapPin, Upload } from 'lucide-react'

const REPORT_TYPES = [
  { value: 'flooded_street', label: 'Flooded Street' },
  { value: 'blocked_drain', label: 'Blocked Drain' },
  { value: 'impassable_road', label: 'Impassable Road' },
  { value: 'other', label: 'Other' },
]

function CorrBadge({ status }) {
  const classes = { corroborated: 'corr-corroborated', emerging: 'corr-emerging', unverified: 'corr-unverified' }
  return <span className={`corr-chip ${classes[status] || 'corr-unverified'}`}>{status}</span>
}

export default function ReportsTab() {
  const qc = useQueryClient()
  const fileRef = useRef()
  const [form, setForm] = useState({ report_type: 'flooded_street', note: '', lat: '', lon: '' })
  const [preview, setPreview] = useState(null)
  const [imageFile, setImageFile] = useState(null)
  const [locStatus, setLocStatus] = useState('')
  const [result, setResult] = useState(null)

  const { data: reportsData } = useQuery({
    queryKey: ['reports'],
    queryFn: fetchReports,
    refetchInterval: 20_000,
  })

  const mutation = useMutation({
    mutationFn: (fd) => submitReport(fd),
    onSuccess: (data) => {
      setResult(data)
      qc.invalidateQueries(['reports'])
    },
  })

  const handleImage = (file) => {
    if (!file) return
    setImageFile(file)
    const url = URL.createObjectURL(file)
    setPreview(url)
  }

  const locate = () => {
    setLocStatus('Locating…')
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        setForm(f => ({ ...f, lat: pos.coords.latitude.toFixed(6), lon: pos.coords.longitude.toFixed(6) }))
        setLocStatus('✅ Location captured')
      },
      () => setLocStatus('⚠️ Location failed – enter manually'),
      { timeout: 8000 }
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v))
    fd.append('ts', new Date().toISOString())
    if (imageFile) fd.append('image', imageFile)
    mutation.mutate(fd)
  }

  const reports = reportsData?.features || []

  return (
    <div>
      <div className="card">
        <div className="card-title">Submit Citizen Report</div>
        <p style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.5 }}>
          Reports are labelled <strong>unverified citizen reports</strong>. No flood depth is implied.
          Images are classified by AI (CLIP zero-shot) — not a guarantee of accuracy.
        </p>

        <form className="report-form" onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Report Type</label>
            <select
              id="report-type-select"
              className="form-control form-select"
              value={form.report_type}
              onChange={e => setForm(f => ({ ...f, report_type: e.target.value }))}
            >
              {REPORT_TYPES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>

          {/* Image upload */}
          <div className="form-group">
            <label className="form-label">Photo (optional)</label>
            <div
              className="upload-zone"
              onClick={() => fileRef.current?.click()}
              onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('drag-over') }}
              onDragLeave={e => e.currentTarget.classList.remove('drag-over')}
              onDrop={e => { e.preventDefault(); e.currentTarget.classList.remove('drag-over'); handleImage(e.dataTransfer.files[0]) }}
            >
              <Upload size={20} style={{ margin: '0 auto 6px', display: 'block' }} />
              Tap to capture or upload photo
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="environment"
                style={{ display: 'none' }}
                onChange={e => handleImage(e.target.files[0])}
              />
            </div>
            {preview && <img src={preview} alt="preview" className="upload-preview" />}
          </div>

          {/* Location */}
          <div className="form-group">
            <label className="form-label">Location</label>
            <button type="button" id="get-location-btn" className="btn btn-ghost btn-sm" onClick={locate} style={{ marginBottom: 6 }}>
              <MapPin size={12} /> Auto-detect Location
            </button>
            {locStatus && <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>{locStatus}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <input className="form-control" placeholder="Latitude" value={form.lat} onChange={e => setForm(f => ({ ...f, lat: e.target.value }))} required />
              <input className="form-control" placeholder="Longitude" value={form.lon} onChange={e => setForm(f => ({ ...f, lon: e.target.value }))} required />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Note (optional)</label>
            <textarea className="form-control" rows={2} placeholder="Brief description…" value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} style={{ resize: 'vertical' }} />
          </div>

          <button id="submit-report-btn" type="submit" className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? 'Submitting…' : 'Submit Report'}
          </button>
        </form>

        {/* Result */}
        {result && (
          <div style={{
            marginTop: 12, padding: '10px 12px',
            background: 'rgba(45,139,255,0.08)', borderRadius: 8,
            border: '1px solid rgba(45,139,255,0.2)',
            fontSize: '0.65rem', lineHeight: 1.6,
          }}>
            <div>✅ Report #{result.id} received</div>
            <div>AI label: <strong>{result.clip_label}</strong> ({(result.clip_score * 100).toFixed(0)}%)</div>
            <div>Corroboration: <CorrBadge status={result.corroboration} /></div>
            <div>Status: <strong>{result.status}</strong></div>
            {result.flags?.length > 0 && (
              <div style={{ color: 'var(--sev-warning-fg)', marginTop: 4 }}>
                ⚠️ Flagged: {result.flags.join('; ')}
              </div>
            )}
            <div style={{ color: 'var(--text-muted)', marginTop: 4, fontSize: '0.6rem' }}>
              {result.disclaimer}
            </div>
          </div>
        )}
      </div>

      {/* Recent reports */}
      <div className="card-title" style={{ marginTop: 4 }}>Recent Reports ({reports.length})</div>
      {reports.slice(0, 10).map((feat, i) => {
        const p = feat.properties
        return (
          <div key={i} className="card" style={{ padding: '10px 12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>{p.report_type?.replace(/_/g, ' ')}</span>
              <CorrBadge status={p.corroboration} />
            </div>
            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: 3 }}>
              {p.clip_label && <span>AI: {p.clip_label} ({(p.clip_score * 100 || 0).toFixed(0)}%) · </span>}
              Status: {p.status}
              {p.dup_count > 0 && <span> · {p.dup_count} duplicates merged</span>}
            </div>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: 2 }}>
              {p.ts?.slice(0, 19).replace('T', ' ')} UTC
            </div>
          </div>
        )
      })}
    </div>
  )
}
