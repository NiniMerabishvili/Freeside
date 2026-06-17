'use client'

import { useState } from 'react'
import Link from 'next/link'
import { AlertCircle, ArrowLeft, Mail } from 'lucide-react'
import { supabase } from '@/lib/supabase'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
      })
      if (err) throw err
      setSent(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_10%_0%,rgba(70,72,212,0.13),transparent_32%),radial-gradient(circle_at_85%_15%,rgba(129,39,207,0.09),transparent_28%),#f7f9fb] px-4 py-10">
      <div className="w-full max-w-md">
        {/* Logo */}
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <div className="grid h-8 w-8 rotate-45 place-items-center rounded bg-[#4648d4]">
            <div className="h-3 w-3 -rotate-45 bg-white" />
          </div>
          <span className="font-serif text-lg font-bold text-[#191c1e]">Freeside</span>
        </Link>

        <section className="rounded-2xl border border-white/70 bg-white/80 p-8 shadow-[0_28px_90px_rgba(70,72,212,0.13)] backdrop-blur-2xl">
          {sent ? (
            <div className="text-center">
              <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-xl bg-[#ededfc] text-[#4648d4]">
                <Mail className="h-7 w-7" />
              </div>
              <h1 className="font-serif text-2xl font-bold text-[#191c1e]">Check your inbox</h1>
              <p className="mt-3 text-sm leading-6 text-[#6b7080]">
                We sent a password reset link to{' '}
                <span className="font-semibold text-[#2f3040]">{email}</span>.
                It expires in 1 hour.
              </p>
              <p className="mt-4 text-sm text-[#8183a0]">
                Didn&apos;t receive it?{' '}
                <button
                  type="button"
                  onClick={() => setSent(false)}
                  className="font-semibold text-[#4648d4] hover:underline"
                >
                  Try again
                </button>
              </p>
              <Link
                href="/login"
                className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[#6b7080] hover:text-[#464554] transition"
              >
                <ArrowLeft className="h-4 w-4" /> Back to login
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-7">
                <Link
                  href="/login"
                  className="mb-5 inline-flex items-center gap-1.5 text-sm font-medium text-[#6b7080] hover:text-[#464554] transition"
                >
                  <ArrowLeft className="h-4 w-4" /> Back to login
                </Link>
                <h1 className="font-serif text-3xl font-bold text-[#191c1e]">Forgot password?</h1>
                <p className="mt-2 text-sm text-[#6b7080]">
                  Enter your email and we&apos;ll send you a reset link.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-[#2f3040]">
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    autoFocus
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="h-12 w-full rounded-lg border border-[#c7c4d7] bg-white px-4 text-base outline-none placeholder:text-[#9ea0b0] focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20 transition"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !email}
                  className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </main>
  )
}
