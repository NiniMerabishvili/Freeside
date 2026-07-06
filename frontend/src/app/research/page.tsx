'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  AlertCircle,
  Download,
  FlaskConical,
  Loader2,
  RefreshCw,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { supabase } from '@/lib/supabase'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_EMAIL = 'ninachkheidze19@gmail.com'

// ── Types ─────────────────────────────────────────────────────────────────────

type MetricRow = {
  user_id: string
  tcr_percentage: number | null
  total_created: number
  total_completed: number
  reroute_percentage: number | null
  total_interactions: number
  reroute_count: number
  avg_hours_slept: number | null
  avg_rested_score: number | null
  sleep_logs_count: number
  avg_initiation_delay_minutes: number | null
  tasks_evaluated: number
  tasks_never_viewed: number
  total_breakdowns_requested: number
  overall_avg_energy: number | null
  consecutive_decline_days: number
  burnout_flag: boolean
}

type UserProfile = {
  id: string
  display_name: string | null
  created_at: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (v: number | null, decimals = 1) =>
  v === null ? <span className="text-[#b0b3c0]">—</span> : v.toFixed(decimals)

const pct = (v: number | null) =>
  v === null ? <span className="text-[#b0b3c0]">—</span> : `${v.toFixed(1)}%`

function TcrBadge({ v }: { v: number | null }) {
  if (v === null) return <span className="text-[#b0b3c0]">—</span>
  const [color, label] =
    v >= 90 ? ['#2d7a3a', 'Excellent'] :
    v >= 75 ? ['#4648d4', 'Good'] :
    v >= 60 ? ['#7a5c00', 'Moderate'] :
    v >= 40 ? ['#c0540a', 'Poor'] :
              ['#c0220a', 'Critical']
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold"
      style={{ background: color + '18', color }}>
      {v.toFixed(1)}% · {label}
    </span>
  )
}

function BurnoutCell({ flag, days }: { flag: boolean; days: number }) {
  if (flag) return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-bold text-red-600">
      <TrendingDown className="h-3 w-3" /> {days}d decline
    </span>
  )
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
      <TrendingUp className="h-3 w-3" /> Stable
    </span>
  )
}

// ── Column definitions ────────────────────────────────────────────────────────

const COLUMNS = [
  { key: 'user_id',                      label: 'Participant',          group: 'meta' },
  { key: 'tcr_percentage',               label: 'TCR %',                group: 'tcr'   },
  { key: 'total_created',                label: 'Created',              group: 'tcr'   },
  { key: 'total_completed',              label: 'Completed',            group: 'tcr'   },
  { key: 'reroute_percentage',           label: 'Reroute %',            group: 'cli'   },
  { key: 'total_interactions',           label: 'Interactions',         group: 'cli'   },
  { key: 'avg_hours_slept',              label: 'Avg Sleep (h)',         group: 'sqds'  },
  { key: 'avg_rested_score',             label: 'Rested (1–5)',         group: 'sqds'  },
  { key: 'avg_initiation_delay_minutes', label: 'Init. Delay (min)',    group: 'pfi'   },
  { key: 'tasks_never_viewed',           label: 'Never Viewed',         group: 'pfi'   },
  { key: 'total_breakdowns_requested',   label: 'Breakdowns',           group: 'pfi'   },
  { key: 'overall_avg_energy',           label: 'Avg Energy (1–5)',     group: 'swbbs' },
  { key: 'burnout_flag',                 label: 'Burnout Signal',       group: 'swbbs' },
]

