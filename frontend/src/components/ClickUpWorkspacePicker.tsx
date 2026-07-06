'use client'

import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Loader2 } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Workspace = { id: string; name: string }

type Props = {
  userId: string
  onComplete: (result: { workspace: string; taskCount: number; preview: string | null }) => void
  onCancel?: () => void
}

export default function ClickUpWorkspacePicker({ userId, onComplete, onCancel }: Props) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [accountLabel, setAccountLabel] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    fetch(`${API}/integrations/clickup/workspaces?user_id=${userId}`)
      .then(async (res) => {
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail ?? 'Could not load workspaces')
        if (cancelled) return
        setAccountLabel(data.account_label ?? null)
        const list: Workspace[] = data.workspaces ?? []
        setWorkspaces(list)
        if (list.length === 1) setSelectedId(list[0].id)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load workspaces')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [userId])

  const save = useCallback(async () => {
    const workspace = workspaces.find((w) => w.id === selectedId)
    if (!workspace) {
      setError('Choose a workspace to continue.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const res = await fetch(`${API}/integrations/clickup/workspace`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          team_id: workspace.id,
          team_name: workspace.name,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Could not save workspace')
      onComplete({
        workspace: data.workspace ?? workspace.name,
        taskCount: data.task_count ?? 0,
        preview: data.preview ?? null,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save workspace')
    } finally {
      setSaving(false)
    }
  }, [userId, workspaces, selectedId, onComplete])

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-[#eceef4] bg-[#f8f9fb] px-4 py-3 text-sm text-[#6b7080]">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading your ClickUp workspaces…
      </div>
    )
  }

  if (workspaces.length === 0) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        No workspaces were authorized. Go back to ClickUp and allow at least one workspace, then connect again.
        {onCancel && (
          <button type="button" onClick={onCancel} className="ml-2 font-semibold underline">
            Close
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-[#7B68EE]/30 bg-[#f8f7ff] p-5">
      <div className="mb-4 flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-[#2d7a3a]" />
        <div>
          <p className="font-semibold text-[#191c1e]">ClickUp account connected</p>
          {accountLabel && (
            <p className="text-sm text-[#464554]">Signed in as {accountLabel}</p>
          )}
          <p className="mt-1 text-sm text-[#6b7080]">Choose which workspace Freeside should use for your tasks.</p>
        </div>
      </div>

      <div className="space-y-2">
        {workspaces.map((ws) => (
          <label
            key={ws.id}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 transition ${
              selectedId === ws.id
                ? 'border-[#7B68EE] bg-white shadow-sm'
                : 'border-[#dfe2e8] bg-white/70 hover:border-[#7B68EE]/50'
            }`}
          >
            <input
              type="radio"
              name="clickup-workspace"
              value={ws.id}
              checked={selectedId === ws.id}
              onChange={() => setSelectedId(ws.id)}
              className="accent-[#7B68EE]"
            />
            <span className="font-medium text-[#191c1e]">{ws.name}</span>
          </label>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving || !selectedId}
          className="flex items-center gap-2 rounded-lg bg-[#7B68EE] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#6a58d4] disabled:opacity-60"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Use this workspace
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="rounded-lg border border-[#dfe2e8] px-4 py-2.5 text-sm font-semibold text-[#6b7080] hover:bg-white"
          >
            Cancel
          </button>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  )
}
