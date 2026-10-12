import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchTasks, fetchTaskMetrics, createTask, updateTask } from '../../api'

const STATUS_FLOW = {
  open:         { next: 'acknowledged',  label: 'Acknowledge', cls: 'btn-primary' },
  acknowledged: { next: 'in_progress',   label: 'Start Work',  cls: 'btn-primary' },
  in_progress:  { next: 'resolved',      label: 'Resolve',     cls: 'btn-success' },
  resolved:     { next: null,            label: 'Resolved ✓',  cls: 'btn-ghost' },
}

const PRIORITY_COLORS = { high: '#ef4444', medium: '#fbbf24', low: '#4ade80' }

export default function TasksTab() {
  const qc = useQueryClient()
  const [newTask, setNewTask] = useState({ title: '', location: '', priority: 'medium', assigned_to: '' })
  const [showForm, setShowForm] = useState(false)

  const { data: tasksData } = useQuery({
    queryKey: ['tasks'],
    queryFn: fetchTasks,
    refetchInterval: 10_000,
  })

  const { data: metrics } = useQuery({
    queryKey: ['task-metrics'],
    queryFn: fetchTaskMetrics,
    refetchInterval: 15_000,
  })

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => { qc.invalidateQueries(['tasks']); qc.invalidateQueries(['task-metrics']); setNewTask({ title: '', location: '', priority: 'medium', assigned_to: '' }); setShowForm(false) },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, status }) => updateTask(id, { status }),
    onSuccess: () => { qc.invalidateQueries(['tasks']); qc.invalidateQueries(['task-metrics']) },
  })

  const tasks = tasksData?.tasks || []
  const grouped = {
    open:         tasks.filter(t => t.status === 'open'),
    acknowledged: tasks.filter(t => t.status === 'acknowledged'),
    in_progress:  tasks.filter(t => t.status === 'in_progress'),
    resolved:     tasks.filter(t => t.status === 'resolved'),
  }

  return (
    <div>
      {/* Metrics */}
      <div className="metric-grid">
        <div className="metric-tile">
          <div className="metric-val">
            {metrics?.median_ack_min != null ? `${metrics.median_ack_min}m` : '—'}
          </div>
          <div className="metric-label">Median Time to Ack</div>
        </div>
        <div className="metric-tile">
          <div className="metric-val">
            {metrics?.median_resolve_min != null ? `${metrics.median_resolve_min}m` : '—'}
          </div>
          <div className="metric-label">Median Time to Resolve</div>
        </div>
        <div className="metric-tile">
          <div className="metric-val" style={{ fontSize: '1.1rem' }}>{tasks.filter(t => t.status !== 'resolved').length}</div>
          <div className="metric-label">Open Tasks</div>
        </div>
        <div className="metric-tile">
          <div className="metric-val" style={{ fontSize: '1.1rem', color: '#4ade80' }}>{grouped.resolved.length}</div>
          <div className="metric-label">Resolved</div>
        </div>
      </div>
      {metrics?.note && (
        <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textAlign: 'center', marginBottom: 12 }}>
          {metrics.note}
        </div>
      )}

      {/* New task form */}
      <button id="new-task-btn" className="btn btn-primary btn-sm" style={{ width: '100%', marginBottom: 12 }} onClick={() => setShowForm(!showForm)}>
        {showForm ? 'Cancel' : '+ New Task'}
      </button>
      {showForm && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="card-title">Create Task</div>
          <div className="report-form">
            <div className="form-group">
              <label className="form-label">Title</label>
              <input className="form-control" value={newTask.title} onChange={e => setNewTask(n => ({ ...n, title: e.target.value }))} placeholder="e.g. Inspect drain on Main Road" />
            </div>
            <div className="form-group">
              <label className="form-label">Location</label>
              <input className="form-control" value={newTask.location} onChange={e => setNewTask(n => ({ ...n, location: e.target.value }))} placeholder="e.g. Kotturpuram Main Road" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div className="form-group">
                <label className="form-label">Priority</label>
                <select className="form-control form-select" value={newTask.priority} onChange={e => setNewTask(n => ({ ...n, priority: e.target.value }))}>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Assigned To</label>
                <input className="form-control" value={newTask.assigned_to} onChange={e => setNewTask(n => ({ ...n, assigned_to: e.target.value }))} placeholder="Team / name" />
              </div>
            </div>
            <button id="create-task-submit" className="btn btn-primary" onClick={() => createMutation.mutate(newTask)} disabled={!newTask.title || createMutation.isPending}>
              {createMutation.isPending ? 'Creating…' : 'Create Task'}
            </button>
          </div>
        </div>
      )}

      {/* Task board */}
      {['open', 'acknowledged', 'in_progress', 'resolved'].map(statusKey => (
        <div key={statusKey}>
          {grouped[statusKey].length > 0 && (
            <div>
              <div className="card-title" style={{ marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {statusKey.replace('_', ' ')} ({grouped[statusKey].length})
              </div>
              {grouped[statusKey].map(task => {
                const flow = STATUS_FLOW[task.status]
                return (
                  <div key={task.id} className="task-item">
                    <div>
                      <div className="task-title">
                        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: PRIORITY_COLORS[task.priority] || '#fff', marginRight: 6 }} />
                        {task.title}
                      </div>
                      <div className="task-meta">
                        {task.location && <span>{task.location} · </span>}
                        {task.assigned_to && <span>👤 {task.assigned_to} · </span>}
                        <span>{task.created_at?.slice(11, 19)}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
                      <span className={`task-status ts-${task.status}`}>{task.status.replace('_', ' ')}</span>
                      {flow?.next && (
                        <button
                          className={`btn btn-sm ${flow.cls}`}
                          style={{ fontSize: '0.6rem', padding: '3px 8px' }}
                          onClick={() => updateMutation.mutate({ id: task.id, status: flow.next })}
                        >
                          {flow.label}
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ))}

      {tasks.length === 0 && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', padding: 20 }}>
          No tasks yet. Create one above or click "Create Task" from an alert.
        </div>
      )}
    </div>
  )
}
