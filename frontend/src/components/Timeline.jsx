import { useState, useRef, useCallback } from 'react'
import { api } from '../api'

const HOUR_HEIGHT = 64
const START_HOUR = 6
const END_HOUR = 23
const TOTAL_HOURS = END_HOUR - START_HOUR

function formatHour(h) {
  return `${String(h).padStart(2, '0')}:00`
}

export default function Timeline({ events, loading, loadError, date, onRefresh, onEditEvent }) {
  const [dragging, setDragging] = useState(null)
  const [dragOver, setDragOver] = useState(null)
  const [saveMsg, setSaveMsg] = useState('')
  const [wasDragged, setWasDragged] = useState(false)
  const timelineRef = useRef(null)

  const getPosition = useCallback((timeStr) => {
    const d = new Date(timeStr)
    const hours = d.getHours() + d.getMinutes() / 60
    return (hours - START_HOUR) * HOUR_HEIGHT
  }, [])

  const getDuration = useCallback((startStr, endStr) => {
    const start = new Date(startStr)
    const end = new Date(endStr)
    const hours = (end - start) / (1000 * 60 * 60)
    return Math.max(hours * HOUR_HEIGHT, 24)
  }, [])

  const handleDragStart = (e, event) => {
    e.dataTransfer.setData('text/plain', event.id)
    setDragging(event.id)
  }

  const handleDragEnd = () => {
    setDragging(null)
    setDragOver(null)
    setTimeout(() => setWasDragged(false), 100)
  }

  const handleTimelineDrop = async (e) => {
    e.preventDefault()
    setDragOver(null)
    const eventId = e.dataTransfer.getData('text/plain')
    if (!eventId || !timelineRef.current) return

    const rect = timelineRef.current.getBoundingClientRect()
    const y = e.clientY - rect.top + timelineRef.current.scrollTop
    const hours = y / HOUR_HEIGHT + START_HOUR
    const hour = Math.floor(hours)
    const minute = Math.round((hours - hour) * 60 / 15) * 15

    const event = events.find(ev => ev.id === eventId)
    if (!event) return

    const oldDuration = (new Date(event.end_time) - new Date(event.start_time)) / (1000 * 60 * 60)
    const newStart = new Date(date + 'T00:00:00')
    newStart.setHours(hour, minute, 0, 0)
    const newEnd = new Date(newStart.getTime() + oldDuration * 3600 * 1000)

    try {
      await api.updateEvent(eventId, {
        start_time: newStart.toISOString(),
        end_time: newEnd.toISOString(),
      })
      setSaveMsg('已更新')
      setTimeout(() => setSaveMsg(''), 2000)
      onRefresh()
    } catch (err) {
      console.error('Failed to move event:', err)
    }
    setWasDragged(true)
  }

  const handleTimelineDragOver = (e) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleEventClick = (e, event) => {
    if (wasDragged) return
    e.stopPropagation()
    onEditEvent(event)
  }

  const handleDelete = async (e, eventId) => {
    e.stopPropagation()
    if (!confirm('确定要删除这个日程吗？')) return
    try {
      await api.deleteEvent(eventId)
      setSaveMsg('已删除')
      setTimeout(() => setSaveMsg(''), 2000)
      onRefresh()
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  const hourMarkers = []
  for (let h = START_HOUR; h <= END_HOUR; h++) {
    hourMarkers.push(
      <div key={h} className="timeline-hour" style={{ top: (h - START_HOUR) * HOUR_HEIGHT }}>
        <span className="hour-label">{formatHour(h)}</span>
        <div className="hour-line" />
      </div>
    )
  }

  const now = new Date()
  const nowLine = (now.getHours() + now.getMinutes() / 60 - START_HOUR) * HOUR_HEIGHT
  const isToday = date === now.toISOString().slice(0, 10)

  return (
    <>
      {saveMsg && <div className="toast">{saveMsg}</div>}
      <div
        className={`timeline ${dragOver ? 'drag-over' : ''}`}
        ref={timelineRef}
        onDrop={handleTimelineDrop}
        onDragOver={handleTimelineDragOver}
      >
        {loading && (
          <div className="timeline-overlay"><span className="spinner" /></div>
        )}
        {loadError && !loading && (
          <div className="timeline-overlay">
            <div className="error-msg">{loadError}</div>
            <button className="btn-primary" onClick={onRefresh}>重试</button>
          </div>
        )}
        <div className="timeline-scroll" style={{ height: TOTAL_HOURS * HOUR_HEIGHT }}>
          {hourMarkers}
          {isToday && (
            <div className="timeline-now" style={{ top: nowLine }}>
              <div className="now-dot" />
              <div className="now-line" />
            </div>
          )}
          {events.map((event) => {
            const top = getPosition(event.start_time)
            const height = getDuration(event.start_time, event.end_time)
            const priorityColors = ['#4A90D9', '#E8A838', '#E05050']
            const color = priorityColors[event.priority] || priorityColors[0]

            return (
              <div
                key={event.id}
                className={`timeline-event ${dragging === event.id ? 'dragging' : ''} ${event.status === 'cancelled' ? 'cancelled' : ''}`}
                style={{ top, height, borderLeftColor: color }}
                draggable
                onDragStart={(e) => handleDragStart(e, event)}
                onDragEnd={handleDragEnd}
                onClick={(e) => handleEventClick(e, event)}
                title="点击编辑，拖拽移动"
              >
                <div className="event-time">
                  {new Date(event.start_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                  {' — '}
                  {new Date(event.end_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </div>
                <div className="event-title">{event.title}</div>
                {event.location && <div className="event-location">📍 {event.location}</div>}
                <button className="event-delete" onClick={(e) => handleDelete(e, event.id)}>×</button>
              </div>
            )
          })}
          {events.length === 0 && !loading && !loadError && (
            <div className="timeline-empty">暂无日程，点击"+ 新建日程"或使用语音添加</div>
          )}
        </div>
      </div>
    </>
  )
}
