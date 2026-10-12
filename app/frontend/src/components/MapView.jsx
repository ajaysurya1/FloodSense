import { useEffect, useRef, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, useMap } from 'react-leaflet'
import { useQuery } from '@tanstack/react-query'
import { fetchRisk, fetchSensors, fetchReports } from '../api'
import CellPanel from './CellPanel'
import 'leaflet/dist/leaflet.css'

const SEVERITY_COLORS = {
  Normal:  '#1a3a2a',
  Watch:   '#b45309',
  Warning: '#c2410c',
  Severe:  '#991b1b',
}

const HORIZONS = [30, 60, 120, 180]

function MapCentrer({ ward }) {
  const map = useMap()
  useEffect(() => {
    if (ward?.centre) {
      map.setView([ward.centre.lat, ward.centre.lon], 14)
    }
  }, [ward, map])
  return null
}

export default function MapView({ horizon, setHorizon, selectedCell, setSelectedCell, ward, mode }) {
  const defaultCenter = ward?.centre
    ? [ward.centre.lat, ward.centre.lon]
    : [13.0155, 80.2462]

  const { data: riskData, isLoading: riskLoading, dataUpdatedAt } = useQuery({
    queryKey: ['risk', horizon],
    queryFn: () => fetchRisk(horizon),
    refetchInterval: 60_000,
  })

  const { data: sensorData } = useQuery({
    queryKey: ['sensors'],
    queryFn: fetchSensors,
    refetchInterval: 15_000,
  })

  const { data: reportData } = useQuery({
    queryKey: ['reports'],
    queryFn: fetchReports,
    refetchInterval: 30_000,
  })

  const cellStyle = (feature) => {
    const sev = feature.properties.severity
    return {
      fillColor: SEVERITY_COLORS[sev] || '#1a3a2a',
      fillOpacity: sev === 'Normal' ? 0.15 : 0.55,
      color: sev === 'Severe' ? '#ef4444' : sev === 'Warning' ? '#f97316' : 'rgba(45,139,255,0.3)',
      weight: sev === 'Normal' ? 0.3 : 1,
    }
  }

  const onCellClick = (feature, layer) => {
    layer.on('click', () => setSelectedCell(feature.properties))
  }

  const sensorStatus = (s) => s.status === 'online' ? '#4ade80' : s.status === 'stale' ? '#fbbf24' : '#6b7280'

  const reportColor = (feat) => {
    const c = feat.properties.corroboration
    if (c === 'corroborated') return '#4ade80'
    if (c === 'emerging')     return '#f97316'
    return '#6b7280'
  }

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      {/* Controls */}
      <div className="map-controls">
        <div className="horizon-control">
          <label>Forecast Horizon</label>
          <div className="horizon-slider">
            {HORIZONS.map(h => (
              <button
                key={h}
                className={`horizon-btn ${horizon === h ? 'active' : ''}`}
                onClick={() => setHorizon(h)}
                id={`horizon-btn-${h}`}
              >
                {h}m
              </button>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="map-legend">
          <div className="legend-title">Risk Level</div>
          {[['Severe', '#991b1b'], ['Warning', '#c2410c'], ['Watch', '#b45309'], ['Normal', '#1a3a2a']].map(([label, color]) => (
            <div key={label} className="legend-row">
              <div className="legend-swatch" style={{ background: color }} />
              {label}
            </div>
          ))}
          <div className="divider" style={{ margin: '6px 0' }} />
          <div className="legend-row"><div className="legend-swatch" style={{ background: '#4ade80', borderRadius: '50%' }} />Sensor (online)</div>
          <div className="legend-row"><div className="legend-swatch" style={{ background: '#f97316', borderRadius: '50%' }} />Report (emerging)</div>
          {mode === 'SCENARIO' && (
            <div style={{ marginTop: 6, padding: '4px 6px', background: 'rgba(251,191,36,0.1)', borderRadius: 4, fontSize: '0.6rem', color: '#fbbf24' }}>
              ⚠️ SIMULATED STORM DATA
            </div>
          )}
        </div>

        {/* Data freshness */}
        {dataUpdatedAt && (
          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', padding: '4px 8px', background: 'var(--bg-glass)', backdropFilter: 'blur(8px)', borderRadius: 6 }}>
            Updated: {new Date(dataUpdatedAt).toLocaleTimeString()}
          </div>
        )}
      </div>

      <MapContainer
        center={defaultCenter}
        zoom={14}
        style={{ height: '100%', width: '100%', background: '#050a14' }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          maxZoom={19}
        />
        {ward && <MapCentrer ward={ward} />}

        {/* Risk cells */}
        {riskData && (
          <GeoJSON
            key={`risk-${horizon}-${dataUpdatedAt}`}
            data={riskData}
            style={cellStyle}
            onEachFeature={onCellClick}
          />
        )}

        {/* Sensor nodes */}
        {sensorData?.devices?.map(sensor => (
          <CircleMarker
            key={sensor.device_id}
            center={[sensor.lat || 13.0132, sensor.lon || 80.2448]}
            radius={sensor.alert_active ? 10 : 7}
            pathOptions={{
              color: sensorStatus(sensor),
              fillColor: sensorStatus(sensor),
              fillOpacity: 0.9,
              weight: sensor.alert_active ? 3 : 1,
            }}
          >
            <Popup>
              <div style={{ minWidth: 180, fontFamily: 'Inter, sans-serif', fontSize: 12 }}>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>{sensor.device_id}</div>
                <div>Level: <strong>{sensor.last_level?.toFixed(1)} cm</strong></div>
                <div>Rise: {sensor.rate_of_rise?.toFixed(1)} cm/5min</div>
                <div>Battery: {sensor.battery_pct?.toFixed(0)}%</div>
                <div style={{ color: '#fbbf24', fontSize: 10, marginTop: 4 }}>
                  Source: {sensor.data_source}
                </div>
                {sensor.alert_active && (
                  <div style={{ color: '#ef4444', fontWeight: 700, marginTop: 4 }}>
                    ⚠️ GROUND OVERRIDE ACTIVE
                  </div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Citizen reports */}
        {reportData?.features?.map((feat, i) => (
          <CircleMarker
            key={i}
            center={[feat.geometry.coordinates[1], feat.geometry.coordinates[0]]}
            radius={5}
            pathOptions={{
              color: reportColor(feat),
              fillColor: reportColor(feat),
              fillOpacity: 0.7,
              weight: 2,
              dashArray: feat.properties.status === 'flagged' ? '4,2' : null,
            }}
          >
            <Popup>
              <div style={{ minWidth: 160, fontFamily: 'Inter, sans-serif', fontSize: 12 }}>
                <div style={{ fontWeight: 700 }}>Citizen Report</div>
                <div>Type: {feat.properties.report_type}</div>
                <div>Label: {feat.properties.clip_label}</div>
                <div>Corr: <strong>{feat.properties.corroboration}</strong></div>
                <div style={{ fontSize: 10, color: '#8bafd6', marginTop: 4 }}>
                  Unverified citizen report. No depth implied.
                </div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Cell detail panel */}
      {selectedCell && (
        <CellPanel cell={selectedCell} onClose={() => setSelectedCell(null)} />
      )}

      {riskLoading && (
        <div className="loading-overlay">
          <div className="spinner" />
        </div>
      )}
    </div>
  )
}
