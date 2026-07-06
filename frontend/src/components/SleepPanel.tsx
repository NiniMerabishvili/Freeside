'use client'

import { useCallback, useEffect, useState } from 'react'
import { Loader2, Moon } from 'lucide-react'
import { supabase } from '@/lib/supabase'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const HOUR_PRESETS = [4, 5, 6, 7, 8, 9]

const RESTED_LABELS: Record<number, string> = {
  1: 'Not rested',
  2: 'Slightly rested',
  3: 'Okay',
  4: 'Well rested',
  5: 'Very rested',
}

export default function SleepPanel() {
  const [userId, setUserId] = useState<string | null>(null)
  const [mode, setMode] = useState<'checking' | 'needs_log' | 'done'>('checking')
  const [hours, setHours] = useState(7)
  const [rested, setRested] = useState(3)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadToday = useCallback(async (uid: string) => {
    setError(null)
    try {
      const res = await fetch(`${API}/sleep/today?user_id=${uid}`)
      const data = await res.json()
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load sleep log.')
      }
      if (data.logged_today) {
        setHours(Number(data.hours_slept) || 7)
        setRested(Number(data.rested_score) || 3)
        setMode('done')
      } else {
        setMode('needs_log')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load sleep log.')
      setMode('needs_log')
    }
  }, [])

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const uid = data.user?.id ?? null
      setUserId(uid)
      if (uid) void loadToday(uid)
      else setMode('needs_log')
    })
  }, [loadToday])

  const saveSleep = async () => {
    if (!userId) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${API}/sleep/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          hours_slept: hours,
          rested_score: rested,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save sleep log.')
      }
      setMode('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save sleep log.')
    } finally {
      setSaving(false)
    }
  }

  if (mode === 'checking') {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-[#eceef4] bg-white px-4 py-3 text-sm text-[#6b7080]">
        <Loader2 className="h-4 w-4 animate-spin text-[#0891b2]" />
        Loading sleep check-in…
      </div>
    )
  }

  if (mode === 'done') {
    return (
      <div className="flex items-center justify-between rounded-lg border border-[#0891b2]/20 bg-[#ecfeff] px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <Moon className="h-3.5 w-3.5 shrink-0 text-[#0891b2]" />
          <span className="text-sm font-semibold text-[#0e7490]">
            {hours}h sleep · {RESTED_LABELS[rested] ?? `${rested}/5`}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setMode('needs_log')}
          className="text-xs text-[#0891b2] underline-offset-2 hover:underline"
        >
          Change
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-[#eceef4] bg-white shadow-sm">
      <div className="border-b border-[#eceef4] px-4 py-3">
        <div className="flex items-center gap-2">
          <Moon className="h-4 w-4 text-[#0891b2]" />
          <p className="text-sm font-medium text-[#2d2d40]">How did you sleep last night?</p>
        </div>
        <p className="mt-1 text-xs text-[#6b7080]">
          Used for your sleep quality research metric (SQDS / PSQI proxy).
        </p>
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      </div>

      <div className="space-y-4 px-4 py-4">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#9092a8]">
            Hours slept
          </div>
          <div className="flex flex-wrap gap-2">
            {HOUR_PRESETS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setHours(value)}
                className={`rounded-lg border px-3 py-1.5 text-sm font-semibold transition ${
                  hours === value
                    ? 'border-[#0891b2] bg-[#ecfeff] text-[#0e7490]'
                    : 'border-[#dfe2e8] bg-white text-[#464554] hover:border-[#0891b2]/40'
                }`}
              >
                {value}h
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-[#9092a8]">
              How rested do you feel?
            </span>
            <span className="text-xs font-semibold text-[#0891b2]">
              {RESTED_LABELS[rested]} · {rested}/5
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={5}
            value={rested}
            onChange={(event) => setRested(Number(event.target.value))}
            className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-[#eceef4] outline-none
                       [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full
                       [&::-webkit-slider-thumb]:bg-[#0891b2] [&::-webkit-slider-thumb]:shadow-sm"
          />
          <div className="mt-2 flex justify-between text-[10px] text-[#9092a8]">
            <span>1</span>
            <span>3</span>
            <span>5</span>
          </div>
        </div>
      </div>

      <div className="border-t border-[#eceef4] px-4 py-3">
        <button
          type="button"
          onClick={() => void saveSleep()}
          disabled={saving || !userId}
          className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-[#0891b2] text-sm font-semibold text-white transition hover:bg-[#0e7490] disabled:opacity-60"
        >
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Log sleep
        </button>
      </div>
    </div>
  )
}
