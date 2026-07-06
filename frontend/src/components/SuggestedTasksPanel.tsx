'use client'

import { useState } from 'react'
import { Check, ChevronDown, ChevronUp, Loader2, Pencil, Sparkles, Target, Trash2, X } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export type SuggestedTask = {
  id: string
  title: string
  cognitive_load_score: number
  estimated_minutes?: number
}

export type SuggestedMilestone = {
  id: string
  title: string
  cognitive_load_score: number
  estimated_minutes?: number
  tasks: SuggestedTask[]
}

const LOAD_META: Record<number, { label: string; color: string; bg: string }> = {}
for (let i = 1; i <= 10; i++) {
  if (i <= 3)       LOAD_META[i] = { label: 'Light',    color: '#2d7a3a', bg: '#e6f4ea' }
  else if (i <= 6)  LOAD_META[i] = { label: 'Moderate', color: '#7a5c00', bg: '#fdf3d0' }
  else              LOAD_META[i] = { label: 'Deep Work', color: '#1f22f0', bg: '#e8e7ff' }
}

type Props = {
  userId: string
  milestones: SuggestedMilestone[]
  onChange: (milestones: SuggestedMilestone[]) => void
  onApproved: () => void
  aiFallback?: boolean
}

export default function SuggestedTasksPanel({ userId, milestones, onChange, onApproved, aiFallback }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editLoad, setEditLoad] = useState(5)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const taskCount = milestones.reduce((n, m) => n + m.tasks.length, 0)
  if (milestones.length === 0) return null

  const toggle = (id: string) => setExpanded(prev => ({ ...prev, [id]: !prev[id] }))

  const removeTask = (milestoneId: string, taskId: string) => {
    onChange(
      milestones
        .map(m => m.id === milestoneId ? { ...m, tasks: m.tasks.filter(t => t.id !== taskId) } : m)
        .filter(m => m.tasks.length > 0)
    )
  }

  const removeMilestone = (milestoneId: string) => {
    onChange(milestones.filter(m => m.id !== milestoneId))
  }

  const startEdit = (task: SuggestedTask) => {
    setEditingTaskId(task.id)
    setEditTitle(task.title)
    setEditLoad(task.cognitive_load_score)
  }

  const saveEdit = (milestoneId: string) => {
    if (!editingTaskId || !editTitle.trim()) return
    onChange(milestones.map(m =>
      m.id === milestoneId
        ? {
            ...m,
            tasks: m.tasks.map(t =>
              t.id === editingTaskId
                ? { ...t, title: editTitle.trim(), cognitive_load_score: editLoad }
                : t
            ),
          }
        : m
    ))
    setEditingTaskId(null)
  }

  const approveAll = async () => {
    if (taskCount === 0) return
    setSaving(true)
    setErr('')
    try {
      const res = await fetch(`${API}/tasks/copilot-suggestions/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          milestones: milestones.map(({ title, cognitive_load_score, estimated_minutes, tasks }) => ({
            title,
            cognitive_load_score,
            estimated_minutes,
            tasks: tasks.map(({ title: t, cognitive_load_score: l, estimated_minutes: e }) => ({
              title: t,
              cognitive_load_score: l,
              estimated_minutes: e,
            })),
          })),
        }),
      })
      if (!res.ok) throw new Error()
      onChange([])
      onApproved()
    } catch {
      setErr('Failed to add milestones. Is the backend running?')
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
            Co-Pilot milestones
          </p>
          <span className="rounded-full bg-[#8127cf]/10 px-2 py-0.5 text-[10px] font-semibold text-[#8127cf]">
            {milestones.length} · {taskCount} tasks
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

      {aiFallback && (
        <p className="border-b border-[#e0d9f7] px-4 py-2 text-xs text-amber-700 bg-amber-50">
          AI quota reached — showing rule-based milestone suggestions until tomorrow.
        </p>
      )}

      <div className="space-y-2 px-4 py-3">
        {milestones.map(milestone => {
          const isOpen = expanded[milestone.id] !== false
          const meta = LOAD_META[milestone.cognitive_load_score] ?? LOAD_META[5]
          return (
            <div key={milestone.id} className="rounded-lg border border-[#dce3f0] bg-white shadow-sm">
              <div className="flex items-start gap-2 px-3 py-2.5">
                <button
                  type="button"
                  onClick={() => toggle(milestone.id)}
                  className="mt-0.5 flex min-w-0 flex-1 items-start gap-2 text-left"
                >
                  <Target className="mt-0.5 h-4 w-4 shrink-0 text-[#4648d4]" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-[#191c1e]">{milestone.title}</p>
                    <div className="mt-0.5 flex flex-wrap gap-1.5">
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: meta.bg, color: meta.color }}>
                        {meta.label} · {milestone.cognitive_load_score}/10
                      </span>
                      <span className="text-[10px] text-[#6b7080]">
                        {milestone.tasks.length} tasks{milestone.estimated_minutes ? ` · ~${milestone.estimated_minutes} min` : ''}
                      </span>
                    </div>
                  </div>
                  {isOpen ? <ChevronUp className="h-4 w-4 shrink-0 text-[#6b7080]" /> : <ChevronDown className="h-4 w-4 shrink-0 text-[#6b7080]" />}
                </button>
                <button
                  type="button"
                  onClick={() => removeMilestone(milestone.id)}
                  className="rounded p-1 text-[#9092a8] hover:bg-red-50 hover:text-red-600"
                  aria-label="Remove milestone"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>

              {isOpen && (
                <div className="space-y-1 border-t border-[#eceef4] px-2 py-2">
                  {milestone.tasks.map(task => {
                    const tmeta = LOAD_META[task.cognitive_load_score] ?? LOAD_META[5]
                    const isEditing = editingTaskId === task.id
                    return (
                      <div key={task.id} className="rounded-md px-2 py-1.5 hover:bg-[#fafbfc]">
                        {isEditing ? (
                          <div className="space-y-2">
                            <input
                              autoFocus
                              value={editTitle}
                              onChange={e => setEditTitle(e.target.value)}
                              className="w-full rounded-md border border-[#d7d9e1] px-2.5 py-1.5 text-sm"
                            />
                            <div className="flex items-center gap-2">
                              <input type="range" min={1} max={10} value={editLoad} onChange={e => setEditLoad(Number(e.target.value))} className="flex-1" />
                              <span className="text-xs font-semibold text-[#8127cf]">{editLoad}/10</span>
                            </div>
                            <div className="flex gap-2">
                              <button type="button" onClick={() => saveEdit(milestone.id)} className="rounded-md bg-[#8127cf] px-2.5 py-1 text-xs font-semibold text-white">Save</button>
                              <button type="button" onClick={() => setEditingTaskId(null)} className="rounded-md border px-2.5 py-1 text-xs text-[#6b7080]">Cancel</button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <p className="flex-1 text-xs text-[#191c1e]">{task.title}</p>
                            <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: tmeta.bg, color: tmeta.color }}>
                              {tmeta.label}
                            </span>
                            <button type="button" onClick={() => startEdit(task)} className="rounded p-1 text-[#9092a8] hover:text-[#8127cf]"><Pencil className="h-3 w-3" /></button>
                            <button type="button" onClick={() => removeTask(milestone.id, task.id)} className="rounded p-1 text-[#9092a8] hover:text-red-600"><Trash2 className="h-3 w-3" /></button>
                          </div>
                        )}
                      </div>
                    )
                  })}
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
          disabled={saving || taskCount === 0}
          className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-sm font-semibold text-white transition hover:bg-[#3f3dc6] disabled:opacity-60"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          {saving ? 'Adding…' : `Add ${milestones.length} milestone${milestones.length !== 1 ? 's' : ''} to my plan`}
        </button>
      </div>
    </div>
  )
}
