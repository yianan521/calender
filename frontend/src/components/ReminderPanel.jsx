import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'

function useCountdown(targetTime) {
  const [remaining, setRemaining] = useState(null)

  useEffect(() => {
    const calc = () => {
      const diff = new Date(targetTime) - new Date()
      if (diff <= 0) {
        setRemaining({ hours: 0, minutes: 0, seconds: 0, total: 0, expired: true })
        return
      }
      const total = Math.floor(diff / 1000)
      const hours = Math.floor(total / 3600)
      const minutes = Math.floor((total % 3600) / 60)
      const seconds = total % 60
      setRemaining({ hours, minutes, seconds, total, expired: false })
    }
    calc()
    const timer = setInterval(calc, 1000)
    return () => clearInterval(timer)
  }, [targetTime])

  return remaining
}

export default function ReminderPanel({ onRefreshEvents }) {
  const [data, setData] = useState({ events: [], reminders: [] })
  const [loading, setLoading] = useState(true)
  const [dismissed, setDismissed] = useState(new Set())

  const fetchData = useCallback(async () => {
    try {
      const result = await api.get5HourEvents()
      setData(result)
    } catch (err) {
      console.error('Failed to load upcoming events:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const timer = setInterval(fetchData, 30000) // poll every 30s
    return () => clearInterval(timer)
  }, [fetchData])

  const handleDismiss = async (reminderId) => {
    try {
      await api.dismissReminder(reminderId)
      setDismissed(prev => new Set([...prev, reminderId]))
      onRefreshEvents()
    } catch (err) {
      console.error('Failed to dismiss reminder:', err)
    }
  }

  const activeReminders = data.reminders.filter(r => !dismissed.has(r.id))

  if (loading) return null

  if (data.events.length === 0 && activeReminders.length === 0) {
    return (
      <div className="reminder-panel empty">
        <div className="reminder-panel-header">
          <h3>即将提醒</h3>
          <span className="reminder-badge">5h</span>
        </div>
        <p className="reminder-empty-text">未来5小时内暂无日程安排</p>
      </div>
    )
  }

  return (
    <div className="reminder-panel">
      <div className="reminder-panel-header">
        <h3>即将提醒</h3>
        <span className="reminder-badge">{data.events.length}个日程</span>
      </div>

      {/* Active reminders first */}
      {activeReminders.length > 0 && (
        <div className="reminder-section">
          <div className="reminder-section-title">⏰ 提醒</div>
          {activeReminders.map(r => (
            <ReminderItem
              key={r.id}
              reminder={r}
              onDismiss={() => handleDismiss(r.id)}
            />
          ))}
        </div>
      )}

      {/* Upcoming events with countdown */}
      {data.events.length > 0 && (
        <div className="reminder-section">
          <div className="reminder-section-title">📋 即将开始</div>
          {data.events.map(event => (
            <UpcomingEventItem key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  )
}

function ReminderItem({ reminder, onDismiss }) {
  const countdown = useCountdown(reminder.remind_at)

  return (
    <div className={`reminder-item ${reminder.remind_type === 'commute' ? 'commute' : ''} ${countdown?.expired ? 'expired' : ''}`}>
      <div className="reminder-item-icon">
        {reminder.remind_type === 'commute' ? '🚗' : '🔔'}
      </div>
      <div className="reminder-item-info">
        <div className="reminder-item-title">{reminder.title}</div>
        <div className="reminder-item-message">{reminder.message}</div>
        {countdown && !countdown.expired && (
          <div className="reminder-countdown">
            还剩 {countdown.hours > 0 ? `${countdown.hours}时` : ''}{countdown.minutes}分{countdown.seconds}秒
          </div>
        )}
        {countdown?.expired && (
          <div className="reminder-countdown overdue">已过期</div>
        )}
      </div>
      <button className="reminder-dismiss" onClick={onDismiss} title="忽略">
        ✕
      </button>
    </div>
  )
}

function UpcomingEventItem({ event }) {
  const countdown = useCountdown(event.start_time)
  const startDate = new Date(event.start_time)

  // Determine urgency class
  let urgency = 'normal'
  if (countdown && countdown.total < 1800) urgency = 'soon'      // < 30 min
  else if (countdown && countdown.total < 7200) urgency = 'close' // < 2 hours

  // Format start time
  const timeStr = startDate.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className={`upcoming-event-item ${urgency}`}>
      <div className="upcoming-event-time">{timeStr}</div>
      <div className="upcoming-event-info">
        <div className="upcoming-event-title">{event.title}</div>
        {event.location && (
          <div className="upcoming-event-location">📍 {event.location}</div>
        )}
        {countdown && !countdown.expired && (
          <div className={`event-countdown ${urgency}`}>
            {countdown.hours > 0 && `${countdown.hours}时`}
            {countdown.minutes}分钟后开始
          </div>
        )}
        {countdown?.expired && (
          <div className="event-countdown overdue">已开始</div>
        )}
      </div>
      <div className={`upcoming-event-indicator ${urgency}`} />
    </div>
  )
}
