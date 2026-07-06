'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  Calendar, CheckCircle2, ChevronDown, ChevronUp, Loader2, Plus, Sparkles, Target, X,
} from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type GoalCategory = 'work' | 'personal' | 'health' | 'learning'
type GoalTimeframe = '1_month' | '3_months' | '6_months'

type Milestone = {
  title: string
  cognitive_load_score: number
  estimated_minutes?: number
  reasoning?: string
  scheduled_date?: string
  scheduled_capacity?: number
  status?: string
  id?: string
  is_future?: boolean
  progress_percent?: number
  tasks?: { id: string; title: string; status: string; step_order?: number; estimated_minutes?: number }[]
}

type Goal = {
  id: string
  title: string
  category?: string
  timeframe?: string
  progress_percent: number
  milestones: Milestone[]
}

type LandscapeDay = {
  date: string
  weekday: string
  predicted_capacity: number
  is_today?: boolean
}

const CATEGORY_LABELS: Record<GoalCategory, string> = {
  work: 'Work',
  personal: 'Personal',
  health: 'Health',
  learning: 'Learning',
}

const TIMEFRAME_LABELS: Record<GoalTimeframe, string> = {
  '1_month': '1 month',
  '3_months': '3 months',
  '6_months': '6 months',
}

const LOAD_META: Record<number, { label: string; color: string; bg: string }> = {}
for (let i = 1; i <= 10; i++) {
  if (i <= 3)       LOAD_META[i] = { label: 'Light',    color: '#2d7a3a', bg: '#e6f4ea' }
  else if (i <= 6)  LOAD_META[i] = { label: 'Moderate', color: '#7a5c00', bg: '#fdf3d0' }
  else              LOAD_META[i] = { label: 'Deep Work', color: '#1f22f0', bg: '#e8e7ff' }
}

