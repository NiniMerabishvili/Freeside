'use client'

import { useEffect, useState } from 'react'
import { BatteryCharging, Calendar, Coffee, Flame, Loader2, Sparkles } from 'lucide-react'
import { supabase } from '@/lib/supabase'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Suggestion =
  | { mode: 'manual'; suggestion: null }
  | {
      mode: 'ai_suggested'
      ai_suggested_score: number
      ai_suggested_level: string
      reasoning: string
      calendar_event_count: number
      calendar_summary: string
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

export default function EnergyPanel({ onConfirmed }: { onConfirmed?: (level: string, score: number) => void }) {
  const [userId, setUserId]           = useState<string | null>(null)
  const [suggestion, setSuggestion]   = useState<Suggestion | null>(null)
  const [confirmedScore, setScore]    = useState(5)
  const [isConfirmed, setConfirmed]   = useState(false)
  const [loading, setLoading]         = useState(true)
  const [confirming, setConfirming]   = useState(false)
  const [error, setError]             = useState<string | null>(null)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const uid = data.user?.id ?? null
      setUserId(uid)
      if (!uid) { setLoading(false); return }
      fetch(`${API}/energy/suggest?user_id=${uid}`)
        .then(r => r.json())
        .then((d: Suggestion) => {
          setSuggestion(d)
          if (d.mode === 'ai_suggested') setScore(d.ai_suggested_score)
        })
        .catch(() => setError('Backend not reachable. Set energy manually.'))
        .finally(() => setLoading(false))
    })
  }, [])

  const confirmEnergy = async () => {
    if (!userId) return
    setConfirming(true)
    const level = scoreToLevel(confirmedScore)
    try {
      await fetch(`${API}/energy/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          confirmed_score: confirmedScore,
          confirmed_level: level,
          ai_suggested_score:   suggestion?.mode === 'ai_suggested' ? suggestion.ai_suggested_score : null,
          ai_suggested_level:   suggestion?.mode === 'ai_suggested' ? suggestion.ai_suggested_level : null,
          ai_reasoning:         suggestion?.mode === 'ai_suggested' ? suggestion.reasoning : null,
          calendar_event_count: suggestion?.mode === 'ai_suggested' ? suggestion.calendar_event_count : null,
          calendar_context:     suggestion?.mode === 'ai_suggested' ? suggestion.calendar_summary : null,
        }),
      })
      setConfirmed(true)
      onConfirmed?.(level, confirmedScore)
    } catch {
      setError('Failed to save. Try again.')
    } finally {
      setConfirming(false)
    }
  }

  if (loading) return (
    <div className="flex items-center gap-3 rounded-lg border border-[#eceef4] bg-white px-4 py-3 text-sm text-[#6b7080]">
      <Loader2 className="h-4 w-4 animate-spin text-[#4648d4]" />
      Analyzing your calendar…
    </div>
  )

  if (isConfirmed) {
    const level = scoreToLevel(confirmedScore)
    const meta  = LEVEL_META[level]
    const Icon  = meta.icon
    return (
      <div className="flex items-center justify-between rounded-lg border px-4 py-3" style={{ borderColor: meta.color + '33', backgroundColor: meta.bg }}>
        <div className="flex items-center gap-3">
          <Icon className="h-4 w-4 shrink-0" style={{ color: meta.color }} />
          <span className="text-sm font-semibold" style={{ color: meta.color }}>
            {meta.label} — {confirmedScore}/10
          </span>
          <span className="text-sm text-[#6b7080]">· {meta.sub}</span>
        </div>
        <button onClick={() => setConfirmed(false)} className="text-xs text-[#6b7080] hover:text-[#191c1e]">
          Adjust
        </button>
      </div>
    )
  }

  const isAI  = suggestion?.mode === 'ai_suggested'
  const level = scoreToLevel(confirmedScore)
  const meta  = LEVEL_META[level]

  return (
    <div className="rounded-lg border border-[#eceef4] bg-white shadow-sm">
      {/* Header */}
      <div className="border-b border-[#eceef4] px-4 py-3">
        {isAI && suggestion ? (
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[#4648d4]" />
            <div>
              <p className="text-sm text-[#2d2d40]">"{suggestion.reasoning}"</p>
              <div className="mt-1 flex items-center gap-2 text-xs text-[#6b7080]">
                <Calendar className="h-3 w-3" />
                <span>{suggestion.calendar_event_count} events today · AI suggests <strong className="text-[#4648d4]">{suggestion.ai_suggested_score}/10</strong></span>
              </div>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium text-[#2d2d40]">How's your energy right now?</p>
            {error && <p className="mt-0.5 text-xs text-amber-600">{error}</p>}
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
          onChange={e => setScore(Number(e.target.value))}
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
