import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const fetchRisk = (horizon) => api.get(`/risk?horizon=${horizon}`).then(r => r.data)
export const fetchSensors = () => api.get('/sensors').then(r => r.data)
export const fetchReports = () => api.get('/reports').then(r => r.data)
export const fetchAlerts = () => api.get('/alerts').then(r => r.data)
export const fetchTasks = () => api.get('/tasks').then(r => r.data)
export const fetchTaskMetrics = () => api.get('/tasks/metrics').then(r => r.data)
export const fetchDashboard = (horizon) => api.get(`/dashboard/summary?horizon=${horizon}`).then(r => r.data)
export const fetchMode = () => api.get('/config/mode').then(r => r.data)
export const fetchWard = () => api.get('/config/ward').then(r => r.data)

export const generateAlert = (payload) => api.post('/alerts/generate', payload).then(r => r.data)
export const createTask = (payload) => api.post('/tasks', payload).then(r => r.data)
export const updateTask = (id, payload) => api.patch(`/tasks/${id}`, payload).then(r => r.data)

export const submitReport = (formData) =>
  api.post('/reports', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)

export default api
