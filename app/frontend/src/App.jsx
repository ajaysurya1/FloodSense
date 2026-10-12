import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMode, fetchWards } from './api'
import MapView from './components/MapView'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'

export default function App() {
  const [horizon, setHorizon] = useState(60)
  const [selectedCell, setSelectedCell] = useState(null)
  const [activeTab, setActiveTab] = useState('risk')
  const [wardId, setWardId] = useState(null)  // null → first ward (resolved below)

  const { data: modeData } = useQuery({
    queryKey: ['mode'],
    queryFn: fetchMode,
    refetchInterval: 30_000,
  })

  const { data: wards } = useQuery({
    queryKey: ['wards'],
    queryFn: fetchWards,
    staleTime: 5 * 60_000,  // ward list rarely changes
    onSuccess: (data) => {
      // Auto-select first ward if no selection yet
      if (!wardId && Array.isArray(data) && data.length > 0) {
        setWardId(data[0].ward_id)
      }
    },
  })

  const mode = modeData?.mode || 'LIVE'

  // Resolve the active ward object from the list
  const activeWardId = wardId || (wards?.[0]?.ward_id ?? null)
  const activeWard = wards?.find(w => w.ward_id === activeWardId) || wards?.[0] || null

  return (
    <div className="app-layout">
      <Topbar
        mode={mode}
        ward={activeWard}
        wards={wards || []}
        wardId={activeWardId}
        setWardId={(id) => {
          setWardId(id)
          setSelectedCell(null)  // clear cell selection on ward switch
        }}
      />
      <div className="map-area">
        <MapView
          horizon={horizon}
          setHorizon={setHorizon}
          selectedCell={selectedCell}
          setSelectedCell={setSelectedCell}
          ward={activeWard}
          wardId={activeWardId}
          mode={mode}
        />
      </div>
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedCell={selectedCell}
        horizon={horizon}
        mode={mode}
        ward={activeWard}
        wardId={activeWardId}
      />
    </div>
  )
}
