import { useState, useEffect, useCallback } from 'react'
import { api } from './api'
import { useTTS } from './hooks/useTTS'
import Timeline from './components/Timeline'
import VoiceInput from './components/VoiceInput'
import DialoguePanel from './components/DialoguePanel'
import Dashboard from './components/Dashboard'
import EventForm from './components/EventForm'
import ReminderPanel from './components/ReminderPanel'

export default function App() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [view, setView] = useState('timeline')
  const [sessionId, setSessionId] = useState(null)
  const [brief, setBrief] = useState(null)
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10))
  // EventForm mode: { mode: 'create' | 'edit', event?: existingEvent }
  const [eventForm, setEventForm] = useState(null)
  const [dialogueRefresh, setDialogueRefresh] = useState(0)
  const { speak, isSupported: ttsSupported } = useTTS()

  const loadEvents = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await api.listEvents({
        start: selectedDate + 'T00:00:00',
        end: selectedDate + 'T23:59:59',
      })
      setEvents(data || [])
    } catch (err) {
      console.error('Failed to load events:', err)
      setLoadError('无法加载日程，请确认后端服务已启动（端口 8000）')
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [selectedDate])

  const loadBrief = useCallback(async () => {
    try {
      const data = await api.getDailyBrief(selectedDate)
      setBrief(data)
    } catch (err) {
      console.error('Failed to load brief:', err)
    }
  }, [selectedDate])

  useEffect(() => {
    loadEvents()
    loadBrief()
  }, [loadEvents, loadBrief])

  const handleVoiceResult = async (text) => {
    if (!text.trim()) return
    try {
      const res = await api.sendMessage(text, sessionId)
      setSessionId(res.session_id)
      // Auto-speak the assistant reply
      if (res.reply) {
        speak(res.reply)
      }
      // Trigger dialogue panel to reload messages
      setDialogueRefresh((k) => k + 1)
      // Always refresh after dialogue — events/tasks may have changed
      await loadEvents()
      await loadBrief()
      return res
    } catch (err) {
      console.error('Dialogue error:', err)
    }
  }

  // Reload events when user switches to timeline view
  useEffect(() => {
    if (view === 'timeline') {
      loadEvents()
      loadBrief()
    }
  }, [view])

  const handleFormSuccess = () => {
    loadEvents()
    loadBrief()
    setEventForm(null)
  }

  const openCreateForm = () => {
    setEventForm({ mode: 'create' })
  }

  const openEditForm = (event) => {
    setEventForm({ mode: 'edit', event })
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">AI Voice Scheduler</h1>
        <span className="app-subtitle">智能语音日程管家</span>
        <nav className="app-nav">
          <button className={`nav-btn ${view === 'timeline' ? 'active' : ''}`} onClick={() => setView('timeline')}>
            时间轴
          </button>
          <button className={`nav-btn ${view === 'dialogue' ? 'active' : ''}`} onClick={() => setView('dialogue')}>
            语音对话
          </button>
          <button className={`nav-btn ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setView('dashboard')}>
            仪表盘
          </button>
        </nav>
        <input
          type="date"
          className="date-picker"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
        />
      </header>

      <main className="app-main">
        {view === 'timeline' && (
          <div className="timeline-view">
            <div className="view-header">
              <h2>日程时间轴</h2>
              <button className="btn-primary" onClick={openCreateForm}>
                + 新建日程
              </button>
            </div>
            <div className="timeline-layout">
              <div className="timeline-main">
                <Timeline
                  events={events}
                  loading={loading}
                  loadError={loadError}
                  date={selectedDate}
                  onRefresh={loadEvents}
                  onEditEvent={openEditForm}
                />
              </div>
              <ReminderPanel onRefreshEvents={loadEvents} />
            </div>
            {eventForm && (
              <EventForm
                mode={eventForm.mode}
                event={eventForm.event}
                date={selectedDate}
                onClose={() => setEventForm(null)}
                onSuccess={handleFormSuccess}
              />
            )}
          </div>
        )}

        {view === 'dialogue' && (
          <div className="dialogue-view">
            <h2>语音对话</h2>
            <VoiceInput onResult={handleVoiceResult} />
            <DialoguePanel sessionId={sessionId} refreshKey={dialogueRefresh} />
          </div>
        )}

        {view === 'dashboard' && (
          <div className="dashboard-view">
            <div className="view-header">
              <h2>日程仪表盘</h2>
              {ttsSupported && brief && (
                <button
                  className="btn-primary"
                  onClick={() => {
                    const lines = []
                    lines.push(`今日忙碌指数${brief.busyness_index}%。`)
                    lines.push(brief.summary)
                    if (brief.free_slots?.length) {
                      const slots = brief.free_slots.map(s => {
                        const start = new Date(s.start).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                        const end = new Date(s.end).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                        return `${start}到${end}`
                      }).join('，')
                      lines.push(`空闲时段：${slots}。`)
                    }
                    if (brief.events_today?.length) {
                      const evs = brief.events_today.map(e => {
                        const t = new Date(e.start_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                        return `${t}${e.title}`
                      }).join('，')
                      lines.push(`今日日程：${evs}。`)
                    }
                    speak(lines.join(' '))
                  }}
                >
                  播报早报
                </button>
              )}
            </div>
            <Dashboard brief={brief} events={events} />
          </div>
        )}
      </main>

      <footer className="app-footer">
        <div className="quick-voice">
          <VoiceInput onResult={handleVoiceResult} compact />
        </div>
      </footer>
    </div>
  )
}
