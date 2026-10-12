import { useState } from 'react'
import {
  Map, Wifi, MessageSquare, Bell, CheckSquare, BarChart2
} from 'lucide-react'
import RiskTab from './tabs/RiskTab'
import SensorsTab from './tabs/SensorsTab'
import ReportsTab from './tabs/ReportsTab'
import AlertsTab from './tabs/AlertsTab'
import TasksTab from './tabs/TasksTab'
import DashboardTab from './tabs/DashboardTab'

const TABS = [
  { id: 'risk',      label: 'Risk',      Icon: Map },
  { id: 'sensors',   label: 'Sensors',   Icon: Wifi },
  { id: 'reports',   label: 'Reports',   Icon: MessageSquare },
  { id: 'alerts',    label: 'Alerts',    Icon: Bell },
  { id: 'tasks',     label: 'Tasks',     Icon: CheckSquare },
  { id: 'dashboard', label: 'Dashboard', Icon: BarChart2 },
]

export default function Sidebar({ activeTab, setActiveTab, selectedCell, horizon, mode, ward }) {
  return (
    <aside className="sidebar">
      <div className="tab-bar">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            id={`tab-${id}`}
            className={`tab-btn ${activeTab === id ? 'active' : ''}`}
            onClick={() => setActiveTab(id)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === 'risk'      && <RiskTab selectedCell={selectedCell} horizon={horizon} />}
        {activeTab === 'sensors'   && <SensorsTab />}
        {activeTab === 'reports'   && <ReportsTab />}
        {activeTab === 'alerts'    && <AlertsTab ward={ward} />}
        {activeTab === 'tasks'     && <TasksTab />}
        {activeTab === 'dashboard' && <DashboardTab horizon={horizon} />}
      </div>
    </aside>
  )
}
