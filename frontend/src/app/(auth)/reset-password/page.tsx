'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, AlertCircle, Check, ShieldCheck } from 'lucide-react'
import { supabase } from '@/lib/supabase'

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'One uppercase letter', test: (p: string) => /[A-Z]/.test(p) },
  { label: 'One number', test: (p: string) => /\d/.test(p) },
]

export default function ResetPasswordPage() {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [sessionReady, setSessionReady] = useState(false)

  // Supabase emits a PASSWORD_RECOVERY event when the reset link is opened.
  // We wait for it before allowing the form to submit.
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY' || event === 'SIGNED_IN') {
        setSessionReady(true)
      }
    })

    // Also check if session already exists (user navigated here after callback)
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) setSessionReady(true)
    })

    return () => subscription.unsubscribe()
  }, [])

  const passwordValid = PASSWORD_RULES.every((r) => r.test(password))
  const matches = password === confirm && confirm.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!passwordValid || !matches) return
    setError('')
    setLoading(true)

    try {
      const { error: err } = await supabase.auth.updateUser({ password })
      if (err) throw err
      setDone(true)
      setTimeout(() => router.push('/dashboard'), 2500)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not update password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const pageWrapper = (children: React.ReactNode) => (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_10%_0%,rgba(70,72,212,0.13),transparent_32%),radial-gradient(circle_at_85%_15%,rgba(129,39,207,0.09),transparent_28%),#f7f9fb] px-4 py-10">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <div className="grid h-8 w-8 rotate-45 place-items-center rounded bg-[#4648d4]">
            <div className="h-3 w-3 -rotate-45 bg-white" />
          </div>
          <span className="font-serif text-lg font-bold text-[#191c1e]">Freeside</span>
        </Link>
        <section className="rounded-2xl border border-white/70 bg-white/80 p-8 shadow-[0_28px_90px_rgba(70,72,212,0.13)] backdrop-blur-2xl">
          {children}
        </section>
      </div>
    </main>
  )

  if (done) {
    return pageWrapper(
      <div className="text-center">
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-xl bg-green-100 text-green-600">
          <ShieldCheck className="h-7 w-7" />
        </div>
        <h1 className="font-serif text-2xl font-bold text-[#191c1e]">Password updated!</h1>
        <p className="mt-3 text-sm text-[#6b7080]">
          Your password has been changed. Redirecting you to the dashboard…
        </p>
      </div>
    )
  }

  if (!sessionReady) {
    return pageWrapper(
      <div className="text-center">
        <div className="mx-auto mb-5 h-10 w-10 animate-spin rounded-full border-4 border-[#e2e3ec] border-t-[#4648d4]" />
        <p className="text-sm text-[#6b7080]">Verifying your reset link…</p>
        <p className="mt-4 text-xs text-[#9ea0b0]">
          Link not working?{' '}
          <Link href="/forgot-password" className="text-[#4648d4] hover:underline">
            Request a new one
          </Link>
        </p>
      </div>
    )
  }

  return pageWrapper(
    <>
      <div className="mb-7 text-center">
        <h1 className="font-serif text-3xl font-bold text-[#191c1e]">Set new password</h1>
        <p className="mt-2 text-sm text-[#6b7080]">Choose a strong password for your account.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* New password */}
        <div>
          <label htmlFor="new-password" className="mb-1.5 block text-sm font-semibold text-[#2f3040]">
            New password
          </label>
          <div className="relative">
            <input
              id="new-password"
              type={showPassword ? 'text' : 'password'}
              required
              autoFocus
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="h-12 w-full rounded-lg border border-[#c7c4d7] bg-white px-4 pr-12 text-base outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9ea0b0] hover:text-[#464554] transition"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>

          {password && (
            <ul className="mt-3 space-y-1.5">
              {PASSWORD_RULES.map((rule) => (
                <li
                  key={rule.label}
                  className={`flex items-center gap-2 text-xs transition-colors ${
                    rule.test(password) ? 'text-green-600' : 'text-[#9ea0b0]'
                  }`}
                >
                  <Check className={`h-3.5 w-3.5 ${rule.test(password) ? 'opacity-100' : 'opacity-30'}`} />
                  {rule.label}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Confirm password */}
        <div>
          <label htmlFor="confirm-password" className="mb-1.5 block text-sm font-semibold text-[#2f3040]">
            Confirm password
          </label>
          <div className="relative">
            <input
              id="confirm-password"
              type={showConfirm ? 'text' : 'password'}
              required
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              className={`h-12 w-full rounded-lg border bg-white px-4 pr-12 text-base outline-none placeholder:text-[#9ea0b0] transition focus:ring-2 ${
                confirm && !matches
                  ? 'border-red-400 focus:border-red-400 focus:ring-red-400/20'
                  : confirm && matches
                  ? 'border-green-400 focus:border-green-400 focus:ring-green-400/20'
                  : 'border-[#c7c4d7] focus:border-[#4648d4] focus:ring-[#4648d4]/20'
              }`}
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowConfirm((v) => !v)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9ea0b0] hover:text-[#464554] transition"
              aria-label={showConfirm ? 'Hide password' : 'Show password'}
            >
              {showConfirm ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>
          {confirm && !matches && (
            <p className="mt-1.5 text-xs text-red-600">Passwords don&apos;t match.</p>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || !passwordValid || !matches}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Updating…' : 'Update password'}
        </button>
      </form>
    </>
  )
}
