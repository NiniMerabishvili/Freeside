'use client'

import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  ChevronDown, ChevronUp, CheckCircle2, Loader2, Lock, Pencil, Plus, Scissors, Sparkles,
  Square, CheckSquare, Target, Trash2, X, Brain, Zap,
} from 'lucide-react'
import AppShell from '@/components/AppShell'
import EnergyPanel from '@/components/EnergyPanel'
import SleepPanel from '@/components/SleepPanel'
import CoPilot, { type CopilotSuggestedMilestone } from '@/components/CoPilot'
import SuggestedTasksPanel, { type SuggestedMilestone } from '@/components/SuggestedTasksPanel'
import SyncWarningsBanner, { type SyncWarning } from '@/components/SyncWarningsBanner'
import GoalsPanel from '@/components/GoalsPanel'
import { supabase } from '@/lib/supabase'
import { effectiveTaskXp, taskXp } from '@/lib/xp'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function dedupeTasksById(tasks: Task[]): Task[] {
  const byId = new Map<string, Task>()
  for (const task of tasks) {
    const prev = byId.get(task.id)
    if (!prev) {
      byId.set(task.id, task)
      continue
    }
    const prevHidden = prev.visible === false
    const curHidden = task.visible === false
    if (prevHidden && !curHidden) byId.set(task.id, task)
  }
  return Array.from(byId.values())
}

// ── Types ─────────────────────────────────────────────────────────────────────

type Task = {
  id: string
  title: string
  description?: string
  cognitive_load_score: number
  xp_earned?: number | null
  status: string
  visible?: boolean
  reroute_reason?: string
  unlock_score?: number
  delta?: number
  priority_score?: number
  completed_at?: string
  parent_task_id?: string | null
  parent_title?: string
  progress_percent?: number
  is_blocked?: boolean
  step_order?: number
  milestone_id?: string | null
  milestone_title?: string
  scheduled_block_start?: string | null
  scheduled_block_end?: string | null
  estimated_minutes?: number
  defer_reason?: string
}

type MilestoneGroup = {
  milestone_id: string
  milestone_title: string
  goal_id?: string
  progress_percent: number
  active: Task[]
  blocked: Task[]
  deferred?: Task[]
}

type ParsedTask = { title: string; cognitive_load_score: number; reasoning?: string }

const LOAD_META: Record<number, { label: string; color: string; bg: string }> = {}
for (let i = 1; i <= 10; i++) {
  if (i <= 3)       LOAD_META[i] = { label: 'Light',    color: '#2d7a3a', bg: '#e6f4ea' }
  else if (i <= 6)  LOAD_META[i] = { label: 'Moderate', color: '#7a5c00', bg: '#fdf3d0' }
  else              LOAD_META[i] = { label: 'Deep Work', color: '#1f22f0', bg: '#e8e7ff' }
}

// ── Add Task Modal ─────────────────────────────────────────────────────────────

