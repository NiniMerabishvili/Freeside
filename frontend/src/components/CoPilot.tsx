'use client'

import { useEffect, useRef, useState } from 'react'
import { Bot, Loader2, Send, Sparkles, Zap } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export type CopilotSuggestedTask = {
  title: string
  cognitive_load_score: number
}

type Message = {
  role: 'user' | 'assistant'
  text: string
  type?: string
}

type Props = {
  userId: string | null
  energyLevel: string
  /** When set, the CoPilot auto-sends this message (used for "Break this down" and proactive triggers) */
  triggerMessage?: { text: string; taskId?: string; type?: string } | null
  onTriggerConsumed?: () => void
  onTasksSuggested?: (tasks: CopilotSuggestedTask[]) => void
  /** Fired when user says they are tired — parent should lower energy and reroute */
  onReportLowEnergy?: () => void
}

const TIRED_PATTERN = /\b(tired|exhausted|drained|burned out|burnout|no energy|low energy|feeling rough|can't focus|cannot focus)\b/i

const PROACTIVE: Record<string, string> = {
  low:      "My energy is low right now. What should I focus on to still make progress?",
  high:     "My energy is high today. What's the most impactful thing I should tackle first?",
  balanced: "I'm in balanced mode today. Help me plan a productive session.",
}

export default function CoPilot({ userId, energyLevel, triggerMessage, onTriggerConsumed, onTasksSuggested, onReportLowEnergy }: Props) {
  const [messages, setMessages]   = useState<Message[]>([])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const bottomRef                 = useRef<HTMLDivElement>(null)
  const inputRef                  = useRef<HTMLInputElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Handle trigger messages (breakdown button + proactive intervention)
  useEffect(() => {
    if (!triggerMessage || !userId) return
    sendMessage(triggerMessage.text, triggerMessage.taskId, triggerMessage.type)
    onTriggerConsumed?.()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerMessage])

  const sendMessage = async (text: string, taskId?: string, type?: string) => {
    if (!userId || !text.trim()) return
    const userMsg: Message = { role: 'user', text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    if (TIRED_PATTERN.test(text)) {
      onReportLowEnergy?.()
    }

    try {
      const res = await fetch(`${API}/copilot/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id:      userId,
          message:      text,
          task_id:      taskId ?? null,
          message_type: type ?? 'user_initiated',
        }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', text: data.reply }])
      const suggested = (data.suggested_tasks ?? []) as CopilotSuggestedTask[]
      if (suggested.length > 0) {
        onTasksSuggested?.(suggested)
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: 'I had trouble connecting. Please check that the backend is running.',
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input.trim())
  }

  const isEmpty = messages.length === 0

  return (
    <aside className="flex h-full flex-col border-l border-[#eceef4] bg-white">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-[#eceef4] px-5 py-4">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#f0e5fb]">
          <Bot className="h-4 w-4 text-[#8127cf]" />
        </div>
        <div>
          <p className="text-sm font-bold text-[#191c1e]">AI Co-Pilot</p>
          <p className="text-xs text-[#6b7080]">
            {energyLevel ? `${energyLevel} energy active` : 'Waiting for check-in'}
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {isEmpty && (
          <div className="space-y-3">
            <div className="flex gap-2.5">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[#8127cf]" />
              <p className="text-sm text-[#2d2d40] leading-relaxed">
                {energyLevel
                  ? { high: "You're in High Energy mode — I've prioritised your deep work tasks.", balanced: "Balanced mode. Great for meetings and regular tasks. Need help breaking something down?", low: "Low energy detected. Let me help you find something light to keep moving." }[energyLevel] ?? "I'm your AI Co-Pilot. Ask me anything about your tasks or energy."
                  : "Set your energy level above to activate task routing, then ask me anything."}
              </p>
            </div>

            {/* Quick-action chips */}
            {energyLevel && userId && (
              <div className="flex flex-wrap gap-2 pl-6">
                {[
                  { label: "Plan my day", type: "user_initiated" },
                  { label: "What should I do first?", type: "user_initiated" },
                  { label: `I'm feeling ${energyLevel}. Help me.`, type: "proactive" },
                ].map(chip => (
                  <button
                    key={chip.label}
                    onClick={() => sendMessage(chip.label, undefined, chip.type)}
                    disabled={loading}
                    className="rounded-full border border-[#e0d9f7] bg-[#f6f4ff] px-3 py-1 text-xs font-medium text-[#4648d4] transition hover:bg-[#ebe8ff] disabled:opacity-40"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'assistant' && (
              <div className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#f0e5fb]">
                <Zap className="h-3 w-3 text-[#8127cf]" />
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'rounded-tr-sm bg-[#4648d4] text-white'
                  : 'rounded-tl-sm bg-[#f4f3ff] text-[#2d2d40]'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-2.5">
            <div className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#f0e5fb]">
              <Zap className="h-3 w-3 text-[#8127cf]" />
            </div>
            <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-[#f4f3ff] px-3.5 py-3">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#8127cf] [animation-delay:0ms]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#8127cf] [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#8127cf] [animation-delay:300ms]" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-[#eceef4] px-4 py-3">
        <div className="flex items-center gap-2 rounded-xl border border-[#d7d9e1] bg-[#fafbfc] px-3 py-2 focus-within:border-[#8127cf] focus-within:ring-1 focus-within:ring-[#8127cf]/20">
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={userId ? "Ask me anything…" : "Sign in to chat"}
            disabled={!userId || loading}
            className="flex-1 bg-transparent text-sm text-[#191c1e] outline-none placeholder:text-[#adb0bb] disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!userId || !input.trim() || loading}
            className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-[#8127cf] text-white transition hover:bg-[#6d1fb3] disabled:opacity-40"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
          </button>
        </div>
      </form>
    </aside>
  )
}
