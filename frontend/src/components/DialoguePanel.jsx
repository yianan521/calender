import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

export default function DialoguePanel({ sessionId, refreshKey = 0 }) {
  const [messages, setMessages] = useState([])
  const bottomRef = useRef(null)

  useEffect(() => {
    if (!sessionId) return
    const loadMessages = async () => {
      try {
        const data = await api.getMessages(sessionId)
        setMessages(data)
      } catch (err) {
        console.error('Failed to load messages:', err)
      }
    }
    loadMessages()
  }, [sessionId, refreshKey])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (!sessionId) {
    return (
      <div className="dialogue-panel empty">
        <p>发送语音或文字开始对话，AI 助手将帮您管理日程。</p>
        <div className="example-prompts">
          <p className="example-title">试试这些：</p>
          <ul>
            <li>"帮我约明天下午三点的牙医"</li>
            <li>"这周五上午十点……不对，改成周四"</li>
            <li>"这周帮我安排健身两次和写周报"</li>
            <li>"今天有什么日程？"</li>
          </ul>
        </div>
      </div>
    )
  }

  return (
    <div className="dialogue-panel">
      <div className="dialogue-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`msg ${msg.role}`}>
            <div className="msg-avatar">{msg.role === 'user' ? '🎤' : '📅'}</div>
            <div className="msg-content">
              <p>{msg.content}</p>
              {msg.intent_json && msg.role === 'assistant' && (
                <div className="msg-intent">
                  <small>意图: {typeof msg.intent_json === 'string' ? msg.intent_json : msg.intent_json.intent}</small>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
