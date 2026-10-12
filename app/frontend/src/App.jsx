import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMode, fetchWard } from './api'
import MapView from './components/MapView'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'

export default function App() {
  const [horizon, setHorizon] = useState(60)
  const [selectedCell, setSelectedCell] = useState(null)
  const [activeTab, setActiveTab] = useState('risk')

  const { data: modeData } = useQuery({
    queryKey: ['mode'],
    queryFn: fetchMode,
    refetchInterval: 30_000,
  })

  const { data: ward } = useQuery({
    queryKey: ['ward'],
    queryFn: fetchWard,
  })

  const mode = modeData?.mode || 'LIVE'

  return (
    <div className="app-layout">
      <Topbar mode={mode} ward={ward} />
      <div className="map-area">
        <MapView
          horizon={horizon}
          setHorizon={setHorizon}
          selectedCell={selectedCell}
          setSelectedCell={setSelectedCell}
          ward={ward}
          mode={mode}
        />
      </div>
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedCell={selectedCell}
        horizon={horizon}
        mode={mode}
        ward={ward}
      />
    </div>
  )
}
