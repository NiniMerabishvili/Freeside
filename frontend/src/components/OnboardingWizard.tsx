'use client'

import { useState, useEffect, Suspense } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  ArrowRight,
  Briefcase,
  Calendar,
  Check,
  ChevronDown,
  ChevronUp,
  GraduationCap,
  Lightbulb,
  Moon,
  Plus,
  Rocket,
  Sparkles,
  Sun,
  SunMedium,
  Trash2,
  User,
  Zap,
  AlertCircle,
  Bot,
  BookOpen,
  FileText,
  ListTodo,
  CheckSquare,
} from 'lucide-react'
import { supabase } from '@/lib/supabase'

// ─── Types ────────────────────────────────────────────────────────────────────

type Role = 'student' | 'professional' | 'entrepreneur' | 'other'
type PeakFocus = 'morning' | 'afternoon' | 'evening'
type WorkStyle = 'long_blocks' | 'short_sprints' | 'flexible'
type GoalCategory = 'work' | 'personal' | 'health' | 'learning'
type GoalTimeframe = '1_month' | '3_months' | '6_months'
type IntegrationType = 'clickup' | 'asana' | 'obsidian' | 'notes' | 'ai_agents'

interface Goal {
  title: string
  category: GoalCategory
  timeframe: GoalTimeframe
}

interface ProfileData {
  name: string
  role: Role | ''
  productive_day_description: string
}

interface WorkStyleData {
  peak_focus_time: PeakFocus | ''
  daily_work_hours: number | ''
  work_style: WorkStyle | ''
}

interface Integration {
  type: IntegrationType
  connected: boolean
  apiToken: string
  contextNotes: string
  workspaceName: string
}

// ─── Animation variants ────────────────────────────────────────────────────────

