import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ── Ward support ─────────────────────────────────────────────────────────────
export const fetchWards = () => api.get('/config/wards').then(r => r.data)
export const fetchWard  = (wardId) => api.get(`/config/ward/${wardId}`).then(r => r.data)

// ── Risk / sensors / reports / dashboard all accept optional ward_id ──────
export const fetchRisk = (horizon, wardId) =>
  api.get(`/risk?horizon=${horizon}${wardId ? `&ward_id=${wardId}` : ''}`).then(r => r.data)

export const fetchSensors = (wardId) =>
  api.get(`/sensors${wardId ? `?ward_id=${wardId}` : ''}`).then(r => r.data)

export const fetchReports = (wardId) =>
  api.get(`/reports${wardId ? `?ward_id=${wardId}` : ''}`).then(r => r.data)

export const fetchDashboard = (horizon, wardId) =>
  api.get(`/dashboard/summary?horizon=${horizon}${wardId ? `&ward_id=${wardId}` : ''}`).then(r => r.data)

// ── CCTV ─────────────────────────────────────────────────────────────────────
export const fetchCctvStatus = () => api.get('/cctv/status').then(r => r.data)

// ── Unchanged ─────────────────────────────────────────────────────────────────
export const fetchAlerts = () => api.get('/alerts').then(r => r.data)
export const fetchTasks = () => api.get('/tasks').then(r => r.data)
export const fetchTaskMetrics = () => api.get('/tasks/metrics').then(r => r.data)
export const fetchMode = () => api.get('/config/mode').then(r => r.data)

export const generateAlert = (payload) => api.post('/alerts/generate', payload).then(r => r.data)
export const createTask = (payload) => api.post('/tasks', payload).then(r => r.data)
export const updateTask = (id, payload) => api.patch(`/tasks/${id}`, payload).then(r => r.data)

export const submitReport = (formData) =>
  api.post('/reports', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)

export default api
