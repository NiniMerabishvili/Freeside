'use client'

import { useState } from 'react'
import { BookOpenText, CheckCircle2, Database, Loader2, Sparkles } from 'lucide-react'
import type { SuggestedMilestone } from '@/components/SuggestedTasksPanel'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type ProjectMemoryMilestone = {
  title: string
  cognitive_load_score: number
  estimated_minutes?: number
  source_refs?: string[]
  tasks: {
    title: string
    cognitive_load_score: number
    estimated_minutes?: number
    source_refs?: string[]
  }[]
}

type RetrievedContext = {
  id?: string
  title?: string
  source_type?: string
  chunk_index?: number
  similarity?: number
  preview?: string
}

type Props = {
  userId: string
  energyScore: number
  energyLevel: string
  onMilestonesSuggested: (milestones: SuggestedMilestone[]) => void
}

function toSuggestedMilestones(milestones: ProjectMemoryMilestone[]): SuggestedMilestone[] {
  return milestones.map(m => ({
    id: crypto.randomUUID(),
    title: m.title,
    cognitive_load_score: m.cognitive_load_score,
    estimated_minutes: m.estimated_minutes,
    tasks: (m.tasks ?? []).map(t => ({
      id: crypto.randomUUID(),
      title: t.title,
      cognitive_load_score: t.cognitive_load_score,
      estimated_minutes: t.estimated_minutes,
    })),
  }))
}

export default function ProjectMemoryPanel({
  userId,
  energyScore,
  energyLevel,
  onMilestonesSuggested,
}: Props) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [question, setQuestion] = useState('What should I move forward next?')
  const [saving, setSaving] = useState(false)
  const [planning, setPlanning] = useState(false)
  const [status, setStatus] = useState('')
  const [err, setErr] = useState('')
  const [reply, setReply] = useState('')
  const [blockers, setBlockers] = useState<string[]>([])
  const [citations, setCitations] = useState<string[]>([])
  const [retrieved, setRetrieved] = useState<RetrievedContext[]>([])

  const saveMemory = async () => {
    if (!title.trim() || !content.trim()) {
      setErr('Add a title and project context first.')
      return
    }
    setSaving(true)
    setErr('')
    setStatus('')
    try {
      const res = await fetch(`${API}/project-memory/sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          title: title.trim(),
          content: content.trim(),
          source_type: 'project_note',
        }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setStatus(`Saved ${data.inserted ?? 0} memory chunk${data.inserted === 1 ? '' : 's'}.`)
      setContent('')
    } catch {
      setErr('Could not save project memory.')
    } finally {
      setSaving(false)
    }
  }

  const planFromMemory = async () => {
    if (!question.trim()) {
      setErr('Write a planning question first.')
      return
    }
    setPlanning(true)
    setErr('')
    setStatus('')
    try {
      const res = await fetch(`${API}/project-memory/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          question: question.trim(),
          energy_score: energyScore || undefined,
          energy_level: energyLevel || undefined,
        }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setReply(data.reply ?? '')
      setBlockers(data.blockers ?? [])
      setCitations(data.citations ?? [])
      setRetrieved(data.retrieved_context ?? [])
      if (Array.isArray(data.milestones) && data.milestones.length) {
        onMilestonesSuggested(toSuggestedMilestones(data.milestones))
      }
    } catch {
      setErr('Could not plan from project memory.')
    } finally {
      setPlanning(false)
    }
  }

  return (
    <section className="rounded-lg border border-[#dce3f0] bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-[#eceef4] px-4 py-3">
        <div className="flex min-w-0 items-start gap-2">
          <Database className="mt-0.5 h-4 w-4 shrink-0 text-[#4648d4]" />
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#4648d4]">Project Memory</p>
            <p className="mt-0.5 text-sm font-semibold text-[#191c1e]">Grounded planning</p>
          </div>
        </div>
        {status && (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#e6f4ea] px-2 py-1 text-[10px] font-semibold text-[#2d7a3a]">
            <CheckCircle2 className="h-3 w-3" />
            {status}
          </span>
        )}
      </div>

      <div className="space-y-4 px-4 py-4">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Client launch brief"
            className="h-10 rounded-lg border border-[#d7d9e1] px-3 text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#4648d4]"
          />
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Paste project notes, requirements, meeting notes, or messy context."
            rows={3}
            className="min-h-10 resize-none rounded-lg border border-[#d7d9e1] px-3 py-2 text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] focus:border-[#4648d4]"
          />
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={saveMemory}
            disabled={saving}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-[#d7d9e1] bg-white px-3 text-xs font-semibold text-[#4a4a58] hover:bg-[#f5f5f8] disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BookOpenText className="h-3.5 w-3.5" />}
            Save memory
          </button>

          <div className="flex min-w-0 flex-1 gap-2">
            <input
              value={question}
              onChange={e => setQuestion(e.target.value)}
              className="h-9 min-w-0 flex-1 rounded-lg border border-[#d7d9e1] px-3 text-sm text-[#191c1e] outline-none focus:border-[#8127cf]"
            />
            <button
              type="button"
              onClick={planFromMemory}
              disabled={planning}
              className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg bg-[#8127cf] px-3 text-xs font-semibold text-white hover:bg-[#6d1fb3] disabled:opacity-60"
            >
              {planning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Plan
            </button>
          </div>
        </div>

        {err && <p className="text-xs text-red-600">{err}</p>}

        {(reply || blockers.length > 0 || citations.length > 0) && (
          <div className="rounded-lg border border-[#eceef4] bg-[#fafbfc] px-3 py-3">
            {reply && <p className="text-sm text-[#2d2d40]">{reply}</p>}
            {blockers.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {blockers.map((blocker, i) => (
                  <span key={`${blocker}-${i}`} className="rounded-full bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-700">
                    {blocker}
                  </span>
                ))}
              </div>
            )}
            {citations.length > 0 && (
              <p className="mt-2 text-[10px] font-semibold uppercase tracking-widest text-[#9092a8]">
                Sources: {citations.join(', ')}
              </p>
            )}
          </div>
        )}

        {retrieved.length > 0 && (
          <details className="rounded-lg border border-[#eceef4] bg-white">
            <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-[#6b7080] [&::-webkit-details-marker]:hidden">
              Retrieved context ({retrieved.length})
            </summary>
            <div className="space-y-2 border-t border-[#eceef4] px-3 py-2">
              {retrieved.slice(0, 4).map((item, i) => (
                <div key={item.id ?? `${item.title}-${i}`} className="text-xs text-[#4a4a58]">
                  <p className="font-semibold text-[#191c1e]">
                    {item.title ?? 'Project memory'} #{item.chunk_index ?? i}
                  </p>
                  <p className="mt-0.5 line-clamp-2">{item.preview}</p>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </section>
  )
}