const slideVariants = {
  enter: (dir: number) => ({ x: dir > 0 ? 60 : -60, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir: number) => ({ x: dir < 0 ? 60 : -60, opacity: 0 }),
}

// ─── Small reusable components ─────────────────────────────────────────────────

function ChoiceButton({
  selected,
  onClick,
  children,
  id,
}: {
  selected: boolean
  onClick: () => void
  children: React.ReactNode
  id: string
}) {
  return (
    <button
      id={id}
      type="button"
      onClick={onClick}
      className={`flex items-center gap-3 rounded-lg border px-5 py-4 text-left text-base font-semibold transition-all ${
        selected
          ? 'border-[#4648d4] bg-[#ededfc] text-[#4648d4] shadow-[0_4px_14px_rgba(70,72,212,0.15)]'
          : 'border-[#d5d7e2] bg-white/70 text-[#464554] hover:border-[#4648d4]/50 hover:bg-white'
      }`}
    >
      {selected && <Check className="h-4 w-4 shrink-0 text-[#4648d4]" />}
      {children}
    </button>
  )
}

function StepProgress({ current, total }: { current: number; total: number }) {
  return (
    <div className="mb-10 flex items-center gap-3">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-1.5 flex-1 rounded-full transition-all duration-500 ${
            i < current ? 'bg-[#4648d4]' : i === current ? 'bg-[#a0a2e8]' : 'bg-[#dfe2e3]'
          }`}
        />
      ))}
      <span className="ml-2 whitespace-nowrap text-sm font-bold text-[#8183a0]">
        {current + 1} / {total}
      </span>
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mb-5 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <AlertCircle className="h-4 w-4 shrink-0" />
      {message}
    </div>
  )
}

// ─── Step 1 — Welcome & Identity ───────────────────────────────────────────────

function Step1({
  profile,
  setProfile,
  onNext,
  saving,
  error,
}: {
  profile: ProfileData
  setProfile: (p: ProfileData) => void
  onNext: () => void
  saving: boolean
  error: string
}) {
  const roles: { value: Role; label: string; icon: React.ElementType; desc: string }[] = [
    { value: 'student', label: 'Student', icon: GraduationCap, desc: 'Research, assignments, exams.' },
    { value: 'professional', label: 'Professional', icon: Briefcase, desc: 'Meetings, deep work blocks.' },
    { value: 'entrepreneur', label: 'Entrepreneur', icon: Rocket, desc: 'Dynamic, high-agency work.' },
    { value: 'other', label: 'Other', icon: User, desc: 'Anything that needs focus.' },
  ]

  const canContinue = profile.name.trim() && profile.role && profile.productive_day_description.trim()

  return (
    <div>
      <div className="mb-8 text-center">
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-xl bg-[#4648d4] text-white shadow-lg">
          <Sparkles className="h-7 w-7" />
        </div>
        <div className="text-label mb-3 text-[#4648d4]">Step 1 — Who are you?</div>
        <h1 className="font-serif text-4xl font-bold text-[#191c1e] md:text-5xl">
          Welcome. Let&apos;s understand<br className="hidden md:block" /> who you are.
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg leading-7 text-[#464554]">
          Before we build your first day, Freeside needs to know you. This takes 2 minutes.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Name */}
      <div className="mb-7">
        <label htmlFor="onboarding-name" className="text-label mb-2 block text-[#2f3040]">
          Your name
        </label>
        <input
          id="onboarding-name"
          type="text"
          autoFocus
          value={profile.name}
          onChange={(e) => setProfile({ ...profile, name: e.target.value })}
          placeholder="e.g. Nina"
          className="h-14 w-full rounded-lg border border-[#c7c4d7] bg-white/80 px-5 text-lg outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
        />
      </div>

      {/* Role */}
      <div className="mb-7">
        <div className="text-label mb-3 text-[#2f3040]">What best describes you?</div>
        <div className="grid gap-3 sm:grid-cols-2">
          {roles.map((r) => {
            const Icon = r.icon
            return (
              <button
                id={`role-${r.value}`}
                key={r.value}
                type="button"
                onClick={() => setProfile({ ...profile, role: r.value })}
                className={`flex items-center gap-4 rounded-lg border p-5 text-left transition-all ${
                  profile.role === r.value
                    ? 'border-[#4648d4] bg-[#ededfc] shadow-[0_4px_14px_rgba(70,72,212,0.15)]'
                    : 'border-[#d5d7e2] bg-white/70 hover:border-[#4648d4]/50 hover:bg-white'
                }`}
              >
                <div
                  className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${
                    profile.role === r.value ? 'bg-[#4648d4] text-white' : 'bg-[#eceef0] text-[#6b7080]'
                  }`}
                >
                  <Icon className="h-6 w-6" />
                </div>
                <div>
                  <div className="text-base font-bold text-[#191c1e]">{r.label}</div>
                  <div className="text-sm text-[#464554]">{r.desc}</div>
                </div>
                {profile.role === r.value && (
                  <Check className="ml-auto h-5 w-5 shrink-0 text-[#4648d4]" />
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Productive day */}
      <div className="mb-8">
        <label htmlFor="productive-day" className="text-label mb-2 flex items-center gap-2 text-[#2f3040]">
          What does a truly productive day look like for you?
          <Lightbulb className="h-4 w-4 text-[#8127cf]" />
        </label>
        <p className="mb-3 text-sm text-[#6b7080]">
          2–3 sentences is plenty. The AI co-pilot uses this to personalise every suggestion.
        </p>
        <textarea
          id="productive-day"
          value={profile.productive_day_description}
          onChange={(e) => setProfile({ ...profile, productive_day_description: e.target.value })}
          placeholder="e.g. I start with 2 hours of deep writing, then take calls after lunch. I feel accomplished when I ship one meaningful thing."
          rows={4}
          className="w-full resize-none rounded-lg border border-[#c7c4d7] bg-white/80 p-5 text-base leading-7 outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
        />
      </div>

      <div className="flex justify-end">
        <button
          id="step1-continue"
          type="button"
          disabled={!canContinue || saving}
          onClick={onNext}
          className="flex h-14 w-full max-w-sm items-center justify-center gap-3 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving…' : <>Continue <ArrowRight className="h-5 w-5" /></>}
        </button>
      </div>
    </div>
  )
}

// ─── Step 2 — Goals ────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<GoalCategory, string> = {
  work: '💼 Work',
  personal: '🌱 Personal',
  health: '🏃 Health',
  learning: '📚 Learning',
}
const TIMEFRAME_LABELS: Record<GoalTimeframe, string> = {
  '1_month': 'This month',
  '3_months': '3 months',
  '6_months': '6 months',
}

