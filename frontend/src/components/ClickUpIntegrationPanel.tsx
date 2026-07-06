'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { CheckCircle2, Link2, ListTodo, Loader2, Unlink } from 'lucide-react'
import ClickUpWorkspacePicker from '@/components/ClickUpWorkspacePicker'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Props = {
  userId: string | null
}

type ClickUpStatus = {
  connected: boolean
  authenticated: boolean
  needs_workspace: boolean
  workspace_name?: string | null
  account_label?: string | null
}

export default function ClickUpIntegrationPanel({ userId }: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<ClickUpStatus>({
    connected: false,
    authenticated: false,
    needs_workspace: false,
  })
  const [showWorkspacePicker, setShowWorkspacePicker] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [taskCount, setTaskCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const clearClickUpParam = useCallback(() => {
    if (searchParams.get('clickup')) {
      router.replace('/settings')
    }
  }, [router, searchParams])

  const loadStatus = useCallback(async () => {
    if (!userId) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API}/integrations/status?user_id=${userId}`)
      const data = await res.json()
      const cu = data.clickup ?? {}
      const next: ClickUpStatus = {
        connected: !!cu.connected,
        authenticated: !!cu.authenticated,
        needs_workspace: !!cu.needs_workspace,
        workspace_name: cu.workspace_name,
        account_label: cu.account_label,
      }
      setStatus(next)

      if (next.connected) {
        const prev = await fetch(`${API}/integrations/clickup/tasks?user_id=${userId}`)
        if (prev.ok) {
          const tasks = await prev.json()
          setTaskCount(tasks.task_count ?? 0)
          setPreview(tasks.task_list ?? null)
        } else {
          setPreview(null)
          setTaskCount(null)
        }
      } else {
        setPreview(null)
        setTaskCount(null)
      }

      if (next.needs_workspace) {
        setShowWorkspacePicker(true)
      }
    } catch {
      setError('Could not load integration status.')
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  useEffect(() => {
    const param = searchParams.get('clickup')
    if (param === 'select_workspace' && userId) {
      setShowWorkspacePicker(true)
      setSuccess('ClickUp account connected — choose your workspace below.')
    } else if (param === 'denied') {
      setError('ClickUp connection was cancelled.')
      clearClickUpParam()
    } else if (param === 'error') {
      setError('ClickUp connection failed. Try again.')
      clearClickUpParam()
    }
  }, [searchParams, userId, clearClickUpParam])

  const connectOAuth = async () => {
    if (!userId) return
    setConnecting(true)
    setError('')
    setSuccess('')
    try {
      const res = await fetch(`${API}/integrations/clickup/auth/url?user_id=${userId}&return_to=settings`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Could not start ClickUp sign-in')
      if (!data.auth_url) throw new Error('No auth URL returned')
      window.location.href = data.auth_url
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not connect ClickUp')
      setConnecting(false)
    }
  }

  const disconnect = async () => {
    if (!userId) return
    setConnecting(true)
    setError('')
    try {
      await fetch(`${API}/integrations/clickup/disconnect?user_id=${userId}`, { method: 'DELETE' })
      setStatus({ connected: false, authenticated: false, needs_workspace: false })
      setShowWorkspacePicker(false)
      setPreview(null)
      setTaskCount(null)
      setSuccess('ClickUp disconnected.')
      clearClickUpParam()
    } catch {
      setError('Disconnect failed.')
    } finally {
      setConnecting(false)
    }
  }

  const onWorkspaceComplete = (result: { workspace: string; taskCount: number; preview: string | null }) => {
    setShowWorkspacePicker(false)
    setStatus((s) => ({
      ...s,
      connected: true,
      needs_workspace: false,
      workspace_name: result.workspace,
    }))
    setTaskCount(result.taskCount)
    setPreview(result.preview)
    setSuccess(`Connected to ${result.workspace} · ${result.taskCount} open tasks`)
    clearClickUpParam()
  }

  return (
    <div className="rounded-lg border border-[#dfe2e8] bg-white p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#7B68EE]/10 text-[#7B68EE]">
            <ListTodo className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-2xl font-medium text-[#191c1e]">ClickUp</h3>
            <p className="mt-1 max-w-xl text-lg text-[#464554]">
              Sign in with ClickUp (like Google Calendar), then pick the workspace Freeside should read tasks from.
            </p>
            {status.connected && (
              <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-[#2d7a3a]">
                <CheckCircle2 className="h-4 w-4" />
                {status.account_label ? `${status.account_label} · ` : ''}
                {status.workspace_name}
                {taskCount != null && ` · ${taskCount} open tasks`}
              </p>
            )}
            {status.needs_workspace && !showWorkspacePicker && (
              <p className="mt-2 text-sm font-semibold text-[#7B68EE]">
                Account connected — select a workspace to finish setup.
              </p>
            )}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="mt-6 flex items-center gap-2 text-sm text-[#6b7080]">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : showWorkspacePicker && userId ? (
        <div className="mt-6">
          <ClickUpWorkspacePicker
            userId={userId}
            onComplete={onWorkspaceComplete}
            onCancel={() => {
              setShowWorkspacePicker(false)
              clearClickUpParam()
            }}
          />
        </div>
      ) : status.connected ? (
        <div className="mt-6 space-y-4">
          {preview && (
            <pre className="max-h-48 overflow-auto rounded-lg border border-[#eceef4] bg-[#f8f9fb] p-4 text-xs text-[#464554] whitespace-pre-wrap">
              {preview}
            </pre>
          )}
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setShowWorkspacePicker(true)}
              disabled={connecting}
              className="rounded-lg border border-[#dfe2e8] px-4 py-2 text-sm font-semibold text-[#464554] hover:bg-[#f5f5f8]"
            >
              Change workspace
            </button>
            <button
              type="button"
              onClick={() => void disconnect()}
              disabled={connecting}
              className="flex items-center gap-2 rounded-lg border border-[#dfe2e8] px-4 py-2 text-sm font-semibold text-[#6b7080] hover:bg-[#f5f5f8] disabled:opacity-50"
            >
              {connecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unlink className="h-4 w-4" />}
              Disconnect
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-6">
          <button
            type="button"
            onClick={() => void connectOAuth()}
            disabled={connecting || !userId}
            className="flex items-center gap-2 rounded-lg bg-[#7B68EE] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#6a58d4] disabled:opacity-60"
          >
            {connecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
            Connect ClickUp
          </button>
          <p className="mt-3 text-sm text-[#6b7080]">
            You&apos;ll sign in on ClickUp, choose which workspaces to allow, then pick one workspace here.
          </p>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      {success && <p className="mt-4 text-sm text-[#2d7a3a]">{success}</p>}
    </div>
  )
}
