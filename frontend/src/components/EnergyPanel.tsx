'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { BatteryCharging, Calendar, Coffee, Flame, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { supabase } from '@/lib/supabase'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Suggestion =
  | {
      mode: 'manual'
      suggestion: null
      quota_exhausted?: boolean
      calendar_reconnect_required?: boolean
      calendar_not_connected?: boolean
      fallback_reason?: string
    }
  | {
      mode: 'ai_suggested'
      ai_suggested_score: number
      ai_suggested_level: string
      reasoning: string
      calendar_event_count: number
      calendar_summary: string
      clickup_task_count?: number
      clickup_overdue?: number
      sources_used?: string[]
    }

function scoreToLevel(score: number): 'high' | 'balanced' | 'low' {
  if (score >= 7) return 'high'
  if (score >= 4) return 'balanced'
  return 'low'
}

const LEVEL_META = {
  high:     { label: 'High',     sub: 'Deep Work & Creation', icon: Flame,          color: '#1f22f0', bg: '#e8e7ff' },
  balanced: { label: 'Balanced', sub: 'Meetings & Planning',  icon: BatteryCharging, color: '#8127cf', bg: '#f0e5fb' },
  low:      { label: 'Low',      sub: 'Admin & Light Tasks',  icon: Coffee,          color: '#6b7080', bg: '#f1f2f5' },
}

type Props = {
  /** uid is passed so the parent can call fetchTasks without a stale userId state */
  onConfirmed?: (level: string, score: number, uid: string, isUpdate?: boolean) => void
  /** Live preview while the user drags the energy slider */
  onScoreChange?: (level: string, score: number) => void
}

