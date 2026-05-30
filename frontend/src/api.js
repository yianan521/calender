// In dev mode (npm run dev), Vite proxies /api → localhost:8000
// In production, fall back to direct connection
const BASE = window.location.hostname === 'localhost' ? '/api' : 'http://localhost:8000'

async function request(path, options = {}) {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const msg = typeof data?.detail === 'string' ? data.detail : JSON.stringify(data?.detail || res.statusText)
    throw new Error(msg)
  }
  return data
}

export const api = {
  // Events
  listEvents: (params) => {
    const clean = {}
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== '') clean[k] = v
    }
    const qs = new URLSearchParams(clean).toString()
    return request(`/events/${qs ? '?' + qs : ''}`)
  },
  getEvent: (id) => request(`/events/${id}`),
  createEvent: (data) => request('/events/', { method: 'POST', body: JSON.stringify(data) }),
  updateEvent: (id, data) => request(`/events/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteEvent: (id) => request(`/events/${id}`, { method: 'DELETE' }),

  // Dialogue
  sendMessage: (text, sessionId) =>
    request('/dialogue/', { method: 'POST', body: JSON.stringify({ text, session_id: sessionId }) }),
  getSessions: () => request('/dialogue/sessions'),
  getMessages: (sessionId) => request(`/dialogue/sessions/${sessionId}/messages`),

  // Schedule
  autoSchedule: (tasks) => request('/schedule/auto', { method: 'POST', body: JSON.stringify({ tasks }) }),
  checkConflicts: (start, end) => {
    const qs = new URLSearchParams({ start, end }).toString()
    return request(`/schedule/conflicts?${qs}`)
  },
  getFreeSlots: (day) => request(`/schedule/free-slots${day ? '?day=' + day : ''}`),
  getDailyBrief: (date) => request(`/schedule/daily-brief${date ? '?date=' + date : ''}`),

  // Tasks
  listTasks: () => request('/tasks/'),
  createTask: (data) => request('/tasks/', { method: 'POST', body: JSON.stringify(data) }),
  updateTask: (id, data) => request(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),

  // Reminders
  listReminders: (status) => request(`/reminders/${status ? '?status=' + status : ''}`),
  createReminder: (data) => request('/reminders/', { method: 'POST', body: JSON.stringify(data) }),
  updateReminder: (id, data) => request(`/reminders/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteReminder: (id) => request(`/reminders/${id}`, { method: 'DELETE' }),
  triggerReminder: (id) => request(`/reminders/${id}/trigger`, { method: 'POST' }),
  dismissReminder: (id) => request(`/reminders/${id}/dismiss`, { method: 'POST' }),
  get5HourEvents: () => request('/reminders/events/5hours'),
  checkCommute: (data) => request('/reminders/commute', { method: 'POST', body: JSON.stringify(data) }),
  createCommuteReminder: (data) => request('/reminders/commute/create', { method: 'POST', body: JSON.stringify(data) }),
  pollPendingReminders: (windowMinutes) =>
    request(`/reminders/poll/pending${windowMinutes ? '?window_minutes=' + windowMinutes : ''}`),
}
