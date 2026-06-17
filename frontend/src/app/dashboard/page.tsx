'use client'

import { useEffect, useState } from 'react'
import { Bot, Check, ChevronRight, Loader2, Plus, Sparkles, X } from 'lucide-react'
import AppShell from '@/components/AppShell'
import EnergyPanel from '@/components/EnergyPanel'
import { supabase } from '@/lib/supabase'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Task = {
  id: string
  title: string
  description?: string
  cognitive_load_score: number
  status: string
  priority?: string
  visible?: boolean
  reroute_reason?: string
}

const LOAD_LABELS: Record<number, { label: string; color: string; bg: string }> = {}
for (let i = 1; i <= 10; i++) {
  if (i <= 3)      LOAD_LABELS[i] = { label: 'Light',    color: '#2d7a3a', bg: '#e6f4ea' }
  else if (i <= 6) LOAD_LABELS[i] = { label: 'Moderate', color: '#7a5c00', bg: '#fdf3d0' }
  else             LOAD_LABELS[i] = { label: 'Deep Work', color: '#1f22f0', bg: '#e8e7ff' }
}

// ── Add Task Modal ────────────────────────────────────────────────────────────
function AddTaskModal({ userId, onClose, onCreated }: {
  userId: string
  onClose: () => void
  onCreated: (task: Task) => void
}) {
  const [title, setTitle]       = useState('')
  const [desc, setDesc]         = useState('')
  const [load, setLoad]         = useState(5)
  const [saving, setSaving]     = useState(false)
  const [err, setErr]           = useState('')

  const LOAD_PRESETS = [
    { value: 2,  label: 'Light',     hint: 'Admin, quick replies',          color: '#2d7a3a', bg: '#e6f4ea' },
    { value: 5,  label: 'Moderate',  hint: 'Meetings, regular work',         color: '#7a5c00', bg: '#fdf3d0' },
    { value: 8,  label: 'Deep Work', hint: 'Strategic thinking, writing',    color: '#1f22f0', bg: '#e8e7ff' },
  ]

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) { setErr('Title is required.'); return }
    setSaving(true)
    try {
      const res = await fetch(`${API}/tasks/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, title: title.trim(), description: desc.trim() || null, cognitive_load_score: load }),
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
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Write project introduction"
              className="w-full rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#4648d4]"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Description <span className="font-normal text-[#adb0bb]">(optional)</span></label>
            <textarea
              value={desc}
              onChange={e => setDesc(e.target.value)}
              placeholder="Any extra context…"
              rows={2}
              className="w-full resize-none rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#4648d4]"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Cognitive load</label>
            <div className="grid grid-cols-3 gap-2">
              {LOAD_PRESETS.map(p => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setLoad(p.value)}
                  className="rounded-lg border px-3 py-2.5 text-left transition"
                  style={load === p.value
                    ? { borderColor: p.color, backgroundColor: p.bg, color: p.color }
                    : { borderColor: '#d7d9e1', backgroundColor: 'white', color: '#4a4a58' }
                  }
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
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create task
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Task Card ─────────────────────────────────────────────────────────────────
function TaskCard({ task, userId, onCompleted }: { task: Task; userId: string; onCompleted: (id: string) => void }) {
  const [completing, setCompleting] = useState(false)
  const loadMeta = LOAD_LABELS[task.cognitive_load_score] ?? LOAD_LABELS[5]

  const complete = async () => {
    setCompleting(true)
    try {
      await fetch(`${API}/tasks/${task.id}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      })
      onCompleted(task.id)
    } finally {
      setCompleting(false)
    }
  }

  const dimmed = task.visible === false

  return (
    <div className={`flex items-start gap-3 rounded-lg border border-[#eceef4] bg-white px-4 py-3 transition ${dimmed ? 'opacity-40' : ''}`}>
      <button
        onClick={complete}
        disabled={completing}
        className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded border-2 border-[#d0d3e0] transition hover:border-[#4648d4]"
      >
        {completing && <Loader2 className="h-3 w-3 animate-spin text-[#4648d4]" />}
      </button>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[#191c1e]">{task.title}</p>
        {task.description && <p className="mt-0.5 text-xs text-[#6b7080] line-clamp-1">{task.description}</p>}
        {dimmed && task.reroute_reason && (
          <p className="mt-1 text-xs text-amber-600">{task.reroute_reason}</p>
        )}
      </div>
      <span className="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold" style={{ backgroundColor: loadMeta.bg, color: loadMeta.color }}>
        {loadMeta.label}
      </span>
    </div>
  )
}

// ── Right Rail ────────────────────────────────────────────────────────────────
function RightRail({ energyLevel }: { energyLevel: string }) {
  const message = energyLevel === 'high'
    ? "You're in High Energy mode — deep work tasks are prioritized."
    : energyLevel === 'balanced'
    ? "Balanced mode. Great for meetings and regular tasks."
    : energyLevel === 'low'
    ? "Low energy. I've surfaced light tasks so you can still make progress."
    : "Set your energy level to activate task routing."

  return (
    <aside className="hidden border-l border-[#eceef4] bg-white px-5 py-6 2xl:flex 2xl:flex-col gap-5">
      <div className="flex items-center gap-3">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#f0e5fb] text-[#8127cf]">
          <Bot className="h-4 w-4" />
        </div>
        <div>
          <p className="text-sm font-bold text-[#191c1e]">AI Co-Pilot</p>
          <p className="text-xs text-[#6b7080]">{energyLevel ? `${energyLevel} energy active` : 'Waiting for check-in'}</p>
        </div>
      </div>

      <div className="flex gap-3">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[#8127cf]" />
        <p className="text-sm leading-6 text-[#2d2d40]">{message}</p>
      </div>

      <div className="mt-auto rounded-lg border border-dashed border-[#d0d3e0] px-4 py-3 text-center text-xs text-[#adb0bb]">
        Full co-pilot chat — coming soon
      </div>
    </aside>
  )
}

// ── Dashboard Page ────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [userId, setUserId]           = useState<string | null>(null)
  const [energyLevel, setEnergy]      = useState('')
  const [tasks, setTasks]             = useState<Task[]>([])
  const [loadingTasks, setLoadingTasks] = useState(false)
  const [showModal, setShowModal]     = useState(false)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const uid = data.user?.id ?? null
      setUserId(uid)
      if (uid) fetchTasks(uid)
    })
  }, [])

  const fetchTasks = async (uid: string) => {
    setLoadingTasks(true)
    try {
      const res = await fetch(`${API}/tasks/routed?user_id=${uid}`)
      const data = await res.json()
      setTasks(data.tasks ?? [])
    } catch {
      // silently fail — tasks stay empty
    } finally {
      setLoadingTasks(false)
    }
  }

  const handleEnergyConfirmed = (level: string) => {
    setEnergy(level)
    if (userId) fetchTasks(userId) // re-fetch routed tasks after energy is set
  }

  const handleTaskCreated = (task: Task) => {
    setTasks(prev => [task, ...prev])
    if (userId) fetchTasks(userId)
  }

  const handleTaskCompleted = (id: string) => {
    setTasks(prev => prev.filter(t => t.id !== id))
  }

  const visibleTasks  = tasks.filter(t => t.visible !== false)
  const deferredTasks = tasks.filter(t => t.visible === false)

  return (
    <AppShell active="focus" rightRail={<RightRail energyLevel={energyLevel} />}>
      {showModal && userId && (
        <AddTaskModal
          userId={userId}
          onClose={() => setShowModal(false)}
          onCreated={handleTaskCreated}
        />
      )}

      <div className="min-h-screen bg-[#f8f9fb] px-5 py-7 md:px-10">
        <div className="mx-auto max-w-2xl space-y-7">

          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold text-[#191c1e]">Dashboard</h1>
            <p className="mt-0.5 text-sm text-[#6b7080]">Let's calibrate your day.</p>
          </div>

          {/* Energy check-in */}
          <section>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#adb0bb]">Morning check-in</p>
            <EnergyPanel onConfirmed={handleEnergyConfirmed} />
          </section>

          {/* Tasks */}
          <section>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-[#adb0bb]">Tasks</p>
                {energyLevel && (
                  <p className="mt-0.5 text-xs text-[#6b7080]">
                    Showing tasks for <span className="font-semibold text-[#4648d4]">{energyLevel}</span> energy
                  </p>
                )}
              </div>
              <button
                onClick={() => setShowModal(true)}
                className="flex items-center gap-1.5 rounded-lg border border-[#d7d9e1] bg-white px-3 py-1.5 text-xs font-semibold text-[#4a4a58] shadow-sm hover:bg-[#f5f5f8]"
              >
                <Plus className="h-3.5 w-3.5" />
                Add task
              </button>
            </div>

            {loadingTasks ? (
              <div className="flex items-center gap-2 py-6 text-sm text-[#6b7080]">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading tasks…
              </div>
            ) : visibleTasks.length === 0 ? (
              <div className="flex flex-col items-center rounded-lg border border-dashed border-[#d0d3e0] bg-white px-6 py-10 text-center">
                <div className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-[#e8e7ff] text-[#4648d4]">
                  <Plus className="h-5 w-5" />
                </div>
                <p className="text-sm font-medium text-[#191c1e]">No tasks yet</p>
                <p className="mt-1 max-w-xs text-xs text-[#6b7080]">
                  {energyLevel
                    ? `Add a task — Freeside will route it for your ${energyLevel} energy.`
                    : 'Add your first task to get started.'}
                </p>
                <button
                  onClick={() => setShowModal(true)}
                  className="mt-4 flex items-center gap-1.5 rounded-lg bg-[#4648d4] px-4 py-2 text-xs font-semibold text-white hover:bg-[#3f3dc6]"
                >
                  <Plus className="h-3.5 w-3.5" /> Add first task
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {visibleTasks.map(t => (
                  <TaskCard key={t.id} task={t} userId={userId!} onCompleted={handleTaskCompleted} />
                ))}
              </div>
            )}

            {/* Deferred tasks */}
            {deferredTasks.length > 0 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-xs font-semibold text-[#adb0bb] hover:text-[#6b7080]">
                  {deferredTasks.length} task{deferredTasks.length !== 1 ? 's' : ''} deferred for your current energy
                </summary>
                <div className="mt-2 space-y-2">
                  {deferredTasks.map(t => (
                    <TaskCard key={t.id} task={t} userId={userId!} onCompleted={handleTaskCompleted} />
                  ))}
                </div>
              </details>
            )}
          </section>

        </div>
      </div>
    </AppShell>
  )
}