function AddTaskModal({ userId, goalId, onClose, onCreated }: {
  userId: string
  goalId?: string | null
  onClose: () => void
  onCreated: (task: Task) => void
}) {
  const [title, setTitle]     = useState('')
  const [desc, setDesc]       = useState('')
  const [load, setLoad]       = useState(5)
  const [saving, setSaving]   = useState(false)
  const [err, setErr]         = useState('')

  const PRESETS = [
    { value: 2,  label: '💤 Light',    hint: 'Admin, quick replies',       color: '#2d7a3a', bg: '#e6f4ea' },
    { value: 5,  label: '📋 Moderate', hint: 'Meetings, regular work',     color: '#7a5c00', bg: '#fdf3d0' },
    { value: 8,  label: '🧠 Deep Work', hint: 'Strategy, writing, building', color: '#1f22f0', bg: '#e8e7ff' },
  ]

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) { setErr('Title is required.'); return }
    setSaving(true)
    try {
      const res  = await fetch(`${API}/tasks/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId, title: title.trim(),
          description: desc.trim() || null,
          cognitive_load_score: load,
          goal_id: goalId ?? null,
        }),
      })
      if (!res.ok) throw new Error()
      const task = await res.json()
      onCreated(task)
      onClose()
    } catch {
      setErr('Failed to create task. Is the backend running?')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-md rounded-xl border border-[#eceef4] bg-white shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#eceef4] px-5 py-4">
          <h2 className="text-sm font-bold text-[#191c1e]">New Task</h2>
          <button onClick={onClose} className="rounded p-1 text-[#6b7080] hover:bg-[#f4f4f8]"><X className="h-4 w-4" /></button>
        </div>
        <form onSubmit={submit} className="px-5 py-4 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Task title *</label>
            <input
              autoFocus value={title} onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Write project introduction"
              className="w-full rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#4648d4]"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Description <span className="font-normal text-[#adb0bb]">(optional)</span></label>
            <textarea
              value={desc} onChange={e => setDesc(e.target.value)} placeholder="Any extra context…" rows={2}
              className="w-full resize-none rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#4648d4]"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Cognitive load</label>
            <div className="grid grid-cols-3 gap-2">
              {PRESETS.map(p => (
                <button key={p.value} type="button" onClick={() => setLoad(p.value)}
                  className="rounded-lg border px-3 py-2.5 text-left transition"
                  style={load === p.value
                    ? { borderColor: p.color, backgroundColor: p.bg, color: p.color }
                    : { borderColor: '#d7d9e1', backgroundColor: 'white', color: '#4a4a58' }}
                >
                  <p className="text-xs font-bold">{p.label}</p>
                  <p className="mt-0.5 text-[10px] leading-tight opacity-70">{p.hint}</p>
                </button>
              ))}
            </div>
          </div>
          {err && <p className="text-xs text-red-600">{err}</p>}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="flex-1 rounded-lg border border-[#d7d9e1] py-2 text-sm font-semibold text-[#4a4a58] hover:bg-[#f5f5f8]">Cancel</button>
            <button type="submit" disabled={saving} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-[#4648d4] py-2 text-sm font-semibold text-white hover:bg-[#3f3dc6] disabled:opacity-60">
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Create task
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Brain Dump Modal ───────────────────────────────────────────────────────────

function BrainDumpModal({ userId, onClose, onCreated }: {
  userId: string
  onClose: () => void
  onCreated: (tasks: Task[]) => void
}) {
  const [text, setText]                 = useState('')
  const [parsing, setParsing]           = useState(false)
  const [parsed, setParsed]             = useState<ParsedTask[] | null>(null)
  const [saving, setSaving]             = useState(false)
  const [err, setErr]                   = useState('')
  const [selected, setSelected]         = useState<Set<number>>(new Set())

  const parse = async () => {
    if (!text.trim()) { setErr('Write something first.'); return }
    setParsing(true); setErr('')
    try {
      const res  = await fetch(`${API}/tasks/brain-dump`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, raw_text: text }),
      })
      const data = await res.json()
      setParsed(data.tasks ?? [])
      setSelected(new Set((data.tasks ?? []).map((_: ParsedTask, i: number) => i)))
    } catch {
      setErr('Failed to parse. Is the backend running?')
    } finally {
      setParsing(false)
    }
  }

  const confirm = async () => {
    if (!parsed) return
    const tasks = parsed.filter((_, i) => selected.has(i))
    setSaving(true)
    try {
      const res  = await fetch(`${API}/tasks/brain-dump/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, tasks }),
      })
      const data = await res.json()
      onCreated(data.tasks ?? [])
      onClose()
    } catch {
      setErr('Failed to save tasks.')
    } finally {
      setSaving(false)
    }
  }

  const toggle = (i: number) => setSelected(prev => {
    const s = new Set(prev)
    s.has(i) ? s.delete(i) : s.add(i)
    return s
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl border border-[#eceef4] bg-white shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#eceef4] px-5 py-4">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-[#8127cf]" />
            <h2 className="text-sm font-bold text-[#191c1e]">Brain Dump</h2>
          </div>
          <button onClick={onClose} className="rounded p-1 text-[#6b7080] hover:bg-[#f4f4f8]"><X className="h-4 w-4" /></button>
        </div>

        {!parsed ? (
          <div className="px-5 py-4 space-y-4">
            <p className="text-xs text-[#6b7080]">
              Type everything on your mind. AI will parse it into tasks with cognitive load scores.
            </p>
            <textarea
              autoFocus value={text} onChange={e => setText(e.target.value)}
              placeholder="I need to finish that report, email Sarah about the meeting, prep for Thursday, figure out the website bug..."
              rows={5}
              className="w-full resize-none rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#8127cf]"
            />
            {err && <p className="text-xs text-red-600">{err}</p>}
            <div className="flex gap-2">
              <button type="button" onClick={onClose} className="flex-1 rounded-lg border border-[#d7d9e1] py-2 text-sm font-semibold text-[#4a4a58] hover:bg-[#f5f5f8]">Cancel</button>
              <button onClick={parse} disabled={parsing} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-[#8127cf] py-2 text-sm font-semibold text-white hover:bg-[#6d1fb3] disabled:opacity-60">
                {parsing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                {parsing ? 'Parsing…' : 'Parse with AI'}
              </button>
            </div>
          </div>
        ) : (
          <div className="px-5 py-4 space-y-3">
            <p className="text-xs text-[#6b7080]">Review parsed tasks. Uncheck any you don't want.</p>
            <div className="max-h-72 space-y-2 overflow-y-auto">
              {parsed.map((t, i) => {
                const meta = LOAD_META[t.cognitive_load_score] ?? LOAD_META[5]
                return (
                  <button key={i} type="button" onClick={() => toggle(i)}
                    className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition ${selected.has(i) ? 'border-[#8127cf] bg-[#faf7ff]' : 'border-[#eceef4] bg-white opacity-50'}`}
                  >
                    {selected.has(i)
                      ? <CheckSquare className="h-4 w-4 shrink-0 text-[#8127cf]" />
                      : <Square className="h-4 w-4 shrink-0 text-[#d0d3e0]" />}
                    <span className="flex-1 text-sm text-[#191c1e]">{t.title}</span>
                    <span className="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold" style={{ backgroundColor: meta.bg, color: meta.color }}>
                      {meta.label}
                    </span>
                  </button>
                )
              })}
            </div>
            {err && <p className="text-xs text-red-600">{err}</p>}
            <div className="flex gap-2 pt-1">
              <button type="button" onClick={() => setParsed(null)} className="flex-1 rounded-lg border border-[#d7d9e1] py-2 text-sm font-semibold text-[#4a4a58] hover:bg-[#f5f5f8]">← Edit dump</button>
              <button onClick={confirm} disabled={saving || selected.size === 0} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-[#4648d4] py-2 text-sm font-semibold text-white hover:bg-[#3f3dc6] disabled:opacity-60">
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Add {selected.size} task{selected.size !== 1 ? 's' : ''}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Task grouping (split parent + subtasks) ────────────────────────────────────

type ParentGroup = {
  parentId: string
  parentTitle: string
  progressPercent: number
  active: Task[]
  blocked: Task[]
}

function buildTaskGroups(tasks: Task[]): { standalone: Task[]; groups: ParentGroup[] } {
  const deduped = dedupeTasksById(tasks)
  const parentIdsWithChildren = new Set(
    deduped.filter(t => t.parent_task_id).map(t => t.parent_task_id as string),
  )
  const standalone: Task[] = []
  const byParent = new Map<string, ParentGroup>()

  for (const t of deduped) {
    if (t.milestone_id) continue
    if (!t.parent_task_id) {
      // Split parent shells are shown via subtask groups only
      if (parentIdsWithChildren.has(t.id)) continue
      if (t.visible !== false) standalone.push(t)
      continue
    }
    const pid = t.parent_task_id
    if (!byParent.has(pid)) {
      byParent.set(pid, {
        parentId: pid,
        parentTitle: t.parent_title ?? 'Task',
        progressPercent: t.progress_percent ?? 0,
        active: [],
        blocked: [],
      })
    }
    const g = byParent.get(pid)!
    if (t.progress_percent != null) g.progressPercent = t.progress_percent
    if (t.parent_title) g.parentTitle = t.parent_title
    if (t.visible === false || t.is_blocked) g.blocked.push(t)
    else g.active.push(t)
  }

  for (const g of byParent.values()) {
    g.active = dedupeTasksById(g.active)
    g.blocked = dedupeTasksById(g.blocked)
    g.active.sort((a, b) => (a.step_order ?? 99) - (b.step_order ?? 99))
    g.blocked.sort((a, b) => (a.step_order ?? 99) - (b.step_order ?? 99))
  }

  return { standalone, groups: Array.from(byParent.values()) }
}

function ParentTaskGroup({ group, userId, energyScore, energyLevel, onCompleted, onUpdated, onDeleted }: {
  group: ParentGroup
  userId: string
  energyScore?: number
  energyLevel?: string
  onCompleted: (task: Task, xpTotal?: number) => void
  onUpdated: (task: Task) => void
  onDeleted: (id: string) => void
}) {
  return (
    <div className="rounded-lg border border-[#e0d9f7] bg-[#faf7ff]">
      <div className="border-b border-[#e8e0f7] px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#8127cf]">Split task</p>
            <p className="mt-0.5 truncate text-sm font-semibold text-[#2d2d40]">{group.parentTitle}</p>
          </div>
          <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-bold text-[#8127cf]">
            {group.progressPercent}% done
          </span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#eceef4]">
          <div
            className="h-full rounded-full bg-[#8127cf] transition-all"
            style={{ width: `${group.progressPercent}%` }}
          />
        </div>
      </div>
      <div className="space-y-px p-2">
        {group.active.map(t => (
          <TaskCard
            key={t.id}
            task={t}
            userId={userId}
            energyScore={energyScore}
            energyLevel={energyLevel}
            isSubtask
            onCompleted={onCompleted}
            onUpdated={onUpdated}
            onDeleted={onDeleted}
          />
        ))}
      </div>
    </div>
  )
}

function formatBlockTime(value: string | null | undefined): string | null {
  if (!value) return null
  const parts = value.split(':')
  if (parts.length < 2) return null
  const h = parseInt(parts[0], 10)
  const m = parts[1]
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12
  return `${h12}:${m} ${ampm}`
}

function MilestoneTaskGroup({
  group,
  userId,
  energyScore,
  energyLevel,
  defaultExpanded = true,
  onCompleted,
  onUpdated,
  onDeleted,
}: {
  group: MilestoneGroup
  userId: string
  energyScore?: number
  energyLevel?: string
  defaultExpanded?: boolean
  onCompleted: (task: Task, xpTotal?: number) => void
  onUpdated: (task: Task) => void
  onDeleted: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const allTasks = [...group.active, ...(group.blocked ?? []), ...(group.deferred ?? [])]

  return (
    <div className="rounded-lg border border-[#dce3f0] bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="flex w-full items-start gap-3 border-b border-[#eceef4] px-4 py-3 text-left hover:bg-[#fafbfc]"
      >
        <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#e8e7ff] text-[#4648d4]">
          <Target className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-widest text-[#4648d4]">Milestone</p>
          <p className="mt-0.5 truncate text-sm font-semibold text-[#191c1e]">{group.milestone_title}</p>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#eceef4]">
              <div
                className="h-full rounded-full bg-[#4648d4] transition-all"
                style={{ width: `${group.progress_percent}%` }}
              />
            </div>
            <span className="text-xs font-bold text-[#4648d4]">{group.progress_percent}%</span>
          </div>
          <p className="mt-1 text-[10px] text-[#6b7080]">
            {group.active.length} active · {(group.blocked?.length ?? 0) + (group.deferred?.length ?? 0)} waiting
          </p>
        </div>
        {expanded ? (
          <ChevronUp className="mt-1 h-4 w-4 shrink-0 text-[#6b7080]" />
        ) : (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-[#6b7080]" />
        )}
      </button>
      {expanded && (
        <div className="space-y-px p-2">
          {allTasks.length === 0 ? (
            <p className="px-3 py-4 text-center text-xs text-[#6b7080]">No tasks scheduled for this milestone today.</p>
          ) : (
            allTasks.map(t => (
              <TaskCard
                key={t.id}
                task={t}
                userId={userId}
                energyScore={energyScore}
                energyLevel={energyLevel}
                isSubtask
                blocked={t.visible === false || !!t.defer_reason}
                onCompleted={onCompleted}
                onUpdated={onUpdated}
                onDeleted={onDeleted}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Task Card ──────────────────────────────────────────────────────────────────

function TaskCard({ task, userId, energyScore, energyLevel, isSubtask, blocked, onCompleted, onUpdated, onDeleted }: {
  task: Task
  userId: string
  energyScore?: number
  energyLevel?: string
  isSubtask?: boolean
  blocked?: boolean
  onCompleted: (task: Task, xpTotal?: number) => void
  onUpdated: (task: Task) => void
  onDeleted: (id: string) => void
}) {
  const [completing, setCompleting]   = useState(false)
  const [completeErr, setCompleteErr] = useState('')
  const [steps, setSteps]             = useState<{ text: string; done: boolean }[] | null>(null)
  const [loadingSteps, setLoadingSteps] = useState(false)
  const [stepsOpen, setStepsOpen]     = useState(false)
  const [editing, setEditing]         = useState(false)
  const [editTitle, setEditTitle]     = useState(task.title)
  const [editDesc, setEditDesc]       = useState(task.description ?? '')
  const [editLoad, setEditLoad]       = useState(task.cognitive_load_score)
  const [saving, setSaving]           = useState(false)
  const [deleting, setDeleting]       = useState(false)
  const [editErr, setEditErr]         = useState('')
  const finishingRef                  = useRef(false)
  const meta = LOAD_META[task.cognitive_load_score] ?? LOAD_META[5]
  const isBlocked = blocked || task.is_blocked || task.visible === false
  const dimmed = isBlocked

  const LOAD_PRESETS = [
    { value: 2, label: 'Light', color: '#2d7a3a', bg: '#e6f4ea' },
    { value: 5, label: 'Moderate', color: '#7a5c00', bg: '#fdf3d0' },
    { value: 8, label: 'Deep', color: '#1f22f0', bg: '#e8e7ff' },
  ]

  const complete = async () => {
    if (completing || finishingRef.current) return
    finishingRef.current = true
    setCompleting(true)
    setCompleteErr('')
    try {
      const res = await fetch(`${API}/tasks/${task.id}/complete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id:      userId,
          was_rerouted: task.visible === false,
          energy_score: energyScore ?? null,
          energy_level: energyLevel ?? null,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Failed to complete task.'
        throw new Error(detail)
      }
      onCompleted({
        ...task,
        status: 'completed',
        completed_at: data.completed_at ?? new Date().toISOString(),
        xp_earned: data.xp_earned ?? taskXp(task.cognitive_load_score),
      }, data.xp_total)
    } catch (err) {
      finishingRef.current = false
      setCompleteErr(err instanceof Error ? err.message : 'Failed to complete task.')
    } finally {
      setCompleting(false)
    }
  }

  const breakDown = async () => {
    setStepsOpen(true)
    if (steps) return
    setLoadingSteps(true)
    try {
      const res = await fetch(`${API}/tasks/breakdown`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id:    userId,
          task_id:    task.id,
          task_title: task.title,
        }),
      })
      const data = await res.json()
      const parsed = (data.steps ?? []).map((s: { text: string }) => ({
        text: s.text,
        done: false,
      }))
      setSteps(parsed.length ? parsed : [{ text: 'Could not generate steps.', done: false }])
    } catch {
      setSteps([{ text: 'Could not generate steps. Try again.', done: false }])
    } finally {
      setLoadingSteps(false)
    }
  }

  const toggleStep = (i: number) => {
    setSteps(prev => {
      if (!prev) return null
      const updated = prev.map((s, idx) => (idx === i ? { ...s, done: !s.done } : s))
      if (updated.length > 0 && updated.every(s => s.done)) {
        queueMicrotask(() => complete())
      }
      return updated
    })
  }

  const doneCount = steps?.filter(s => s.done).length ?? 0
  const totalSteps = steps?.length ?? 0

  const startEdit = () => {
    setEditTitle(task.title)
    setEditDesc(task.description ?? '')
    setEditLoad(task.cognitive_load_score)
    setEditErr('')
    setEditing(true)
  }

  const saveEdit = async () => {
    if (!editTitle.trim()) { setEditErr('Title is required.'); return }
    setSaving(true)
    setEditErr('')
    try {
      const res = await fetch(`${API}/tasks/${task.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          title: editTitle.trim(),
          description: editDesc.trim() || null,
          cognitive_load_score: editLoad,
        }),
      })
      if (!res.ok) throw new Error()
      const updated = await res.json()
      setEditing(false)
      onUpdated(updated)
    } catch {
      setEditErr('Failed to save changes.')
    } finally {
      setSaving(false)
    }
  }

  const deleteTask = async () => {
    if (!window.confirm(`Delete "${task.title}"?`)) return
    setDeleting(true)
    try {
      const res = await fetch(`${API}/tasks/${task.id}?user_id=${userId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error()
      onDeleted(task.id)
    } catch {
      window.alert('Failed to delete task.')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className={`group rounded-lg border border-[#eceef4] bg-white transition hover:border-[#d0d3e8] ${dimmed ? 'opacity-60' : ''} ${isSubtask ? 'border-transparent shadow-none' : ''}`}>
      {editing ? (
        <div className="space-y-3 px-4 py-3">
          <input
            autoFocus
            value={editTitle}
            onChange={e => setEditTitle(e.target.value)}
            className="w-full rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm text-[#191c1e] outline-none focus:border-[#4648d4]"
          />
          <textarea
            value={editDesc}
            onChange={e => setEditDesc(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full resize-none rounded-lg border border-[#d7d9e1] px-3 py-2 text-xs text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#4648d4]"
          />
          <div className="flex gap-2">
            {LOAD_PRESETS.map(p => (
              <button
                key={p.value}
                type="button"
                onClick={() => setEditLoad(p.value)}
                className="flex-1 rounded-lg border px-2 py-1.5 text-xs font-semibold transition"
                style={editLoad === p.value
                  ? { borderColor: p.color, backgroundColor: p.bg, color: p.color }
                  : { borderColor: '#d7d9e1', color: '#6b7080' }}
              >
                {p.label} {p.value}
              </button>
            ))}
          </div>
          {editErr && <p className="text-xs text-red-600">{editErr}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="flex-1 rounded-lg border border-[#d7d9e1] py-1.5 text-xs font-semibold text-[#6b7080] hover:bg-[#f5f5f8]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={saveEdit}
              disabled={saving}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[#4648d4] py-1.5 text-xs font-semibold text-white hover:bg-[#3f3dc6] disabled:opacity-60"
            >
              {saving && <Loader2 className="h-3 w-3 animate-spin" />}
              Save
            </button>
          </div>
        </div>
      ) : (
      <>
      {/* Main row */}
      <div className="flex items-start gap-3 px-4 py-3">
        {isBlocked ? (
          <div
            className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded border-2 border-[#e0d9f7] bg-[#f6f4ff] text-[#8127cf]"
            title="Blocked until your energy is higher"
          >
            <Lock className="h-3 w-3" />
          </div>
        ) : (
        <button
          onClick={complete} disabled={completing}
          className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded border-2 border-[#d0d3e0] transition hover:border-[#4648d4]"
        >
          {completing && <Loader2 className="h-3 w-3 animate-spin text-[#4648d4]" />}
        </button>
        )}

        <div className="min-w-0 flex-1">
          {isSubtask && task.step_order != null && (
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[#adb0bb]">
              Step {task.step_order}
            </p>
          )}
          <p className={`truncate text-sm font-medium text-[#191c1e] ${isBlocked ? 'text-[#6b7080]' : ''}`}>{task.title}</p>
          {task.scheduled_block_start && (
            <p className="mt-0.5 text-[10px] font-semibold text-[#8127cf]">
              {formatBlockTime(task.scheduled_block_start)}
              {task.scheduled_block_end && ` – ${formatBlockTime(task.scheduled_block_end)}`}
              {task.estimated_minutes ? ` · ~${task.estimated_minutes} min` : ''}
            </p>
          )}
          {task.description && <p className="mt-0.5 text-xs text-[#6b7080] line-clamp-1">{task.description}</p>}
          {dimmed && task.reroute_reason && (
            <p className="mt-1 text-xs text-amber-600">
              {isBlocked ? '🔒 Blocked — ' : ''}{task.reroute_reason}
              {task.unlock_score ? ` (unlock at ${task.unlock_score}+/10)` : ''}
            </p>
          )}
          {/* CLCS delta chip — subtle context for the user */}
          {!dimmed && task.delta !== undefined && (
            <p className="mt-0.5 text-[10px] text-[#adb0bb]">
              delta {task.delta > 0 ? '+' : ''}{task.delta} · priority {task.priority_score}/10
            </p>
          )}
          {completeErr && <p className="mt-1 text-xs text-red-600">{completeErr}</p>}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {!dimmed && !isSubtask && (
            <button
              onClick={breakDown}
              title="Break into micro-steps"
              className="flex items-center gap-1 rounded-md border border-[#e0d9f7] bg-[#f6f4ff] px-2 py-1 text-xs font-medium text-[#8127cf] opacity-0 transition hover:bg-[#ebe8ff] group-hover:opacity-100"
            >
              <Scissors className="h-3 w-3" />
              Break down
            </button>
          )}
          <button
            type="button"
            onClick={startEdit}
            title="Edit task"
            className="rounded p-1 text-[#9092a8] opacity-0 transition hover:bg-[#f0f1f5] hover:text-[#4648d4] group-hover:opacity-100"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={deleteTask}
            disabled={deleting}
            title="Delete task"
            className="rounded p-1 text-[#9092a8] opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 disabled:opacity-40"
          >
            {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
          </button>
          <span className="ml-1 rounded-full px-2 py-0.5 text-xs font-semibold" style={{ backgroundColor: meta.bg, color: meta.color }}>
            {meta.label} {task.cognitive_load_score}
          </span>
          <span className="rounded-full bg-[#f5f4ff] px-2 py-0.5 text-xs font-bold text-[#4648d4]" title="XP on completion">
            +{taskXp(task.cognitive_load_score)} XP
          </span>
        </div>
      </div>

      {/* Micro-steps accordion */}
      {stepsOpen && !dimmed && (
        <div className="border-t border-[#f0f1f5] px-4 pb-3 pt-2">
          {loadingSteps ? (
            <div className="flex items-center gap-2 py-1 text-xs text-[#8127cf]">
              <Loader2 className="h-3 w-3 animate-spin" /> Generating micro-steps…
            </div>
          ) : (
            <>
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-[#adb0bb]">
                    <Zap className="h-3 w-3 text-[#8127cf]" /> Micro-steps
                  </div>
                  {totalSteps > 0 && (
                    <span className="rounded-full bg-[#f0e5fb] px-2 py-0.5 text-[10px] font-semibold text-[#8127cf]">
                      {doneCount}/{totalSteps}
                    </span>
                  )}
                </div>
                <button onClick={() => setStepsOpen(false)} className="text-[10px] text-[#adb0bb] hover:text-[#6b7080]">
                  hide
                </button>
              </div>
              {totalSteps > 0 && (
                <div className="mb-2 h-1 overflow-hidden rounded-full bg-[#eceef4]">
                  <div
                    className="h-full rounded-full bg-[#8127cf] transition-all"
                    style={{ width: `${(doneCount / totalSteps) * 100}%` }}
                  />
                </div>
              )}
              <ul className="space-y-1.5">
                {(steps ?? []).map((s, i) => (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => toggleStep(i)}
                      className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs transition hover:bg-[#f8f8fb] ${s.done ? 'opacity-50' : ''}`}
                    >
                      {s.done
                        ? <CheckSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#4648d4]" />
                        : <Square className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#d0d3e0]" />}
                      <span className={s.done ? 'line-through text-[#adb0bb]' : 'text-[#2d2d40]'}>{s.text}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      </>
      )}
    </div>
  )
}

function CompletedTaskRow({ task, userId, onDeleted }: {
  task: Task
  userId: string
  onDeleted: (id: string) => void
}) {
  const meta = LOAD_META[task.cognitive_load_score] ?? LOAD_META[5]
  const when = task.completed_at
    ? new Date(task.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null
  const [deleting, setDeleting] = useState(false)

  const deleteTask = async () => {
    if (!window.confirm(`Delete "${task.title}" from done list?`)) return
    setDeleting(true)
    try {
      const res = await fetch(`${API}/tasks/${task.id}?user_id=${userId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error()
      onDeleted(task.id)
    } catch {
      window.alert('Failed to delete task.')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="group flex items-center gap-3 px-4 py-2.5 opacity-70">
      <CheckCircle2 className="h-4 w-4 shrink-0 text-[#2d7a3a]" />
      <p className="min-w-0 flex-1 truncate text-sm text-[#6b7080] line-through">{task.title}</p>
      {when && <span className="shrink-0 text-[10px] text-[#adb0bb]">{when}</span>}
      <span
        className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
        style={{ backgroundColor: meta.bg, color: meta.color }}
      >
        {meta.label}
      </span>
      <span className="shrink-0 rounded-full bg-[#f5f4ff] px-2 py-0.5 text-[10px] font-bold text-[#4648d4]">
        +{effectiveTaskXp(task)} XP
      </span>
      <button
        type="button"
        onClick={deleteTask}
        disabled={deleting}
        title="Delete task"
        className="rounded p-1 text-[#9092a8] opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 disabled:opacity-40"
      >
        {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
      </button>
    </div>
  )
}

// ── Right Rail ────────────────────────────────────────────────────────────────

function RightRail({ userId, energyLevel, energyScore, triggerMessage, onTriggerConsumed, onTasksSuggested, onReportLowEnergy }: {
  userId: string | null
  energyLevel: string
  energyScore: number
  triggerMessage?: { text: string; taskId?: string; type?: string } | null
  onTriggerConsumed?: () => void
  onTasksSuggested?: (milestones: CopilotSuggestedMilestone[], aiFallback?: boolean) => void
  onReportLowEnergy?: () => void
}) {
  return (
    <div className="mx-5 mb-7 flex h-[min(720px,calc(100vh-2rem))] min-w-0 flex-col md:mx-10 xl:sticky xl:top-0 xl:mx-0 xl:mb-0 xl:h-screen xl:min-w-[320px] xl:max-w-[380px]">
      <CoPilot
        userId={userId}
        energyLevel={energyLevel}
        energyScore={energyScore}
        triggerMessage={triggerMessage}
        onTriggerConsumed={onTriggerConsumed}
        onTasksSuggested={onTasksSuggested}
        onReportLowEnergy={onReportLowEnergy}
      />
    </div>
  )
}

// ── Dashboard Page ─────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [userId, setUserId]             = useState<string | null>(null)
  const [energyLevel, setEnergyLevel]   = useState('')
  const [energyScore, setEnergyScore]   = useState(0)
  const [tasks, setTasks]               = useState<Task[]>([])
  const [completedTasks, setCompletedTasks] = useState<Task[]>([])
  const [loadingTasks, setLoadingTasks] = useState(false)
  const [showModal, setShowModal]       = useState(false)
  const [showBrainDump, setShowBrainDump] = useState(false)
  const [clcsMeta, setClcsMeta]         = useState<{
    effective_capacity?: number; peak_boost?: boolean; active_count?: number; rerouted_count?: number
  }>({})
  const [copilotTrigger, setCopilotTrigger] = useState<{
    text: string; taskId?: string; type?: string
  } | null>(null)
  const [suggestedMilestones, setSuggestedMilestones] = useState<SuggestedMilestone[]>([])
  const [suggestionsAiFallback, setSuggestionsAiFallback] = useState(false)
  const [planningDay, setPlanningDay] = useState(false)
  const [dayPlanSummary, setDayPlanSummary] = useState<string | null>(null)
  const [xpTotal, setXpTotal] = useState(0)
  const [goalsRefreshKey, setGoalsRefreshKey] = useState(0)
  const [milestoneGroups, setMilestoneGroups] = useState<MilestoneGroup[]>([])
  const [dailySchedule, setDailySchedule] = useState<{
    budget?: { max_load_points?: number; max_focus_minutes?: number }
    free_time?: { total_free_minutes?: number; block_count?: number }
    selected_count?: number
    deferred_count?: number
  } | null>(null)
  const [syncWarnings, setSyncWarnings] = useState<SyncWarning[]>([])
  const previewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchProfileStats = useCallback(async (uid: string) => {
    try {
      const res = await fetch(`${API}/profile/stats?user_id=${uid}`)
      if (!res.ok) return
      const data = await res.json()
      setXpTotal(data.xp_total ?? 0)
    } catch {
      // silently fail
    }
  }, [])

  const handleCopilotTasksSuggested = useCallback((incoming: CopilotSuggestedMilestone[], aiFallback?: boolean) => {
    if (!incoming.length) return
    setSuggestionsAiFallback(!!aiFallback)
    setSuggestedMilestones(
      incoming.map(m => ({
        id: crypto.randomUUID(),
        title: m.title,
        cognitive_load_score: m.cognitive_load_score,
        estimated_minutes: m.estimated_minutes,
        tasks: m.tasks.map(t => ({
          id: crypto.randomUUID(),
          title: t.title,
          cognitive_load_score: t.cognitive_load_score,
          estimated_minutes: t.estimated_minutes,
        })),
      }))
    )
  }, [])

  const fetchCompletedTasks = useCallback(async (uid: string) => {
    try {
      const res  = await fetch(`${API}/tasks/completed?user_id=${uid}`)
      const data = await res.json()
      setCompletedTasks(Array.isArray(data) ? data : [])
    } catch {
      // silently fail
    }
  }, [])

  const fetchTasks = useCallback(async (
    uid: string,
    logRouting = false,
    previewScore?: number,
    previewLevel?: string,
  ) => {
    setLoadingTasks(true)
    try {
      const params = new URLSearchParams({
        user_id: uid,
        log_routing: String(logRouting && previewScore == null),
      })
      if (previewScore != null) {
        params.set('energy_score', String(previewScore))
        if (previewLevel) params.set('energy_level', previewLevel)
      }
      const res  = await fetch(`${API}/tasks/routed?${params}`)
      const data = await res.json()
      setTasks(dedupeTasksById(data.tasks ?? []))
      setMilestoneGroups(data.milestone_groups ?? [])
      setDailySchedule(data.daily_schedule ?? null)
      setClcsMeta({
        effective_capacity: data.effective_capacity,
        peak_boost:         data.peak_boost,
        active_count:       data.active_count,
        rerouted_count:     data.rerouted_count,
      })
      setSyncWarnings(Array.isArray(data.sync_warnings) ? data.sync_warnings : [])
      fetchCompletedTasks(uid)
    } catch {
      // silently fail
    } finally {
      setLoadingTasks(false)
    }
  }, [fetchCompletedTasks])

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const uid = data.user?.id ?? null
      setUserId(uid)
      if (uid) fetchProfileStats(uid)
    })
  }, [fetchProfileStats])

  const planDay = useCallback(async (uid: string, level: string, score: number) => {
    try {
      const res = await fetch(`${API}/copilot/plan-day`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: uid,
          energy_level: level,
          energy_score: score,
        }),
      })
      if (!res.ok) return
      const data = await res.json()
      if (data.reply) {
        setDayPlanSummary(data.reply as string)
      }
      // Tasks synced to DB by plan-day; routing runs in fetchTasks next
    } catch {
      // plan-day is best-effort; routing still works without it
    }
  }, [])

  const handleEnergyConfirmed = useCallback(async (level: string, score: number, uid: string, isUpdate = false) => {
    setEnergyLevel(level)
    setEnergyScore(score)
    if (!isUpdate) {
      setPlanningDay(true)
      try {
        await planDay(uid, level, score)
      } finally {
        setPlanningDay(false)
      }
    }
    await fetchTasks(uid, true)
  }, [fetchTasks, planDay])

  const handleScorePreview = useCallback((level: string, score: number) => {
    if (!userId) return
    setEnergyLevel(level)
    setEnergyScore(score)
    if (previewTimerRef.current) clearTimeout(previewTimerRef.current)
    previewTimerRef.current = setTimeout(() => {
      void fetchTasks(userId, false, score, level)
    }, 200)
  }, [userId, fetchTasks])

  useEffect(() => {
    return () => {
      if (previewTimerRef.current) clearTimeout(previewTimerRef.current)
    }
  }, [])

  const handleReportLowEnergy = useCallback(async () => {
    if (!userId) return
    const newScore = Math.max(1, Math.min(energyScore, 3))
    const newLevel = newScore >= 7 ? 'high' : newScore >= 4 ? 'balanced' : 'low'
    if (newScore === energyScore && energyLevel === 'low') {
      await fetchTasks(userId, true)
      return
    }
    try {
      await fetch(`${API}/energy/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          confirmed_score: newScore,
          confirmed_level: newLevel,
        }),
      })
      await handleEnergyConfirmed(newLevel, newScore, userId, true)
    } catch {
      await fetchTasks(userId, true)
    }
  }, [userId, energyScore, energyLevel, fetchTasks, handleEnergyConfirmed])

  const handleTaskCreated = (_task: Task) => {
    if (userId) void fetchTasks(userId)
  }

  const handleBrainDumpCreated = (newTasks: Task[]) => {
    if (userId) fetchTasks(userId)
    // Confirm to co-pilot how many tasks were added
    if (newTasks.length) {
      setCopilotTrigger({
        text: `I just added ${newTasks.length} task${newTasks.length !== 1 ? 's' : ''} from a brain dump. Which should I start with given my current energy?`,
        type: 'user_initiated',
      })
    }
  }

  const handleTaskCompleted = (completed: Task, newXpTotal?: number) => {
    setTasks(prev => prev.filter(t => t.id !== completed.id))
    setCompletedTasks(prev => [
      {
        ...completed,
        status: 'completed',
        completed_at: completed.completed_at ?? new Date().toISOString(),
      },
      ...prev,
    ])
    if (typeof newXpTotal === 'number') {
      setXpTotal(newXpTotal)
    } else if (userId) {
      void fetchProfileStats(userId)
    }
    if (userId) {
      void fetchCompletedTasks(userId)
      void fetchTasks(userId)
      setGoalsRefreshKey(k => k + 1)
    }
  }

  const handleTaskUpdated = () => {
    if (userId) fetchTasks(userId)
  }

  const handleTaskDeleted = (id: string) => {
    setTasks(prev => prev.filter(t => t.id !== id))
    setCompletedTasks(prev => prev.filter(t => t.id !== id))
    if (userId) {
      fetchTasks(userId)
      void fetchProfileStats(userId)
    }
  }

  const visibleTasks  = tasks.filter(t => t.visible !== false)
  const deferredTasks = tasks.filter(t => t.visible === false)
  const { standalone: standaloneTasks, groups: parentGroups } = buildTaskGroups(tasks)
  const blockedSubtasks = parentGroups.flatMap(g => g.blocked)
  const deferredWholeTasks = deferredTasks.filter(t => !t.parent_task_id)
  const futureTasks = [...blockedSubtasks, ...deferredWholeTasks]
  const hasActiveTasks =
    standaloneTasks.length > 0
    || parentGroups.some(g => g.active.length > 0)
    || milestoneGroups.some(g => g.active.length > 0)

  // When there are no visible tasks and energy is set → offer co-pilot help
  const handleRequestLightTasks = () => {
    setCopilotTrigger({
      text: `My energy is ${energyScore}/10 and I have no suitable tasks showing. Can you suggest 2–3 light things I could do based on my goals?`,
      type: 'proactive',
    })
  }

  const rightRail = (
    <RightRail
      userId={userId}
      energyLevel={energyLevel}
      energyScore={energyScore}
      triggerMessage={copilotTrigger}
      onTriggerConsumed={() => setCopilotTrigger(null)}
      onTasksSuggested={handleCopilotTasksSuggested}
      onReportLowEnergy={() => void handleReportLowEnergy()}
    />
  )

  const isFirstVisit = tasks.length === 0 && !loadingTasks && !energyLevel && suggestedMilestones.length === 0
  const showTaskSection = !isFirstVisit || suggestedMilestones.length > 0 || completedTasks.length > 0

  return (
    <AppShell active="focus" rightRail={rightRail}>
      {showModal && userId && (
        <AddTaskModal
          userId={userId}
          onClose={() => setShowModal(false)}
          onCreated={handleTaskCreated}
        />
      )}
      {showBrainDump && userId && (
        <BrainDumpModal
          userId={userId}
          onClose={() => setShowBrainDump(false)}
          onCreated={handleBrainDumpCreated}
        />
      )}

      <div className="min-h-screen bg-[#f8f9fb] px-5 py-7 md:px-10">
        <div className="mx-auto max-w-2xl space-y-7">

          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold text-[#191c1e]">Dashboard</h1>
            <p className="mt-0.5 text-sm text-[#6b7080]">
              {energyLevel
                ? `Routing tasks for ${energyLevel} energy (${clcsMeta.effective_capacity ?? energyScore}/10 effective capacity${clcsMeta.peak_boost ? ' ⚡ +1 peak boost' : ''})`
                : "Let's calibrate your day."}
              {xpTotal > 0 && (
                <span className="ml-2 font-semibold text-[#4648d4]">· {xpTotal} XP total</span>
              )}
            </p>
          </div>

          {/* Morning check-in */}
          <section className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#adb0bb]">Morning check-in</p>
            <Suspense fallback={
              <div className="flex items-center gap-3 rounded-lg border border-[#eceef4] bg-white px-4 py-3 text-sm text-[#6b7080]">
                <Loader2 className="h-4 w-4 animate-spin text-[#4648d4]" />
                Loading check-in…
              </div>
            }>
              <EnergyPanel onConfirmed={handleEnergyConfirmed} onScoreChange={handleScorePreview} />
            </Suspense>
            <SleepPanel />
          </section>

          {/* Goals — persistent anchor with milestone timeline */}
          {userId && (
            <GoalsPanel
              userId={userId}
              refreshKey={goalsRefreshKey}
              onGoalsChanged={() => userId && void fetchTasks(userId)}
            />
          )}

          {/* Cold-start: first visit with no tasks */}
          {isFirstVisit && (
            <section className="rounded-lg border border-dashed border-[#d0d3e0] bg-white px-6 py-10 text-center">
              <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-[#e8e7ff] text-[#4648d4]">
                <Sparkles className="h-5 w-5" />
              </div>
              <p className="text-sm font-semibold text-[#191c1e]">Welcome to Freeside</p>
              <p className="mx-auto mt-1 max-w-xs text-xs text-[#6b7080]">
                Start your energy check-in above, then add your first tasks — or let AI build a list from your goal.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                <button
                  onClick={() => setShowModal(true)}
                  className="flex items-center gap-1.5 rounded-lg bg-[#4648d4] px-4 py-2 text-xs font-semibold text-white hover:bg-[#3f3dc6]"
                >
                  <Plus className="h-3.5 w-3.5" /> Add first task
                </button>
                <button
                  onClick={() => setShowBrainDump(true)}
                  className="flex items-center gap-1.5 rounded-lg border border-[#e0d9f7] bg-[#f6f4ff] px-4 py-2 text-xs font-semibold text-[#8127cf] hover:bg-[#ebe8ff]"
                >
                  <Brain className="h-3.5 w-3.5" /> Brain dump
                </button>
              </div>
            </section>
          )}

          {/* Task section */}
          {showTaskSection && userId && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-[#adb0bb]">Tasks</p>
                  {energyLevel && clcsMeta.active_count !== undefined && (
                    <p className="mt-0.5 text-xs text-[#6b7080]">
                      <span className="font-semibold text-[#4648d4]">{clcsMeta.active_count} active</span>
                      {clcsMeta.rerouted_count ? ` · ${clcsMeta.rerouted_count} deferred` : ''}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowBrainDump(true)}
                    className="flex items-center gap-1.5 rounded-lg border border-[#e0d9f7] bg-[#f6f4ff] px-3 py-1.5 text-xs font-semibold text-[#8127cf] shadow-sm hover:bg-[#ebe8ff]"
                  >
                    <Brain className="h-3.5 w-3.5" /> Brain dump
                  </button>
                  <button
                    onClick={() => setShowModal(true)}
                    className="flex items-center gap-1.5 rounded-lg border border-[#d7d9e1] bg-white px-3 py-1.5 text-xs font-semibold text-[#4a4a58] shadow-sm hover:bg-[#f5f5f8]"
                  >
                    <Plus className="h-3.5 w-3.5" /> Add task
                  </button>
                </div>
              </div>

              <SyncWarningsBanner warnings={syncWarnings} />

              {planningDay && (
                <div className="mb-4 flex items-center gap-2 rounded-lg border border-[#e0d9f7] bg-[#faf7ff] px-4 py-3 text-sm text-[#8127cf]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analysing calendar, ClickUp, and Co-Pilot chat to plan your day…
                </div>
              )}

              {dayPlanSummary && !planningDay && (
                <div className="mb-4 rounded-lg border border-[#e0d9f7] bg-[#faf7ff] px-4 py-3 text-sm text-[#2d2d40]">
                  <p className="text-xs font-semibold uppercase tracking-widest text-[#8127cf] mb-1">Today&apos;s plan</p>
                  <p>{dayPlanSummary}</p>
                </div>
              )}

              {dailySchedule && !planningDay && energyLevel && (
                <div className="mb-4 rounded-lg border border-[#dce3f0] bg-[#f8f9fc] px-4 py-3 text-xs text-[#4a4a58]">
                  <p className="font-semibold text-[#4648d4]">Today&apos;s schedule</p>
                  <p className="mt-1">
                    {dailySchedule.selected_count ?? 0} milestone tasks assigned
                    {dailySchedule.free_time?.total_free_minutes != null && (
                      <> · {dailySchedule.free_time.total_free_minutes} min free after calendar</>
                    )}
                    {dailySchedule.budget?.max_load_points != null && (
                      <> · cognitive budget {dailySchedule.budget.max_load_points} pts</>
                    )}
                  </p>
                </div>
              )}

              {suggestedMilestones.length > 0 && (
                <SuggestedTasksPanel
                  userId={userId}
                  milestones={suggestedMilestones}
                  onChange={setSuggestedMilestones}
                  onApproved={() => {
                    fetchTasks(userId)
                    setGoalsRefreshKey(k => k + 1)
                  }}
                  aiFallback={suggestionsAiFallback}
                />
              )}

              {loadingTasks ? (
                <div className="flex items-center gap-2 py-6 text-sm text-[#6b7080]">
                  <Loader2 className="h-4 w-4 animate-spin" /> Routing tasks…
                </div>

              ) : !hasActiveTasks && energyLevel ? (
                /* Empty after CLCS routing — never leave the user with a blank list */
                <div className="rounded-lg border border-dashed border-[#e0d9f7] bg-[#faf7ff] px-6 py-8 text-center">
                  <p className="text-sm font-medium text-[#2d2d40]">
                    No tasks match your current energy ({energyScore}/10)
                  </p>
                  <p className="mt-1 text-xs text-[#6b7080]">
                    Your other tasks need a higher-energy window. Heavy parts may appear under Future tasks below.
                    {!energyLevel && energyScore > 0 && (
                      <span className="block mt-1 text-[#8127cf]">Click &quot;Start my day&quot; to confirm energy and apply routing.</span>
                    )}
                  </p>
                  <div className="mt-4 flex flex-wrap justify-center gap-2">
                    <button
                      onClick={handleRequestLightTasks}
                      className="flex items-center gap-1.5 rounded-lg bg-[#8127cf] px-4 py-2 text-xs font-semibold text-white hover:bg-[#6d1fb3]"
                    >
                      <Sparkles className="h-3.5 w-3.5" /> Ask co-pilot for ideas
                    </button>
                    <button
                      onClick={() => setShowModal(true)}
                      className="flex items-center gap-1.5 rounded-lg border border-[#d7d9e1] bg-white px-4 py-2 text-xs font-semibold text-[#4a4a58] hover:bg-[#f5f5f8]"
                    >
                      <Plus className="h-3.5 w-3.5" /> Add a light task
                    </button>
                  </div>
                </div>

              ) : !hasActiveTasks && tasks.length === 0 ? (
                /* No tasks at all, energy not yet set */
                <div className="flex flex-col items-center rounded-lg border border-dashed border-[#d0d3e0] bg-white px-6 py-10 text-center">
                  <div className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-[#e8e7ff] text-[#4648d4]">
                    <Plus className="h-5 w-5" />
                  </div>
                  <p className="text-sm font-medium text-[#191c1e]">No tasks yet</p>
                  <p className="mt-1 max-w-xs text-xs text-[#6b7080]">
                    Add your first task, or use Brain Dump to capture everything at once.
                  </p>
                  <div className="mt-4 flex gap-2">
                    <button onClick={() => setShowModal(true)} className="flex items-center gap-1.5 rounded-lg bg-[#4648d4] px-4 py-2 text-xs font-semibold text-white hover:bg-[#3f3dc6]">
                      <Plus className="h-3.5 w-3.5" /> Add first task
                    </button>
                    <button onClick={() => setShowBrainDump(true)} className="flex items-center gap-1.5 rounded-lg border border-[#e0d9f7] bg-[#f6f4ff] px-4 py-2 text-xs font-semibold text-[#8127cf] hover:bg-[#ebe8ff]">
                      <Brain className="h-3.5 w-3.5" /> Brain dump
                    </button>
                  </div>
                </div>

              ) : (
                <div className="space-y-3">
                  {milestoneGroups.filter(g => g.active.length > 0 || (g.blocked?.length ?? 0) > 0).map(g => (
                    <MilestoneTaskGroup
                      key={g.milestone_id}
                      group={g}
                      userId={userId!}
                      energyScore={energyScore}
                      energyLevel={energyLevel}
                      onCompleted={handleTaskCompleted}
                      onUpdated={handleTaskUpdated}
                      onDeleted={handleTaskDeleted}
                    />
                  ))}
                  {parentGroups.filter(g => g.active.length > 0).map(g => (
                    <ParentTaskGroup
                      key={g.parentId}
                      group={g}
                      userId={userId!}
                      energyScore={energyScore}
                      energyLevel={energyLevel}
                      onCompleted={handleTaskCompleted}
                      onUpdated={handleTaskUpdated}
                      onDeleted={handleTaskDeleted}
                    />
                  ))}
                  {standaloneTasks.map(t => (
                    <TaskCard key={t.id} task={t} userId={userId!} energyScore={energyScore} energyLevel={energyLevel} onCompleted={handleTaskCompleted} onUpdated={handleTaskUpdated} onDeleted={handleTaskDeleted} />
                  ))}
                </div>
              )}

              {/* Future tasks — blocked subtask parts + whole deferred tasks */}
              {futureTasks.length > 0 && (
                <details className="mt-4 rounded-lg border border-[#eceef4] bg-white">
                  <summary className="flex cursor-pointer items-center justify-between px-4 py-3 text-xs font-semibold text-[#6b7080] hover:text-[#191c1e] [&::-webkit-details-marker]:hidden">
                    <span>
                      Future tasks ({futureTasks.length}) — blocked until energy rises
                    </span>
                    <ChevronDown className="h-4 w-4 [[open]>&]:hidden" />
                    <ChevronUp className="hidden h-4 w-4 [[open]>&]:block" />
                  </summary>
                  <div className="space-y-3 border-t border-[#eceef4] p-3">
                    {parentGroups.filter(g => g.blocked.length > 0).map(g => (
                      <div key={`future-${g.parentId}`} className="rounded-lg border border-dashed border-[#e0d9f7] bg-[#faf7ff]">
                        <div className="flex items-center justify-between border-b border-[#e8e0f7] px-4 py-2">
                          <p className="truncate text-xs font-semibold text-[#8127cf]">{g.parentTitle}</p>
                          <span className="text-[10px] font-bold text-[#8127cf]">{g.progressPercent}% done</span>
                        </div>
                        <div className="space-y-px p-2">
                          {g.blocked.map(t => (
                            <TaskCard key={t.id} task={t} userId={userId!} energyScore={energyScore} energyLevel={energyLevel} isSubtask blocked onCompleted={handleTaskCompleted} onUpdated={handleTaskUpdated} onDeleted={handleTaskDeleted} />
                          ))}
                        </div>
                      </div>
                    ))}
                    {deferredWholeTasks.map(t => (
                      <TaskCard key={t.id} task={t} userId={userId!} energyScore={energyScore} energyLevel={energyLevel} blocked onCompleted={handleTaskCompleted} onUpdated={handleTaskUpdated} onDeleted={handleTaskDeleted} />
                    ))}
                  </div>
                  <p className="px-4 py-2 text-[10px] text-[#adb0bb]">
                    CLCS re-evaluates these when your energy rises — lighter subtask parts unlock automatically.
                  </p>
                </details>
              )}

              {/* Tasks Done */}
              {completedTasks.length > 0 && (
                <details className="mt-4 rounded-lg border border-[#e6f4ea] bg-[#f8fdf9]" open>
                  <summary className="flex cursor-pointer items-center justify-between px-4 py-3 text-xs font-semibold text-[#2d7a3a] hover:text-[#1f5c28] [&::-webkit-details-marker]:hidden">
                    <span className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4" />
                      Tasks done ({completedTasks.length})
                    </span>
                    <ChevronDown className="h-4 w-4 [[open]>&]:hidden" />
                    <ChevronUp className="hidden h-4 w-4 [[open]>&]:block" />
                  </summary>
                  <div className="divide-y divide-[#e6f4ea] border-t border-[#e6f4ea]">
                    {completedTasks.map(t => (
                      <CompletedTaskRow key={t.id} task={t} userId={userId!} onDeleted={handleTaskDeleted} />
                    ))}
                  </div>
                </details>
              )}
            </section>
          )}

        </div>
      </div>
    </AppShell>
  )
}