function formatScheduleDate(iso: string | undefined): string {
  if (!iso) return 'Unscheduled'
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`)
  const today = new Date()
  today.setHours(12, 0, 0, 0)
  const diff = Math.round((d.getTime() - today.getTime()) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff > 1 && diff < 7) return d.toLocaleDateString(undefined, { weekday: 'short' })
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function CapacityStrip({ landscape }: { landscape: LandscapeDay[] }) {
  const days = landscape.slice(0, 7)
  if (!days.length) return null
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-[#adb0bb]">
        Next 7 days — predicted capacity
      </p>
      <div className="flex items-end gap-1">
        {days.map(day => (
          <div key={day.date} className="flex flex-1 flex-col items-center">
            <div
              className="mb-1 w-full max-w-[28px] rounded-sm"
              style={{
                height: `${Math.max(8, day.predicted_capacity * 3)}px`,
                background: day.is_today ? '#4648d4' : '#c5c8e8',
              }}
              title={`${day.weekday}: ${day.predicted_capacity}/10`}
            />
            <p className="text-[9px] text-[#6b7080]">{day.weekday.slice(0, 3)}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function GoalCard({
  goal,
  expanded,
  onToggle,
  onPlan,
  planning,
}: {
  goal: Goal
  expanded: boolean
  onToggle: () => void
  onPlan: () => void
  planning: boolean
}) {
  const done = goal.milestones.filter(m => m.status === 'completed').length
  const total = goal.milestones.length
  const pct = goal.progress_percent ?? (total ? Math.round(done / total * 100) : 0)
  const taskDone = goal.milestones.reduce(
    (n, m) => n + (m.tasks?.filter(t => t.status === 'completed').length ?? 0),
    0,
  )
  const taskTotal = goal.milestones.reduce((n, m) => n + (m.tasks?.length ?? 0), 0)

  return (
    <div className="rounded-lg border border-[#eceef4] bg-white shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-[#fafbfc]"
      >
        <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#e8e7ff] text-[#4648d4]">
          <Target className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-[#191c1e]">{goal.title}</p>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#eceef4]">
              <div
                className="h-full rounded-full bg-[#4648d4] transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-[#4648d4]">{pct}%</span>
          </div>
          <p className="mt-1 text-xs text-[#6b7080]">
            {total
              ? `${done}/${total} milestones${taskTotal ? ` · ${taskDone}/${taskTotal} tasks` : ''} · ${goal.category ?? 'work'}`
              : 'No milestones planned yet'}
          </p>
        </div>
        {expanded ? (
          <ChevronUp className="mt-1 h-4 w-4 shrink-0 text-[#6b7080]" />
        ) : (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-[#6b7080]" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-[#eceef4] px-4 py-3">
          {total === 0 ? (
            <div className="text-center py-2">
              <p className="text-xs text-[#6b7080] mb-3">
                Break this goal into substantive milestones and spread them across your best days.
              </p>
              <button
                type="button"
                onClick={onPlan}
                disabled={planning}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#4648d4] px-4 py-2 text-xs font-semibold text-white hover:bg-[#3f3dc6] disabled:opacity-60"
              >
                {planning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                Plan milestones
              </button>
            </div>
          ) : (
            <ol className="space-y-2">
              {goal.milestones.map((m, i) => {
                const load = m.cognitive_load_score ?? 5
                const meta = LOAD_META[load] ?? LOAD_META[5]
                const completed = m.status === 'completed'
                return (
                  <li
                    key={m.id ?? i}
                    className={`flex items-start gap-2 rounded-md px-2 py-1.5 ${completed ? 'opacity-60' : ''}`}
                  >
                    {completed ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#2d7a3a]" />
                    ) : (
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-[#d0d3e0] text-[10px] font-bold text-[#6b7080]">
                        {i + 1}
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className={`text-xs font-medium ${completed ? 'line-through text-[#6b7080]' : 'text-[#191c1e]'}`}>
                        {m.title}
                      </p>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                          style={{ color: meta.color, background: meta.bg }}
                        >
                          {meta.label} · {load}/10
                        </span>
                        {m.estimated_minutes && (
                          <span className="text-[10px] text-[#6b7080]">~{m.estimated_minutes} min</span>
                        )}
                        <span className="flex items-center gap-0.5 text-[10px] text-[#8127cf]">
                          <Calendar className="h-3 w-3" />
                          {formatScheduleDate(m.scheduled_date)}
                          {m.is_future && ' · upcoming'}
                        </span>
                        {m.progress_percent != null && m.progress_percent > 0 && (
                          <span className="text-[10px] font-semibold text-[#4648d4]">{m.progress_percent}%</span>
                        )}
                      </div>
                      {m.tasks && m.tasks.length > 0 && (
                        <ul className="mt-1.5 space-y-0.5 border-l-2 border-[#eceef4] pl-2">
                          {m.tasks.map((t, ti) => (
                            <li key={t.id ?? ti} className="flex items-center gap-1.5 text-[10px] text-[#6b7080]">
                              {t.status === 'completed' ? (
                                <CheckCircle2 className="h-3 w-3 shrink-0 text-[#2d7a3a]" />
                              ) : (
                                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#d0d3e0]" />
                              )}
                              <span className={t.status === 'completed' ? 'line-through' : ''}>{t.title}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      )}
    </div>
  )
}

function PlanGoalModal({
  userId,
  goal,
  onClose,
  onPlanned,
}: {
  userId: string
  goal?: Goal | null
  onClose: () => void
  onPlanned: () => void
}) {
  const isNew = !goal
  const [title, setTitle] = useState(goal?.title ?? '')
  const [category, setCategory] = useState<GoalCategory>((goal?.category as GoalCategory) ?? 'work')
  const [timeframe, setTimeframe] = useState<GoalTimeframe>((goal?.timeframe as GoalTimeframe) ?? '3_months')
  const [step, setStep] = useState<'form' | 'review'>('form')
  const [goalId, setGoalId] = useState(goal?.id ?? '')
  const [milestones, setMilestones] = useState<Milestone[]>([])
  const [landscape, setLandscape] = useState<LandscapeDay[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [aiFallback, setAiFallback] = useState(false)

  const decompose = async () => {
    setLoading(true)
    setErr('')
    try {
      let gid = goalId
      if (isNew) {
        const createRes = await fetch(`${API}/goals/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId, title: title.trim(), category, timeframe }),
        })
        if (!createRes.ok) {
          const body = await createRes.json().catch(() => ({}))
          throw new Error(body.detail ?? 'Could not create goal')
        }
        const created = await createRes.json()
        gid = created.id
        setGoalId(gid)
      }

      const res = await fetch(`${API}/goals/${gid}/decompose?user_id=${userId}`, { method: 'POST' })
      if (!res.ok) throw new Error('Decomposition failed')
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Decomposition failed')
      setMilestones(data.milestones ?? [])
      setLandscape(data.landscape ?? [])
      setAiFallback(!!data.ai_fallback)
      setStep('review')
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Planning failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const confirm = async () => {
    setSaving(true)
    setErr('')
    try {
      const res = await fetch(`${API}/goals/${goalId}/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, milestones }),
      })
      if (!res.ok) throw new Error('Could not save milestones')
      onPlanned()
      onClose()
    } catch {
      setErr('Failed to save plan.')
    } finally {
      setSaving(false)
    }
  }

  const removeMilestone = (idx: number) => {
    setMilestones(prev => prev.filter((_, i) => i !== idx))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-[#eceef4] bg-white shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-[#eceef4] bg-white px-5 py-4">
          <h2 className="text-sm font-bold text-[#191c1e]">
            {step === 'form' ? (isNew ? 'Add goal' : 'Plan milestones') : 'Review milestone schedule'}
          </h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-[#6b7080] hover:bg-[#f4f4f8]">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {step === 'form' ? (
            <>
              {!isNew && (
                <p className="text-xs text-[#6b7080]">
                  AI will propose 4–6 substantive milestones (~1+ hour each) and schedule them across your best upcoming days.
                </p>
              )}
              {isNew && (
                <>
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Goal *</label>
                    <input
                      value={title}
                      onChange={e => setTitle(e.target.value)}
                      placeholder="Launch my side project"
                      className="w-full rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm outline-none focus:border-[#4648d4]"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Category</label>
                      <select
                        value={category}
                        onChange={e => setCategory(e.target.value as GoalCategory)}
                        className="w-full rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm"
                      >
                        {(Object.keys(CATEGORY_LABELS) as GoalCategory[]).map(c => (
                          <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-semibold text-[#6b7080]">Timeframe</label>
                      <select
                        value={timeframe}
                        onChange={e => setTimeframe(e.target.value as GoalTimeframe)}
                        className="w-full rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm"
                      >
                        {(Object.keys(TIMEFRAME_LABELS) as GoalTimeframe[]).map(t => (
                          <option key={t} value={t}>{TIMEFRAME_LABELS[t]}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </>
              )}
              <button
                type="button"
                onClick={decompose}
                disabled={loading || (isNew && !title.trim())}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] py-2.5 text-sm font-semibold text-white hover:bg-[#3f3dc6] disabled:opacity-60"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {loading ? 'Generating milestones…' : 'Generate milestone plan'}
              </button>
            </>
          ) : (
            <>
              {aiFallback && (
                <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  AI quota reached — using rule-based milestone templates. You can edit before confirming.
                </p>
              )}
              <p className="text-xs text-[#6b7080]">
                Each milestone is sized for real focused work. They surface on the day shown — not all at once in today&apos;s list.
              </p>
              <CapacityStrip landscape={landscape} />
              <ol className="space-y-2">
                {milestones.map((m, i) => {
                  const load = m.cognitive_load_score ?? 6
                  const meta = LOAD_META[load] ?? LOAD_META[6]
                  return (
                    <li key={i} className="rounded-lg border border-[#eceef4] px-3 py-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-[#191c1e]">{m.title}</p>
                          <div className="mt-1 flex flex-wrap gap-1.5">
                            <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold" style={{ color: meta.color, background: meta.bg }}>
                              {load}/10 · ~{m.estimated_minutes ?? 90} min
                            </span>
                            <span className="text-[10px] font-semibold text-[#8127cf]">
                              → {formatScheduleDate(m.scheduled_date)}
                              {m.scheduled_capacity != null && ` (cap ${m.scheduled_capacity}/10)`}
                            </span>
                          </div>
                          {m.reasoning && (
                            <p className="mt-0.5 text-[10px] text-[#6b7080]">{m.reasoning}</p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => removeMilestone(i)}
                          className="shrink-0 rounded p-1 text-[#6b7080] hover:bg-[#f4f4f8]"
                          aria-label="Remove milestone"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </li>
                  )
                })}
              </ol>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setStep('form')}
                  className="flex-1 rounded-lg border border-[#d7d9e1] py-2 text-xs font-semibold text-[#4a4a58] hover:bg-[#f5f5f8]"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={confirm}
                  disabled={saving || milestones.length === 0}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[#4648d4] py-2 text-xs font-semibold text-white hover:bg-[#3f3dc6] disabled:opacity-60"
                >
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                  Confirm schedule
                </button>
              </div>
            </>
          )}
          {err && <p className="text-xs text-red-600">{err}</p>}
        </div>
      </div>
    </div>
  )
}

type Props = {
  userId: string
  refreshKey?: number
  onGoalsChanged?: () => void
}

export default function GoalsPanel({ userId, refreshKey = 0, onGoalsChanged }: Props) {
  const [goals, setGoals] = useState<Goal[]>([])
  const [landscape, setLandscape] = useState<LandscapeDay[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [planGoal, setPlanGoal] = useState<Goal | null>(null)

  const fetchGoals = useCallback(async () => {
    setLoading(true)
    try {
      const [goalsRes, forecastRes] = await Promise.all([
        fetch(`${API}/goals/?user_id=${userId}`),
        fetch(`${API}/goals/forecast?user_id=${userId}&days=14`),
      ])
      if (goalsRes.ok) {
        const data = await goalsRes.json()
        const list: Goal[] = data.goals ?? []
        setGoals(list)
        setExpandedId(prev => prev ?? (list[0]?.id ?? null))
      }
      if (forecastRes.ok) {
        const data = await forecastRes.json()
        setLandscape(data.landscape ?? [])
      }
    } catch {
      // best-effort
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    if (userId) void fetchGoals()
  }, [userId, refreshKey, fetchGoals])

  const handlePlanned = () => {
    void fetchGoals()
    onGoalsChanged?.()
  }

  const openPlanExisting = (goal: Goal) => {
    setPlanGoal(goal)
    setShowModal(true)
  }

  if (loading && goals.length === 0) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-[#6b7080]">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading goals…
      </div>
    )
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-[#adb0bb]">Goals</p>
          <p className="mt-0.5 text-xs text-[#6b7080]">
            Milestones spread across your energy landscape — not dumped into today.
          </p>
        </div>
        {goals.length < 3 && (
          <button
            type="button"
            onClick={() => { setPlanGoal(null); setShowModal(true) }}
            className="flex items-center gap-1.5 rounded-lg border border-[#d7d9e1] bg-white px-3 py-1.5 text-xs font-semibold text-[#4a4a58] shadow-sm hover:bg-[#f5f5f8]"
          >
            <Plus className="h-3.5 w-3.5" /> Add goal
          </button>
        )}
      </div>

      {landscape.length > 0 && goals.some(g => g.milestones.length > 0) && (
        <div className="mb-4 rounded-lg border border-[#eceef4] bg-white px-4 py-3">
          <CapacityStrip landscape={landscape} />
        </div>
      )}

      {goals.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[#d0d3e0] bg-white px-6 py-8 text-center">
          <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-[#e8e7ff] text-[#4648d4]">
            <Target className="h-5 w-5" />
          </div>
          <p className="text-sm font-medium text-[#191c1e]">No goals yet</p>
          <p className="mt-1 text-xs text-[#6b7080]">
            Add a goal and AI will break it into substantive milestones scheduled across your best days.
          </p>
          <button
            type="button"
            onClick={() => { setPlanGoal(null); setShowModal(true) }}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#4648d4] px-4 py-2 text-xs font-semibold text-white hover:bg-[#3f3dc6]"
          >
            <Plus className="h-3.5 w-3.5" /> Add your first goal
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {goals.map(goal => (
            <GoalCard
              key={goal.id}
              goal={goal}
              expanded={expandedId === goal.id}
              onToggle={() => setExpandedId(expandedId === goal.id ? null : goal.id)}
              onPlan={() => openPlanExisting(goal)}
              planning={false}
            />
          ))}
        </div>
      )}

      {showModal && (
        <PlanGoalModal
          userId={userId}
          goal={planGoal}
          onClose={() => { setShowModal(false); setPlanGoal(null) }}
          onPlanned={handlePlanned}
        />
      )}
    </section>
  )
}
