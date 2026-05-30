export default function Dashboard({ brief, events }) {
  const busyness = brief?.busyness_index ?? 0

  const getLevel = (val) => {
    if (val < 30) return { label: '轻松', color: '#4CAF50', emoji: '😊' }
    if (val < 60) return { label: '适中', color: '#FF9800', emoji: '🙂' }
    if (val < 85) return { label: '忙碌', color: '#F44336', emoji: '😰' }
    return { label: '超负荷', color: '#B71C1C', emoji: '🔥' }
  }

  const level = getLevel(busyness)

  const upcomingEvents = events
    .filter(e => new Date(e.start_time) > new Date())
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
    .slice(0, 5)

  return (
    <div className="dashboard">
      <div className="dash-cards">
        <div className="dash-card busyness-card">
          <h3>忙碌指数 {level.emoji}</h3>
          <div className="busyness-gauge">
            <svg viewBox="0 0 120 120" className="gauge-svg">
              <circle cx="60" cy="60" r="50" fill="none" stroke="#e0e0e0" strokeWidth="10" />
              <circle
                cx="60" cy="60" r="50"
                fill="none"
                stroke={level.color}
                strokeWidth="10"
                strokeDasharray={`${busyness * 3.14} 314`}
                strokeLinecap="round"
                transform="rotate(-90 60 60)"
              />
              <text x="60" y="55" textAnchor="middle" className="gauge-value">{busyness}%</text>
              <text x="60" y="72" textAnchor="middle" className="gauge-label">{level.label}</text>
            </svg>
          </div>
        </div>

        <div className="dash-card stats-card">
          <h3>今日统计</h3>
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-num">{events.length}</span>
              <span className="stat-label">今日日程</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">{brief?.free_slots?.length ?? 0}</span>
              <span className="stat-label">空闲时段</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">
                {events.reduce((sum, e) => {
                  const dur = (new Date(e.end_time) - new Date(e.start_time)) / (1000 * 60 * 60)
                  return sum + dur
                }, 0).toFixed(1)}h
              </span>
              <span className="stat-label">总时长</span>
            </div>
          </div>
        </div>

        <div className="dash-card summary-card">
          <h3>AI 摘要</h3>
          <p className="summary-text">{brief?.summary || '加载中...'}</p>
        </div>
      </div>

      {brief?.free_slots?.length > 0 && (
        <div className="dash-card free-slots-card">
          <h3>空闲时段</h3>
          <ul className="free-slots-list">
            {brief.free_slots.map((slot, i) => (
              <li key={i} className="free-slot-item">
                <span className="slot-time">
                  {new Date(slot.start).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                  {' — '}
                  {new Date(slot.end).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className="slot-duration">
                  {Math.round((new Date(slot.end) - new Date(slot.start)) / (1000 * 60))} 分钟
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {upcomingEvents.length > 0 && (
        <div className="dash-card upcoming-card">
          <h3>即将开始</h3>
          <ul className="upcoming-list">
            {upcomingEvents.map((event) => (
              <li key={event.id} className="upcoming-item">
                <div className="upcoming-time">
                  {new Date(event.start_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </div>
                <div className="upcoming-info">
                  <div className="upcoming-title">{event.title}</div>
                  {event.location && <div className="upcoming-location">📍 {event.location}</div>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