function Step2({
  goals,
  setGoals,
  onNext,
  saving,
  error,
}: {
  goals: Goal[]
  setGoals: (g: Goal[]) => void
  onNext: () => void
  saving: boolean
  error: string
}) {
  const [draft, setDraft] = useState<Goal>({ title: '', category: 'work', timeframe: '1_month' })
  const canAdd = draft.title.trim() && goals.length < 3
  const canContinue = goals.length >= 1

  const addGoal = () => {
    if (!canAdd) return
    setGoals([...goals, { ...draft }])
    setDraft({ title: '', category: 'work', timeframe: '1_month' })
  }

  const removeGoal = (i: number) => {
    setGoals(goals.filter((_, idx) => idx !== i))
  }

  return (
    <div>
      <div className="mb-8 text-center">
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-xl bg-[#8127cf] text-white shadow-lg">
          <Zap className="h-7 w-7" />
        </div>
        <div className="text-label mb-3 text-[#8127cf]">Step 2 — Your Goals</div>
        <h1 className="font-serif text-4xl font-bold text-[#191c1e] md:text-5xl">
          What do you want to achieve?
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg leading-7 text-[#464554]">
          Add 1–3 goals. Every AI decision — routing, co-pilot advice, proactive nudges — anchors to these.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Existing goals */}
      {goals.length > 0 && (
        <div className="mb-6 space-y-3">
          {goals.map((g, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-lg border border-[#4648d4]/30 bg-[#ededfc] px-5 py-4"
            >
              <div>
                <div className="font-bold text-[#191c1e]">{g.title}</div>
                <div className="mt-0.5 text-sm text-[#6b7080]">
                  {CATEGORY_LABELS[g.category]} · {TIMEFRAME_LABELS[g.timeframe]}
                </div>
              </div>
              <button
                id={`remove-goal-${i}`}
                type="button"
                onClick={() => removeGoal(i)}
                className="ml-4 text-[#ba1a1a] hover:text-[#911414] transition"
                aria-label="Remove goal"
              >
                <Trash2 className="h-5 w-5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add goal form */}
      {goals.length < 3 && (
        <div className="mb-6 rounded-lg border border-[#dfe2e8] bg-white/80 p-6">
          <div className="text-label mb-4 text-[#2f3040]">
            {goals.length === 0 ? 'Add your first goal' : 'Add another goal'}
          </div>
          <input
            id="goal-title"
            type="text"
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && addGoal()}
            placeholder='e.g. "Launch my side project"'
            className="mb-4 h-12 w-full rounded-lg border border-[#c7c4d7] bg-white px-4 text-base outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
          />
          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="text-label mb-2 text-[#6b7080]">Category</div>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(CATEGORY_LABELS) as GoalCategory[]).map((c) => (
                  <button
                    id={`cat-${c}`}
                    key={c}
                    type="button"
                    onClick={() => setDraft({ ...draft, category: c })}
                    className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
                      draft.category === c
                        ? 'border-[#4648d4] bg-[#4648d4] text-white'
                        : 'border-[#d5d7e2] bg-white text-[#464554] hover:border-[#4648d4]/50'
                    }`}
                  >
                    {CATEGORY_LABELS[c]}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-label mb-2 text-[#6b7080]">Timeframe</div>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(TIMEFRAME_LABELS) as GoalTimeframe[]).map((t) => (
                  <button
                    id={`tf-${t}`}
                    key={t}
                    type="button"
                    onClick={() => setDraft({ ...draft, timeframe: t })}
                    className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
                      draft.timeframe === t
                        ? 'border-[#4648d4] bg-[#4648d4] text-white'
                        : 'border-[#d5d7e2] bg-white text-[#464554] hover:border-[#4648d4]/50'
                    }`}
                  >
                    {TIMEFRAME_LABELS[t]}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <button
            id="add-goal-btn"
            type="button"
            onClick={addGoal}
            disabled={!canAdd}
            className="flex h-11 items-center gap-2 rounded-lg border border-[#4648d4] px-5 text-sm font-bold text-[#4648d4] transition hover:bg-[#ededfc] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4" /> Add Goal
          </button>
        </div>
      )}

      {goals.length === 3 && (
        <div className="mb-6 rounded-lg border border-[#c0c1ff] bg-[#f3f3ff] px-5 py-3 text-sm font-semibold text-[#4648d4]">
          ✓ You&apos;ve added 3 goals — that&apos;s the maximum. Great focus!
        </div>
      )}

      <div className="flex justify-between gap-4 border-t border-[#dfe2e8] pt-6">
        <p className="text-sm text-[#8183a0] self-center">
          {goals.length === 0 ? 'Add at least 1 goal to continue.' : `${goals.length} goal${goals.length > 1 ? 's' : ''} added.`}
        </p>
        <button
          id="step2-continue"
          type="button"
          disabled={!canContinue || saving}
          onClick={onNext}
          className="flex h-14 w-full max-w-sm items-center justify-center gap-3 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving…' : <>Continue <ArrowRight className="h-5 w-5" /></>}
        </button>
      </div>
    </div>
  )
}

// ─── Step 3 — Work Style ───────────────────────────────────────────────────────

function Step3({
  workStyle,
  setWorkStyle,
  onNext,
  saving,
  error,
}: {
  workStyle: WorkStyleData
  setWorkStyle: (w: WorkStyleData) => void
  onNext: () => void
  saving: boolean
  error: string
}) {
  const peakOptions: { value: PeakFocus; label: string; icon: React.ElementType }[] = [
    { value: 'morning', label: '🌅 Morning person', icon: Sun },
    { value: 'afternoon', label: '☀️ Afternoon', icon: SunMedium },
    { value: 'evening', label: '🌙 Night owl', icon: Moon },
  ]
  const hoursOptions: { value: number; label: string }[] = [
    { value: 3, label: 'Less than 4h' },
    { value: 5, label: '4–6 hours' },
    { value: 7, label: '6–8 hours' },
    { value: 9, label: '8h+' },
  ]
  const styleOptions: { value: WorkStyle; label: string; desc: string }[] = [
    { value: 'long_blocks', label: 'Long deep-focus blocks', desc: 'Uninterrupted 90–120 min sessions.' },
    { value: 'short_sprints', label: 'Short sprints with breaks', desc: 'Pomodoro-style 25–45 min cycles.' },
    { value: 'flexible', label: 'Flexible, depends on the day', desc: 'Context-driven, adaptive.' },
  ]

  const canContinue = workStyle.peak_focus_time && workStyle.daily_work_hours !== '' && workStyle.work_style

  return (
    <div>
      <div className="mb-8 text-center">
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-xl bg-[#4648d4] text-white shadow-lg">
          <Sun className="h-7 w-7" />
        </div>
        <div className="text-label mb-3 text-[#4648d4]">Step 3 — Your Work Style</div>
        <h1 className="font-serif text-4xl font-bold text-[#191c1e] md:text-5xl">
          How do you work best?
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg leading-7 text-[#464554]">
          Three quick questions. The algorithm uses these to boost the right tasks during your peak hours.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Peak focus */}
      <div className="mb-7">
        <div className="text-label mb-3 text-[#2f3040]">When do you feel most mentally sharp?</div>
        <div className="grid gap-3 sm:grid-cols-3">
          {peakOptions.map((o) => (
            <ChoiceButton
              id={`peak-${o.value}`}
              key={o.value}
              selected={workStyle.peak_focus_time === o.value}
              onClick={() => setWorkStyle({ ...workStyle, peak_focus_time: o.value })}
            >
              {o.label}
            </ChoiceButton>
          ))}
        </div>
      </div>

      {/* Hours */}
      <div className="mb-7">
        <div className="text-label mb-3 text-[#2f3040]">How many hours do you realistically work per day?</div>
        <div className="grid gap-3 sm:grid-cols-4">
          {hoursOptions.map((o) => (
            <ChoiceButton
              id={`hours-${o.value}`}
              key={o.value}
              selected={workStyle.daily_work_hours === o.value}
              onClick={() => setWorkStyle({ ...workStyle, daily_work_hours: o.value })}
            >
              {o.label}
            </ChoiceButton>
          ))}
        </div>
      </div>

      {/* Work style */}
      <div className="mb-8">
        <div className="text-label mb-3 text-[#2f3040]">How do you prefer to work?</div>
        <div className="grid gap-3">
          {styleOptions.map((o) => (
            <button
              id={`style-${o.value}`}
              key={o.value}
              type="button"
              onClick={() => setWorkStyle({ ...workStyle, work_style: o.value })}
              className={`flex items-start gap-4 rounded-lg border p-5 text-left transition-all ${
                workStyle.work_style === o.value
                  ? 'border-[#4648d4] bg-[#ededfc] shadow-[0_4px_14px_rgba(70,72,212,0.15)]'
                  : 'border-[#d5d7e2] bg-white/70 hover:border-[#4648d4]/50 hover:bg-white'
              }`}
            >
              {workStyle.work_style === o.value && (
                <Check className="mt-0.5 h-5 w-5 shrink-0 text-[#4648d4]" />
              )}
              <div>
                <div className="font-bold text-[#191c1e]">{o.label}</div>
                <div className="mt-0.5 text-sm text-[#464554]">{o.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex justify-end border-t border-[#dfe2e8] pt-6">
        <button
          id="step3-continue"
          type="button"
          disabled={!canContinue || saving}
          onClick={onNext}
          className="flex h-14 w-full max-w-sm items-center justify-center gap-3 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving…' : <>Continue <ArrowRight className="h-5 w-5" /></>}
        </button>
      </div>
    </div>
  )
}

// ─── Step 4 — Connect Google Calendar ─────────────────────────────────────────

function Step4({
  onConnect,
  onSkip,
  loading,
}: {
  onConnect: () => void
  onSkip: () => void
  loading: boolean
}) {
  return (
    <div className="text-center">
      <div className="mx-auto mb-6 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-[#4648d4] to-[#8127cf] text-white shadow-xl">
        <Calendar className="h-8 w-8" />
      </div>
      <div className="text-label mb-3 text-[#4648d4]">Step 4 — Connect Your Calendar</div>
      <h1 className="font-serif text-4xl font-bold text-[#191c1e] md:text-5xl">
        Freeside&apos;s superpower.
      </h1>
      <p className="mx-auto mt-5 max-w-xl text-lg leading-7 text-[#464554]">
        Connect your Google Calendar and we&apos;ll analyze your schedule each morning to suggest your energy level — so you never have to guess.
      </p>

      <div className="mx-auto mt-10 max-w-lg rounded-lg border border-[#e0e2ee] bg-white/80 p-6 text-left">
        <div className="text-label mb-4 text-[#2f3040]">Here&apos;s what happens</div>
        <ul className="space-y-3">
          {[
            'We read your calendar (read-only, never write)',
            'Claude AI infers your cognitive energy based on your schedule',
            'You see the suggestion every morning and confirm in 5 seconds',
            'Tasks are automatically routed to match your confirmed energy',
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-3 text-sm text-[#464554]">
              <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[#ededfc] text-xs font-bold text-[#4648d4]">
                {i + 1}
              </span>
              {item}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-10 space-y-4">
        <button
          id="connect-calendar-btn"
          type="button"
          onClick={onConnect}
          disabled={loading}
          className="flex h-16 w-full items-center justify-center gap-4 rounded-lg bg-[#4648d4] text-lg font-bold text-white shadow-xl transition hover:bg-[#3a3cc0] disabled:opacity-60"
        >
          <Calendar className="h-6 w-6" />
          {loading ? 'Redirecting to Google…' : 'Connect Google Calendar →'}
        </button>
        <button
          id="skip-calendar-btn"
          type="button"
          onClick={onSkip}
          className="block w-full text-center text-base text-[#6b7080] underline underline-offset-2 hover:text-[#464554] transition"
        >
          Skip for now — I&apos;ll enter my energy manually
        </button>
      </div>
    </div>
  )
}

// ─── Step 5 — Integrations ─────────────────────────────────────────────────────

const INTEGRATION_DEFS: {
  type: IntegrationType
  label: string
  tagline: string
  icon: React.ElementType
  color: string
  inputType: 'token' | 'text'
  tokenLabel?: string
  tokenPlaceholder?: string
  notesLabel?: string
  notesPlaceholder?: string
}[] = [
  {
    type: 'clickup',
    label: 'ClickUp',
    tagline: 'Pull your tasks & projects. AI sees your real workload.',
    icon: ListTodo,
    color: '#7B68EE',
    inputType: 'token',
    tokenLabel: 'Personal API Token',
    tokenPlaceholder: 'pk_xxxxxxxxxxxxxxxx',
    notesLabel: 'Workspace / Space name (optional)',
    notesPlaceholder: 'e.g. My Startup Workspace',
  },
  {
    type: 'asana',
    label: 'Asana',
    tagline: 'Sync your Asana tasks so the AI knows your project priorities.',
    icon: CheckSquare,
    color: '#F06A6A',
    inputType: 'token',
    tokenLabel: 'Personal Access Token',
    tokenPlaceholder: '1/xxxxxxxxxxxxxxxx',
    notesLabel: 'Workspace name (optional)',
    notesPlaceholder: 'e.g. My Team Workspace',
  },
  {
    type: 'obsidian',
    label: 'Obsidian',
    tagline: 'Describe your vault so the AI understands your knowledge system.',
    icon: BookOpen,
    color: '#7C3AED',
    inputType: 'text',
    notesLabel: 'Describe your Obsidian vault',
    notesPlaceholder: 'e.g. I use Obsidian to track my research notes, daily journals, and project plans. My main areas are software development, philosophy, and personal finance.',
  },
  {
    type: 'notes',
    label: 'Notes & Context',
    tagline: 'Paste any notes, context, or recurring to-dos the AI should always know.',
    icon: FileText,
    color: '#0EA5E9',
    inputType: 'text',
    notesLabel: 'Your notes or context',
    notesPlaceholder: 'e.g. I maintain a weekly review every Sunday. My recurring priorities are: client deliverables by Thursday, team sync on Mondays. I struggle with context-switching.',
  },
  {
    type: 'ai_agents',
    label: 'AI Agents',
    tagline: 'Tell Freeside about your existing AI agents so it can coordinate with them.',
    icon: Bot,
    color: '#10B981',
    inputType: 'text',
    notesLabel: 'Describe your AI agents',
    notesPlaceholder: 'e.g. I have a research agent that summarises papers, a writing agent for blog drafts, and a code review agent in VS Code. I use them mostly in the morning.',
  },
]

function IntegrationCard({
  def,
  integration,
  onChange,
}: {
  def: typeof INTEGRATION_DEFS[0]
  integration: Integration
  onChange: (updated: Integration) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const Icon = def.icon

  const handleConnect = () => {
    const hasInput =
      def.inputType === 'token'
        ? integration.apiToken.trim()
        : integration.contextNotes.trim()

    if (!expanded) {
      setExpanded(true)
      return
    }
    if (hasInput) {
      onChange({ ...integration, connected: true })
      setExpanded(false)
    }
  }

  const handleDisconnect = () => {
    onChange({ ...integration, connected: false, apiToken: '', contextNotes: '', workspaceName: '' })
    setExpanded(false)
  }

  return (
    <div
      className={`rounded-xl border transition-all ${
        integration.connected
          ? 'border-green-200 bg-green-50/60'
          : 'border-[#dfe2e8] bg-white/80'
      }`}
    >
      {/* Card header */}
      <div className="flex items-center gap-4 p-5">
        <div
          className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-white shadow-sm"
          style={{ backgroundColor: def.color }}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-bold text-[#191c1e]">{def.label}</div>
          <div className="text-sm text-[#6b7080] leading-snug">{def.tagline}</div>
        </div>
        <div className="ml-2 flex shrink-0 gap-2">
          {integration.connected ? (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1.5 text-xs font-bold text-green-700">
                <Check className="h-3 w-3" /> Connected
              </span>
              <button
                type="button"
                onClick={handleDisconnect}
                className="rounded-full border border-[#dfe2e8] px-3 py-1.5 text-xs font-semibold text-[#6b7080] hover:border-red-300 hover:text-red-600 transition"
              >
                Remove
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1.5 rounded-full border border-[#4648d4] px-4 py-1.5 text-xs font-bold text-[#4648d4] hover:bg-[#ededfc] transition"
            >
              Connect
              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* Expanded input */}
      {expanded && !integration.connected && (
        <div className="border-t border-[#dfe2e8] px-5 pb-5 pt-4">
          {def.inputType === 'token' && (
            <>
              <label className="text-label mb-1.5 block text-[#2f3040]">{def.tokenLabel}</label>
              <input
                type="password"
                value={integration.apiToken}
                onChange={(e) => onChange({ ...integration, apiToken: e.target.value })}
                placeholder={def.tokenPlaceholder}
                className="mb-4 h-11 w-full rounded-lg border border-[#c7c4d7] bg-white px-4 text-sm font-mono outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
              />
              <label className="text-label mb-1.5 block text-[#2f3040]">{def.notesLabel}</label>
              <input
                type="text"
                value={integration.workspaceName}
                onChange={(e) => onChange({ ...integration, workspaceName: e.target.value })}
                placeholder={def.notesPlaceholder}
                className="mb-4 h-11 w-full rounded-lg border border-[#c7c4d7] bg-white px-4 text-sm outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
              />
            </>
          )}
          {def.inputType === 'text' && (
            <>
              <label className="text-label mb-1.5 block text-[#2f3040]">{def.notesLabel}</label>
              <textarea
                value={integration.contextNotes}
                onChange={(e) => onChange({ ...integration, contextNotes: e.target.value })}
                placeholder={def.notesPlaceholder}
                rows={4}
                className="mb-4 w-full resize-none rounded-lg border border-[#c7c4d7] bg-white p-4 text-sm leading-6 outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
              />
            </>
          )}
          <button
            type="button"
            onClick={handleConnect}
            disabled={
              def.inputType === 'token'
                ? !integration.apiToken.trim()
                : !integration.contextNotes.trim()
            }
            className="flex h-10 items-center gap-2 rounded-lg bg-[#4648d4] px-5 text-sm font-bold text-white transition hover:bg-[#3a3cc0] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Check className="h-4 w-4" /> Save & Connect
          </button>
        </div>
      )}
    </div>
  )
}

function Step5({
  integrations,
  setIntegrations,
  onFinish,
  saving,
  error,
  calendarBanner,
}: {
  integrations: Integration[]
  setIntegrations: (list: Integration[]) => void
  onFinish: () => void
  saving: boolean
  error: string
  calendarBanner: 'connected' | 'denied' | 'error' | null
}) {
  const connectedCount = integrations.filter((i) => i.connected).length

  const updateIntegration = (type: IntegrationType, updated: Integration) => {
    setIntegrations(integrations.map((i) => (i.type === type ? updated : i)))
  }

  return (
    <div>
      <div className="mb-8 text-center">
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-xl bg-gradient-to-br from-[#4648d4] to-[#10B981] text-white shadow-lg">
          <Sparkles className="h-7 w-7" />
        </div>
        <div className="text-label mb-3 text-[#4648d4]">Step 5 — Your Tools</div>
        <h1 className="font-serif text-4xl font-bold text-[#191c1e] md:text-5xl">
          Connect your ecosystem.
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg leading-7 text-[#464554]">
          The more context the AI has, the more personal and accurate every suggestion becomes.
          Connect the tools you already use — or skip and add them later.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Calendar connection status banner */}
      {calendarBanner === 'connected' && (
        <div className="mb-5 flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          <Check className="h-4 w-4 shrink-0" />
          Google Calendar connected! Your schedule will power the daily energy inference.
        </div>
      )}
      {calendarBanner === 'error' && (
        <div className="mb-5 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Calendar wasn&apos;t connected — you can try again later in Settings. You can still use Freeside manually.
        </div>
      )}

      <div className="mb-6 space-y-3">
        {INTEGRATION_DEFS.map((def) => {
          const integration = integrations.find((i) => i.type === def.type)!
          return (
            <IntegrationCard
              key={def.type}
              def={def}
              integration={integration}
              onChange={(updated) => updateIntegration(def.type, updated)}
            />
          )
        })}
      </div>

      <div className="rounded-lg border border-[#e0e2ee] bg-[#f7f9fb] px-5 py-4 text-sm text-[#6b7080] mb-6">
        <span className="font-bold text-[#2f3040]">How this powers your AI: </span>
        ClickUp / Asana tasks are pulled into your daily plan. Obsidian, Notes, and Agent descriptions
        are injected into every co-pilot call — so it gives advice that fits <em>your</em> actual system.
      </div>

      <div className="flex items-center justify-between gap-4 border-t border-[#dfe2e8] pt-6">
        <p className="text-sm text-[#8183a0]">
          {connectedCount === 0
            ? 'No integrations yet — you can add them later in Settings.'
            : `${connectedCount} integration${connectedCount > 1 ? 's' : ''} connected.`}
        </p>
        <button
          id="finish-onboarding-btn"
          type="button"
          onClick={onFinish}
          disabled={saving}
          className="flex h-14 w-full max-w-sm items-center justify-center gap-3 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? 'Setting up…' : <>Go to Dashboard <ArrowRight className="h-5 w-5" /></>}
        </button>
      </div>
    </div>
  )
}

// ─── Main Wizard ───────────────────────────────────────────────────────────────

const defaultIntegrations = (): Integration[] =>
  INTEGRATION_DEFS.map((def) => ({
    type: def.type,
    connected: false,
    apiToken: '',
    contextNotes: '',
    workspaceName: '',
  }))

function OnboardingWizardInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(1)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [calendarLoading, setCalendarLoading] = useState(false)
  const [calendarBanner, setCalendarBanner] = useState<'connected' | 'denied' | 'error' | null>(null)

  // After Google OAuth redirect, detect the ?calendar= param and jump to step 5
  useEffect(() => {
    const calendarParam = searchParams.get('calendar')
    if (calendarParam === 'connected') {
      setCalendarBanner('connected')
      setDirection(1)
      setStep(4)
    } else if (calendarParam === 'denied' || calendarParam === 'error' || calendarParam === 'no_refresh_token') {
      setCalendarBanner('error')
      setDirection(1)
      setStep(4)
    }
  }, [searchParams])

  const [profile, setProfile] = useState<ProfileData>({
    name: '',
    role: '',
    productive_day_description: '',
  })
  const [goals, setGoals] = useState<Goal[]>([])
  const [workStyle, setWorkStyle] = useState<WorkStyleData>({
    peak_focus_time: '',
    daily_work_hours: '',
    work_style: '',
  })
  const [integrations, setIntegrations] = useState<Integration[]>(defaultIntegrations())

  const go = (nextStep: number) => {
    setError('')
    setDirection(nextStep > step ? 1 : -1)
    setStep(nextStep)
  }

  const getUser = async () => {
    const { data: { user } } = await supabase.auth.getUser()
    return user
  }

  // ── Save step 1 → Supabase profiles ──────────────────────────────
  const saveStep1 = async () => {
    setSaving(true)
    setError('')
    try {
      const user = await getUser()
      if (!user) throw new Error('Not logged in')
      const { error: dbErr } = await supabase.from('profiles').upsert({
        id: user.id,
        name: profile.name,
        role: profile.role,
        productive_day_description: profile.productive_day_description,
      })
      if (dbErr) throw dbErr
      go(1)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  // ── Save step 2 → Supabase goals ─────────────────────────────────
  const saveStep2 = async () => {
    setSaving(true)
    setError('')
    try {
      const user = await getUser()
      if (!user) throw new Error('Not logged in')
      await supabase.from('goals').delete().eq('user_id', user.id)
      const { error: dbErr } = await supabase.from('goals').insert(
        goals.map((g) => ({
          user_id: user.id,
          title: g.title,
          category: g.category,
          timeframe: g.timeframe,
        }))
      )
      if (dbErr) throw dbErr
      go(2)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not save goals. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  // ── Save step 3 → Supabase profiles ──────────────────────────────
  const saveStep3 = async () => {
    setSaving(true)
    setError('')
    try {
      const user = await getUser()
      if (!user) throw new Error('Not logged in')
      const { error: dbErr } = await supabase.from('profiles').upsert({
        id: user.id,
        peak_focus_time: workStyle.peak_focus_time,
        daily_work_hours: workStyle.daily_work_hours,
        work_style: workStyle.work_style,
      })
      if (dbErr) throw dbErr
      go(3)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not save work style. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  // ── Step 4 — Connect Google Calendar ─────────────────────────────
  const connectCalendar = async () => {
    setCalendarLoading(true)
    setError('')
    try {
      const user = await getUser()
      const userId = user?.id ?? 'anonymous'
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/calendar/auth/url?user_id=${userId}`
      )
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail ?? `Server error ${res.status}`)
      }
      if (!data.auth_url) {
        throw new Error('No auth URL returned from server.')
      }
      window.location.href = data.auth_url
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not connect calendar. Please try again or skip.')
      setCalendarLoading(false)
    }
  }

  const skipCalendar = () => {
    go(4)
  }

  // ── Save step 5 → integrations + complete onboarding ─────────────
  const saveStep5 = async () => {
    setSaving(true)
    setError('')
    try {
      const user = await getUser()
      if (!user) throw new Error('Not logged in')

      const connected = integrations.filter((i) => i.connected)
      if (connected.length > 0) {
        const { error: intErr } = await supabase.from('user_integrations').upsert(
          connected.map((i) => ({
            user_id: user.id,
            integration_type: i.type,
            is_connected: true,
            api_token: i.apiToken || null,
            context_notes: i.contextNotes || null,
            workspace_name: i.workspaceName || null,
          })),
          { onConflict: 'user_id,integration_type' }
        )
        if (intErr) throw intErr
      }

      const { error: profileErr } = await supabase.from('profiles').upsert({
        id: user.id,
        onboarding_completed: true,
      })
      if (profileErr) throw profileErr

      router.push('/dashboard')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not complete setup. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_10%_0%,rgba(70,72,212,0.13),transparent_32%),radial-gradient(circle_at_85%_15%,rgba(129,39,207,0.09),transparent_28%),#f7f9fb] px-4 py-10">
      <section className="w-full max-w-2xl rounded-2xl border border-white/70 bg-white/80 p-8 shadow-[0_28px_90px_rgba(70,72,212,0.13)] backdrop-blur-2xl md:p-12">
        {/* Logo */}
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-8 w-8 rotate-45 place-items-center rounded bg-[#4648d4]">
            <div className="h-3 w-3 -rotate-45 bg-white" />
          </div>
          <span className="font-serif text-lg font-bold text-[#191c1e]">Freeside</span>
        </div>

        {/* Step progress */}
        <StepProgress current={step} total={5} />

        {/* Animated step content */}
        <div className="overflow-hidden">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={step}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.28, ease: 'easeInOut' }}
            >
              {step === 0 && (
                <Step1
                  profile={profile}
                  setProfile={setProfile}
                  onNext={saveStep1}
                  saving={saving}
                  error={error}
                />
              )}
              {step === 1 && (
                <Step2
                  goals={goals}
                  setGoals={setGoals}
                  onNext={saveStep2}
                  saving={saving}
                  error={error}
                />
              )}
              {step === 2 && (
                <Step3
                  workStyle={workStyle}
                  setWorkStyle={setWorkStyle}
                  onNext={saveStep3}
                  saving={saving}
                  error={error}
                />
              )}
              {step === 3 && (
                <Step4
                  onConnect={connectCalendar}
                  onSkip={skipCalendar}
                  loading={calendarLoading || saving}
                />
              )}
              {step === 4 && (
                <Step5
                  integrations={integrations}
                  setIntegrations={setIntegrations}
                  onFinish={saveStep5}
                  saving={saving}
                  error={error}
                  calendarBanner={calendarBanner}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </section>
    </main>
  )
}

export default function OnboardingWizard() {
  return (
    <Suspense fallback={
      <main className="grid min-h-screen place-items-center bg-[#f7f9fb]">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-[#e2e3ec] border-t-[#4648d4]" />
      </main>
    }>
      <OnboardingWizardInner />
    </Suspense>
  )
}
