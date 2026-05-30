import { useState, useEffect } from 'react'
import { api } from '../api'

function toLocalDatetime(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function EventForm({ mode, event, date, onClose, onSuccess }) {
  const isEdit = mode === 'edit' && event

  const [form, setForm] = useState({
    title: isEdit ? event.title : '',
    description: isEdit ? event.description : '',
    location: isEdit ? event.location : '',
    start_time: isEdit ? toLocalDatetime(event.start_time) : date + 'T09:00',
    end_time: isEdit ? toLocalDatetime(event.end_time) : date + 'T10:00',
    all_day: isEdit ? event.all_day : false,
    priority: isEdit ? event.priority : 0,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setForm(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      // datetime-local input is already local ISO like "2026-05-29T21:00"
      // append seconds so backend can parse it as naive local datetime
      const payload = {
        ...form,
        start_time: form.start_time + ':00',
        end_time: form.end_time + ':00',
      }
      if (isEdit) {
        const patch = {}
        for (const [k, v] of Object.entries(payload)) {
          patch[k] = v
        }
        await api.updateEvent(event.id, patch)
      } else {
        await api.createEvent(payload)
      }
      onSuccess()
    } catch (err) {
      const msg = err.message || ''
      if (msg.includes('conflict')) {
        setError('该时段与其他日程冲突，请选择其他时间。')
      } else {
        setError(msg || (isEdit ? '更新失败' : '创建失败'))
      }
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!isEdit) return
    if (!confirm('确定要删除「' + event.title + '」吗？')) return
    try {
      await api.deleteEvent(event.id)
      onSuccess()
    } catch (err) {
      setError(err.message || '删除失败')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? '编辑日程' : '新建日程'}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>标题</label>
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              placeholder="日程标题"
              required
              autoFocus
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>开始时间</label>
              <input
                type="datetime-local"
                name="start_time"
                value={form.start_time}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label>结束时间</label>
              <input
                type="datetime-local"
                name="end_time"
                value={form.end_time}
                onChange={handleChange}
                required
              />
            </div>
          </div>
          <div className="form-group">
            <label>地点</label>
            <input
              name="location"
              value={form.location}
              onChange={handleChange}
              placeholder="可选"
            />
          </div>
          <div className="form-group">
            <label>备注</label>
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              placeholder="可选"
              rows={2}
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>优先级</label>
              <select name="priority" value={form.priority} onChange={handleChange}>
                <option value={0}>普通</option>
                <option value={1}>重要</option>
                <option value={2}>紧急</option>
              </select>
            </div>
            <div className="form-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="all_day"
                  checked={form.all_day}
                  onChange={handleChange}
                />
                全天事件
              </label>
            </div>
          </div>
          {error && <div className="form-error">{error}</div>}
          <div className="form-actions">
            {isEdit && (
              <button type="button" className="btn-danger" onClick={handleDelete}>
                删除
              </button>
            )}
            <div className="form-actions-right">
              <button type="button" className="btn-secondary" onClick={onClose}>取消</button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? '保存中...' : (isEdit ? '保存' : '创建')}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