const GROUP_META: Record<string, { label: string; color: string }> = {
  meta:  { label: 'Participant',                       color: '#464554' },
  tcr:   { label: 'TCR — Task Completion (PPS proxy)', color: '#4648d4' },
  cli:   { label: 'CLI — Cognitive Load (NASA-TLX)',   color: '#7c3aed' },
  sqds:  { label: 'SQDS — Sleep Quality (PSQI)',       color: '#0891b2' },
  pfi:   { label: 'PFI — Procrastination (PPS/IPS)',   color: '#d97706' },
  swbbs: { label: 'SWBBS — Well-Being (PSS-10/OLBI)', color: '#dc2626' },
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ResearchPage() {
  const router = useRouter()
  const [adminEmail, setAdminEmail] = useState<string | null>(null)
  const [accessDenied, setAccessDenied] = useState(false)

  const today = new Date().toISOString().split('T')[0]
  const monthAgo = new Date(Date.now() - 28 * 86400000).toISOString().split('T')[0]

  const [startDate, setStartDate] = useState(monthAgo)
  const [endDate, setEndDate] = useState(today)
  const [users, setUsers] = useState<UserProfile[]>([])
  const [rows, setRows] = useState<MetricRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [csvString, setCsvString] = useState('')
  const [lastWindow, setLastWindow] = useState('')

  // ── Auth guard ──────────────────────────────────────────────────────────────
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) { router.push('/login'); return }
      if (user.email !== ADMIN_EMAIL) { setAccessDenied(true); return }
      setAdminEmail(user.email)
    })
  }, [router])

  // ── Load cohort user list ───────────────────────────────────────────────────
  useEffect(() => {
    if (!adminEmail) return
    fetch(`${API}/research/users?admin_email=${encodeURIComponent(adminEmail)}`)
      .then(r => r.json())
      .then(d => setUsers(d.users ?? []))
      .catch(() => setError('Could not load participant list from backend.'))
  }, [adminEmail])

  // ── Fetch metrics ───────────────────────────────────────────────────────────
  const fetchMetrics = useCallback(async () => {
    if (!adminEmail || users.length === 0) return
    setLoading(true)
    setError('')
    try {
      const resp = await fetch(`${API}/research/export/json`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_email: adminEmail,
          user_ids: users.map(u => u.id),
          start_date: startDate,
          end_date: endDate,
        }),
      })
      if (!resp.ok) {
        const msg = await resp.json()
        throw new Error(msg.detail ?? 'Export failed')
      }
      const data = await resp.json()
      setRows(data.rows ?? [])
      setCsvString(data.csv_string ?? '')
      setLastWindow(`${startDate} → ${endDate}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [adminEmail, users, startDate, endDate])

  // ── CSV download ────────────────────────────────────────────────────────────
  const downloadCsv = () => {
    if (!csvString) return
    const blob = new Blob([csvString], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `freeside_behavioral_${startDate}_${endDate}_n${rows.length}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Render: access denied ───────────────────────────────────────────────────
  if (accessDenied) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f7f9fb]">
        <div className="flex flex-col items-center gap-4 rounded-2xl border border-red-200 bg-white p-10 shadow-lg">
          <ShieldAlert className="h-12 w-12 text-red-500" />
          <h1 className="text-xl font-bold text-[#191c1e]">Admin access only</h1>
          <p className="text-sm text-[#6b7080]">This page is restricted to the research administrator.</p>
          <button onClick={() => router.push('/dashboard')}
            className="mt-2 rounded-lg bg-[#4648d4] px-6 py-2.5 text-sm font-bold text-white hover:bg-[#3a3cc0]">
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  if (!adminEmail) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f7f9fb]">
        <Loader2 className="h-8 w-8 animate-spin text-[#4648d4]" />
      </div>
    )
  }

  // ── Render: dashboard ───────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#f7f9fb] px-6 py-10">
      <div className="mx-auto max-w-[1600px]">

        {/* Header */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#4648d4]">
              <FlaskConical className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-extrabold text-[#191c1e]">Research Dashboard</h1>
              <p className="text-sm text-[#6b7080]">
                Admin · {users.length} participant{users.length !== 1 ? 's' : ''} in cohort
                {lastWindow && <span className="ml-2 text-[#4648d4]">· {lastWindow}</span>}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 rounded-lg border border-[#dfe2e8] bg-white px-3 py-2">
              <label className="text-xs font-semibold text-[#6b7080]">From</label>
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                className="text-sm font-medium text-[#191c1e] outline-none" />
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-[#dfe2e8] bg-white px-3 py-2">
              <label className="text-xs font-semibold text-[#6b7080]">To</label>
              <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
                className="text-sm font-medium text-[#191c1e] outline-none" />
            </div>
            <button onClick={fetchMetrics} disabled={loading || users.length === 0}
              className="flex items-center gap-2 rounded-lg bg-[#4648d4] px-4 py-2.5 text-sm font-bold text-white shadow hover:bg-[#3a3cc0] disabled:opacity-50">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Run Analysis
            </button>
            <button onClick={downloadCsv} disabled={!csvString}
              className="flex items-center gap-2 rounded-lg border border-[#4648d4] bg-white px-4 py-2.5 text-sm font-bold text-[#4648d4] hover:bg-[#f0f0fc] disabled:opacity-40">
              <Download className="h-4 w-4" /> Download CSV
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" /> {error}
          </div>
        )}

        {/* Legend */}
        <div className="mb-5 flex flex-wrap gap-3">
          {Object.entries(GROUP_META).filter(([k]) => k !== 'meta').map(([, g]) => (
            <span key={g.label} className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold"
              style={{ borderColor: g.color + '40', color: g.color, background: g.color + '10' }}>
              {g.label}
            </span>
          ))}
        </div>

        {/* Empty state */}
        {!loading && rows.length === 0 && (
          <div className="rounded-2xl border border-dashed border-[#c7c4d7] bg-white py-20 text-center">
            <FlaskConical className="mx-auto mb-3 h-10 w-10 text-[#c7c4d7]" />
            <p className="font-semibold text-[#6b7080]">Select a date range and click <strong>Run Analysis</strong></p>
            <p className="mt-1 text-sm text-[#9ea0b0]">Metrics will be computed for all {users.length} participants</p>
          </div>
        )}

        {/* Table */}
        {rows.length > 0 && (
          <div className="overflow-x-auto rounded-2xl border border-[#dfe2e8] bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead>
                {/* Group header row */}
                <tr className="border-b border-[#eceef4]">
                  {(() => {
                    const groups: { key: string; span: number }[] = []
                    COLUMNS.forEach(col => {
                      if (groups.length === 0 || groups[groups.length - 1].key !== col.group) {
                        groups.push({ key: col.group, span: 1 })
                      } else {
                        groups[groups.length - 1].span++
                      }
                    })
                    return groups.map(g => (
                      <th key={g.key} colSpan={g.span}
                        className="px-4 py-2 text-left text-[10px] font-bold uppercase tracking-widest"
                        style={{ color: GROUP_META[g.key].color }}>
                        {GROUP_META[g.key].label}
                      </th>
                    ))
                  })()}
                </tr>
                {/* Column header row */}
                <tr className="border-b border-[#eceef4] bg-[#f9fafb]">
                  {COLUMNS.map(col => (
                    <th key={col.key} className="whitespace-nowrap px-4 py-2.5 text-left text-xs font-semibold text-[#6b7080]">
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => {
                  const profile = users.find(u => u.id === row.user_id)
                  return (
                    <tr key={row.user_id}
                      className={`border-b border-[#f0f1f4] transition hover:bg-[#f7f8ff] ${i % 2 === 0 ? '' : 'bg-[#fafbfc]'}`}>
                      {/* Participant */}
                      <td className="px-4 py-3">
                        <div className="font-semibold text-[#191c1e]">
                          {profile?.display_name ?? 'Participant ' + (i + 1)}
                        </div>
                        <div className="font-mono text-[10px] text-[#9ea0b0]">{row.user_id.slice(0, 8)}…</div>
                      </td>
                      {/* TCR */}
                      <td className="px-4 py-3"><TcrBadge v={row.tcr_percentage} /></td>
                      <td className="px-4 py-3 text-[#464554]">{row.total_created}</td>
                      <td className="px-4 py-3 text-[#464554]">{row.total_completed}</td>
                      {/* CLI */}
                      <td className="px-4 py-3 text-[#464554]">{pct(row.reroute_percentage)}</td>
                      <td className="px-4 py-3 text-[#464554]">{row.total_interactions}</td>
                      {/* SQDS */}
                      <td className="px-4 py-3 text-[#464554]">{fmt(row.avg_hours_slept)}</td>
                      <td className="px-4 py-3 text-[#464554]">{fmt(row.avg_rested_score)}</td>
                      {/* PFI */}
                      <td className="px-4 py-3 text-[#464554]">{fmt(row.avg_initiation_delay_minutes, 0)}</td>
                      <td className="px-4 py-3 text-[#464554]">{row.tasks_never_viewed}</td>
                      <td className="px-4 py-3 text-[#464554]">{row.total_breakdowns_requested}</td>
                      {/* SWBBS */}
                      <td className="px-4 py-3 text-[#464554]">{fmt(row.overall_avg_energy)}</td>
                      <td className="px-4 py-3">
                        <BurnoutCell flag={row.burnout_flag} days={row.consecutive_decline_days} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Footer summary */}
            <div className="border-t border-[#eceef4] px-6 py-3 text-xs text-[#9ea0b0]">
              {rows.length} participants · window {lastWindow} · export ready
              <span className="ml-3 cursor-pointer text-[#4648d4] hover:underline" onClick={downloadCsv}>
                Download CSV →
              </span>
            </div>
          </div>
        )}

        {/* Metric definitions reference */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {[
            { label: 'TCR', full: 'Task Completion Rate', instrument: 'PPS / IPS', color: '#4648d4',
              desc: 'Ratio of tasks completed to tasks created. Higher = less procrastination.' },
            { label: 'CLI', full: 'Cognitive Load Index', instrument: 'NASA-TLX', color: '#7c3aed',
              desc: 'Rerouting rate on low-energy sessions. Higher = more load managed by system.' },
            { label: 'SQDS', full: 'Sleep Quality & Duration', instrument: 'PSQI', color: '#0891b2',
              desc: 'Mean hours slept and subjective restedness from daily pulse checks.' },
            { label: 'PFI', full: 'Procrastination Frequency', instrument: 'PPS/IPS', color: '#d97706',
              desc: 'Time from task creation to first view (initiation delay) + breakdown requests.' },
            { label: 'SWBBS', full: 'Well-Being & Burnout Risk', instrument: 'PSS-10 / OLBI', color: '#dc2626',
              desc: 'Rolling energy trend. Flag = 3+ consecutive declining days at window end.' },
          ].map(m => (
            <div key={m.label} className="rounded-xl border border-[#eceef4] bg-white p-4">
              <div className="mb-1 flex items-center gap-2">
                <span className="rounded-md px-2 py-0.5 text-xs font-bold text-white" style={{ background: m.color }}>
                  {m.label}
                </span>
                <span className="text-xs text-[#6b7080]">vs {m.instrument}</span>
              </div>
              <div className="text-sm font-bold text-[#191c1e]">{m.full}</div>
              <p className="mt-1 text-xs text-[#6b7080]">{m.desc}</p>
            </div>
          ))}
        </div>

      </div>
    </div>
  )
}
