import { useState, useEffect, useRef } from 'react'
import { useVoiceInput } from '../hooks/useVoiceInput'

export default function VoiceInput({ onResult, compact = false }) {
  const { isListening, transcript, isSupported, startListening, stopListening, clearTranscript } = useVoiceInput()
  const [text, setText] = useState('')
  const [status, setStatus] = useState('')
  const [animActive, setAnimActive] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (transcript) {
      setText(transcript)
    }
  }, [transcript])

  const handleSubmit = async () => {
    const msg = text.trim()
    if (!msg) return

    setStatus('处理中...')
    try {
      const res = await onResult(msg)
      if (res?.reply) {
        setStatus(res.reply)
      }
      setText('')
      clearTranscript()
    } catch (err) {
      setStatus('出错了，请重试')
    } finally {
      setTimeout(() => setStatus(''), 5000)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const toggleListening = () => {
    if (isListening) {
      stopListening()
      setAnimActive(false)
      if (text.trim()) handleSubmit()
    } else {
      startListening()
      setAnimActive(true)
    }
  }

  if (compact) {
    return (
      <div className="voice-input-wrapper">
        <div className="voice-input compact">
          <button
            className={`mic-btn compact ${isListening ? 'listening' : ''}`}
            onClick={toggleListening}
            disabled={!isSupported}
            title={isSupported ? '语音输入' : '浏览器不支持语音识别'}
          >
            {isListening ? '⏹' : '🎤'}
          </button>
          <input
            ref={inputRef}
            className="quick-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入或点击麦克风..."
          />
        </div>
        {status && <div className="voice-status-bar">{status}</div>}
      </div>
    )
  }

  return (
    <div className="voice-input full">
      <div className="voice-area">
        <div className={`voice-wave ${animActive ? 'active' : ''}`}>
          {[...Array(5)].map((_, i) => (
            <div key={i} className="wave-bar" style={{ animationDelay: `${i * 0.1}s` }} />
          ))}
        </div>
        <button
          className={`mic-btn large ${isListening ? 'listening' : ''}`}
          onClick={toggleListening}
          disabled={!isSupported}
        >
          {isListening ? '⏹ 停止' : '🎤 开始说话'}
        </button>
        {!isSupported && (
          <p className="voice-warning">您的浏览器不支持语音识别，请使用 Chrome 浏览器</p>
        )}
        {isListening && <p className="voice-hint">正在聆听...</p>}
      </div>

      <div className="voice-input-box">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入文字或点击麦克风说话..."
          rows={3}
        />
        <button className="btn-primary send-btn" onClick={handleSubmit} disabled={!text.trim()}>
          发送
        </button>
      </div>

      {transcript && isListening && (
        <div className="transcript-live">{transcript}</div>
      )}

      {status && <div className="voice-status">{status}</div>}
    </div>
  )
}
