'use client'

import { useState } from 'react'
import { Check, Loader2, Pencil, Sparkles, Trash2, X } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export type SuggestedTask = {
  id: string
  title: string
  cognitive_load_score: number
}

const LOAD_META: Record<number, { label: string; color: string; bg: string }> = {}
for (let i = 1; i <= 10; i++) {
  if (i <= 3)       LOAD_META[i] = { label: 'Light',    color: '#2d7a3a', bg: '#e6f4ea' }
  else if (i <= 6)  LOAD_META[i] = { label: 'Moderate', color: '#7a5c00', bg: '#fdf3d0' }
  else              LOAD_META[i] = { label: 'Deep Work', color: '#1f22f0', bg: '#e8e7ff' }
}

type Props = {
  userId: string
  tasks: SuggestedTask[]
  onChange: (tasks: SuggestedTask[]) => void
  onApproved: () => void
}

export default function SuggestedTasksPanel({ userId, tasks, onChange, onApproved }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editLoad, setEditLoad] = useState(5)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  if (tasks.length === 0) return null

  const startEdit = (task: SuggestedTask) => {
    setEditingId(task.id)
    setEditTitle(task.title)
    setEditLoad(task.cognitive_load_score)
  }

  const saveEdit = () => {
    if (!editingId || !editTitle.trim()) return
    onChange(tasks.map(t =>
      t.id === editingId
        ? { ...t, title: editTitle.trim(), cognitive_load_score: editLoad }
        : t
    ))
    setEditingId(null)
  }

  const remove = (id: string) => onChange(tasks.filter(t => t.id !== id))

  const approveAll = async () => {
    if (tasks.length === 0) return
    setSaving(true)
    setErr('')
    try {
      const res = await fetch(`${API}/tasks/copilot-suggestions/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          tasks: tasks.map(({ title, cognitive_load_score }) => ({ title, cognitive_load_score })),
        }),
      })
      if (!res.ok) throw new Error()
      onChange([])
      onApproved()
    } catch {
      setErr('Failed to add tasks. Is the backend running?')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-4 rounded-lg border border-[#e0d9f7] bg-[#faf7ff]">
      <div className="flex items-center justify-between border-b border-[#e0d9f7] px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-[#8127cf]" />
          <p className="text-xs font-semibold uppercase tracking-widest text-[#8127cf]">
            Co-Pilot suggestions
          </p>
          <span className="rounded-full bg-[#8127cf]/10 px-2 py-0.5 text-[10px] font-semibold text-[#8127cf]">
            {tasks.length}
          </span>
        </div>
        <button
          type="button"
          onClick={() => onChange([])}
          className="text-xs text-[#9092a8] hover:text-[#191c1e] hover:underline"
        >
          Dismiss all
        </button>
      </div>

      <div className="space-y-2 px-4 py-3">
        {tasks.map(task => {
          const meta = LOAD_META[task.cognitive_load_score] ?? LOAD_META[5]
          const isEditing = editingId === task.id

          return (
            <div
              key={task.id}
              className="rounded-lg border border-white bg-white px-3 py-2.5 shadow-sm"
            >
              {isEditing ? (
                <div className="space-y-2">
                  <input
                    autoFocus
                    value={editTitle}
                    onChange={e => setEditTitle(e.target.value)}
                    className="w-full rounded-md border border-[#d7d9e1] px-2.5 py-1.5 text-sm text-[#191c1e] outline-none focus:border-[#8127cf]"
                  />
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-[#6b7080]">Load</label>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={editLoad}
                      onChange={e => setEditLoad(Number(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-xs font-semibold text-[#8127cf]">{editLoad}/10</span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={saveEdit}
                      className="flex items-center gap-1 rounded-md bg-[#8127cf] px-2.5 py-1 text-xs font-semibold text-white hover:bg-[#6d1fb3]"
                    >
                      <Check className="h-3 w-3" /> Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="flex items-center gap-1 rounded-md border border-[#d7d9e1] px-2.5 py-1 text-xs text-[#6b7080] hover:bg-[#f5f5f8]"
                    >
                      <X className="h-3 w-3" /> Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <p className="flex-1 text-sm text-[#191c1e]">{task.title}</p>
                  <span
                    className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    style={{ backgroundColor: meta.bg, color: meta.color }}
                  >
                    {meta.label}
                  </span>
                  <button
                    type="button"
                    onClick={() => startEdit(task)}
                    title="Edit"
                    className="rounded p-1 text-[#9092a8] hover:bg-[#f0f1f5] hover:text-[#8127cf]"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(task.id)}
                    title="Delete"
                    className="rounded p-1 text-[#9092a8] hover:bg-red-50 hover:text-red-600"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {err && <p className="px-4 pb-2 text-xs text-red-600">{err}</p>}

      <div className="border-t border-[#e0d9f7] px-4 py-3">
        <button
          type="button"
          onClick={approveAll}
          disabled={saving || tasks.length === 0}
          className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-sm font-semibold text-white transition hover:bg-[#3f3dc6] disabled:opacity-60"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          {saving ? 'Adding…' : `Add ${tasks.length} task${tasks.length !== 1 ? 's' : ''} to my list`}
        </button>
      </div>
    </div>
  )
}
