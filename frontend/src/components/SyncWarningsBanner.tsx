'use client'

import { AlertTriangle, X } from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'

export type SyncWarning = {
  code: string
  message: string
  integration: 'calendar' | 'clickup' | string
}

type Props = {
  warnings: SyncWarning[]
}

export default function SyncWarningsBanner({ warnings }: Props) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  const visible = warnings.filter(w => !dismissed.has(w.code))
  if (!visible.length) return null

  return (
    <div className="mb-4 space-y-2">
      {visible.map(w => (
        <div
          key={w.code}
          className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
          role="alert"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <div className="min-w-0 flex-1">
            <p>{w.message}</p>
            <Link
              href="/settings"
              className="mt-1 inline-block text-xs font-semibold text-amber-800 underline hover:text-amber-900"
            >
              Open Settings
            </Link>
          </div>
          <button
            type="button"
            onClick={() => setDismissed(prev => new Set(prev).add(w.code))}
            className="shrink-0 rounded p-0.5 text-amber-700 hover:bg-amber-100"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