export default function EnergyPanel({ onConfirmed, onScoreChange }: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [userId, setUserId]         = useState<string | null>(null)
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null)
  const [confirmedScore, setScore]  = useState(5)
  // Three states: 'checking' | 'needs_checkin' | 'already_done'
  const [mode, setMode]             = useState<'checking' | 'needs_checkin' | 'already_done'>('checking')
  const [refreshing, setRefreshing] = useState(false)
  const [connectingCalendar, setConnectingCalendar] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError]           = useState<string | null>(null)

  // Keep a stable ref to the callback so it never triggers the useEffect
  const onConfirmedRef = useRef(onConfirmed)
  useEffect(() => { onConfirmedRef.current = onConfirmed })
  const onScoreChangeRef = useRef(onScoreChange)
  useEffect(() => { onScoreChangeRef.current = onScoreChange })
  const isReconfirmRef = useRef(false)

  const fetchSuggestion = useCallback((uid: string, isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    setError(null)
    return fetch(`${API}/energy/suggest?user_id=${uid}`)
      .then(r => r.json())
      .then((d: Suggestion) => {
        setSuggestion(d)
        if (d.mode === 'ai_suggested') setScore(d.ai_suggested_score)
        return d
      })
      .catch(() => {
        setError('Backend not reachable. Set energy manually.')
        return null
      })
      .finally(() => setRefreshing(false))
  }, [])

  const connectCalendar = async () => {
    if (!userId) return
    setConnectingCalendar(true)
    setError(null)
    try {
      const res = await fetch(`${API}/calendar/auth/url?user_id=${userId}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? `Server error ${res.status}`)
      if (!data.auth_url) throw new Error('No auth URL returned from server.')
      window.location.href = data.auth_url
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not connect Google Calendar.')
      setConnectingCalendar(false)
    }
  }

  // After Google OAuth redirect, re-fetch calendar-based AI suggestion
  useEffect(() => {
    if (searchParams.get('calendar') !== 'connected' || !userId) return
    setMode('needs_checkin')
    fetchSuggestion(userId, true)
    router.replace('/dashboard')
  }, [searchParams, userId, fetchSuggestion, router])

  // Runs exactly once on mount — no callback in deps to avoid infinite loops
  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const uid = data.user?.id ?? null
      setUserId(uid)
      if (!uid) { setMode('needs_checkin'); return }

      // Check if energy already logged today — skip full check-in if so
      fetch(`${API}/energy/today?user_id=${uid}`)
        .then(r => r.json())
        .then((d: { logged_today: boolean; confirmed_score?: number; confirmed_level?: string }) => {
          if (d.logged_today && d.confirmed_score != null) {
            setScore(d.confirmed_score)
            setMode('already_done')
            onConfirmedRef.current?.(d.confirmed_level!, d.confirmed_score, uid, true)
          } else {
            setMode('needs_checkin')
            fetchSuggestion(uid)
          }
        })
        .catch(() => {
          setMode('needs_checkin')
          fetchSuggestion(uid)
        })
    })
  // fetchSuggestion is a stable useCallback — safe to include; onConfirmedRef.current is not reactive
  }, [fetchSuggestion])

  const confirmEnergy = async () => {
    if (!userId) return
    setConfirming(true)
    const level = scoreToLevel(confirmedScore)
    const uid   = userId
    try {
      await fetch(`${API}/energy/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id:              uid,
          confirmed_score:      confirmedScore,
          confirmed_level:      level,
          ai_suggested_score:   suggestion?.mode === 'ai_suggested' ? suggestion.ai_suggested_score : null,
          ai_suggested_level:   suggestion?.mode === 'ai_suggested' ? suggestion.ai_suggested_level : null,
          ai_reasoning:         suggestion?.mode === 'ai_suggested' ? suggestion.reasoning : null,
          calendar_event_count: suggestion?.mode === 'ai_suggested' ? suggestion.calendar_event_count : null,
          calendar_context:     suggestion?.mode === 'ai_suggested' ? suggestion.calendar_summary : null,
        }),
      })
      setMode('already_done')
      onConfirmedRef.current?.(level, confirmedScore, uid, isReconfirmRef.current)
      isReconfirmRef.current = false
    } catch {
      setError('Failed to save. Try again.')
    } finally {
      setConfirming(false)
    }
  }

  // ── Checking state ──────────────────────────────────────────────────────────
  if (mode === 'checking') return (
    <div className="flex items-center gap-3 rounded-lg border border-[#eceef4] bg-white px-4 py-3 text-sm text-[#6b7080]">
      <Loader2 className="h-4 w-4 animate-spin text-[#4648d4]" />
      Checking your energy for today…
    </div>
  )

  // ── Already confirmed today — show compact chip ─────────────────────────────
  if (mode === 'already_done') {
    const level = scoreToLevel(confirmedScore)
    const meta  = LEVEL_META[level]
    const Icon  = meta.icon
    return (
      <div className="flex items-center justify-between rounded-lg border px-4 py-2.5" style={{ borderColor: meta.color + '33', backgroundColor: meta.bg }}>
        <div className="flex items-center gap-2.5">
          <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: meta.color }} />
          <span className="text-sm font-semibold" style={{ color: meta.color }}>
            Energy {confirmedScore}/10 · {meta.label}
          </span>
          <span className="hidden text-xs text-[#6b7080] sm:inline">— {meta.sub}</span>
        </div>
        <button
          onClick={() => { isReconfirmRef.current = true; setMode('needs_checkin'); fetchSuggestion(userId!) }}
          className="text-xs text-[#9092a8] underline-offset-2 hover:text-[#191c1e] hover:underline"
        >
          Change
        </button>
      </div>
    )
  }

  // ── Full check-in panel ─────────────────────────────────────────────────────
  const isAI  = suggestion?.mode === 'ai_suggested'
  const level = scoreToLevel(confirmedScore)
  const meta  = LEVEL_META[level]

  return (
    <div className="rounded-lg border border-[#eceef4] bg-white shadow-sm">
      {/* Header */}
      <div className="border-b border-[#eceef4] px-4 py-3">
        {isAI && suggestion ? (
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[#4648d4]" />
              <div>
                <p className="text-sm text-[#2d2d40]">"{suggestion.reasoning}"</p>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[#6b7080]">
                  {suggestion.sources_used?.includes('calendar') && (
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {suggestion.calendar_event_count} meeting{suggestion.calendar_event_count !== 1 ? 's' : ''}
                    </span>
                  )}
                  {suggestion.sources_used?.includes('clickup') && (
                    <span>
                      ClickUp: {suggestion.clickup_task_count ?? 0} tasks
                      {(suggestion.clickup_overdue ?? 0) > 0 && ` · ${suggestion.clickup_overdue} overdue`}
                    </span>
                  )}
                  {suggestion.sources_used?.includes('copilot') && (
                    <span>Co-Pilot history</span>
                  )}
                  <span>
                    · AI suggests <strong className="text-[#4648d4]">{suggestion.ai_suggested_score}/10</strong>
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={() => userId && fetchSuggestion(userId, true)}
              disabled={refreshing}
              title="Re-analyse day context"
              className="mt-0.5 shrink-0 rounded p-1 text-[#9092a8] transition hover:bg-[#f0f1f5] hover:text-[#4648d4] disabled:opacity-40"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-3">
            <div>
              {suggestion?.mode === 'manual' &&
              (suggestion.calendar_not_connected || suggestion.calendar_reconnect_required) ? (
                <>
                  <p className="text-sm font-medium text-[#2d2d40]">Connect your tools for AI energy planning</p>
                  <p className="mt-0.5 text-xs text-[#6b7080]">
                    Link Google Calendar and/or ClickUp in Settings — Freeside combines them with Co-Pilot chat to suggest energy and route tasks.
                  </p>
                  <button
                    type="button"
                    onClick={connectCalendar}
                    disabled={connectingCalendar}
                    className="mt-2 flex items-center gap-1.5 rounded-lg bg-[#4648d4] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#3f3dc6] disabled:opacity-60"
                  >
                    {connectingCalendar ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Calendar className="h-3.5 w-3.5" />
                    )}
                    {connectingCalendar ? 'Redirecting to Google…' : 'Connect Google Calendar'}
                  </button>
                </>
              ) : suggestion?.mode === 'manual' && suggestion.quota_exhausted ? (
                <>
                  <p className="text-sm font-medium text-[#2d2d40]">Set your energy manually</p>
                  <p className="mt-0.5 text-xs text-amber-600">
                    ⚠ AI calendar analysis unavailable — daily Gemini quota reached. Resets tomorrow.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-[#2d2d40]">How's your energy right now?</p>
                  {error && <p className="mt-0.5 text-xs text-amber-600">{error}</p>}
                </>
              )}
            </div>
            {userId && (
              <button
                onClick={() => fetchSuggestion(userId, true)}
                disabled={refreshing}
                title="Re-analyse day context"
                className="mt-0.5 shrink-0 rounded p-1 text-[#9092a8] transition hover:bg-[#f0f1f5] hover:text-[#4648d4] disabled:opacity-40"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Slider */}
      <div className="px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs text-[#9092a8]">Drag to adjust</span>
          <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ backgroundColor: meta.bg, color: meta.color }}>
            {meta.label} · {confirmedScore}/10
          </span>
        </div>
        <input
          type="range" min={1} max={10} value={confirmedScore}
          onChange={e => {
            const score = Number(e.target.value)
            setScore(score)
            onScoreChangeRef.current?.(scoreToLevel(score), score)
          }}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-[#eceef4] outline-none
                     [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4
                     [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full
                     [&::-webkit-slider-thumb]:bg-[#4648d4] [&::-webkit-slider-thumb]:shadow-sm"
        />
        <div className="mt-2 flex justify-between text-xs text-[#9092a8]">
          <span>🌙 Low</span>
          <span>🌤 Balanced</span>
          <span>⚡ High</span>
        </div>
        {isAI && suggestion && confirmedScore !== suggestion.ai_suggested_score && (
          <p className="mt-2 text-xs text-[#8127cf]">Adjusted from AI suggestion ({suggestion.ai_suggested_score}/10)</p>
        )}
      </div>

      {/* Action */}
      <div className="border-t border-[#eceef4] px-4 py-3">
        <button
          onClick={confirmEnergy}
          disabled={confirming}
          className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-sm font-semibold text-white transition hover:bg-[#3f3dc6] disabled:opacity-60"
        >
          {confirming && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Start my day →
        </button>
      </div>
    </div>
  )
}
