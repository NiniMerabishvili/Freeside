'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, AlertCircle, ArrowRight, Check } from 'lucide-react'
import { supabase } from '@/lib/supabase'

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'One uppercase letter', test: (p: string) => /[A-Z]/.test(p) },
  { label: 'One number', test: (p: string) => /\d/.test(p) },
]

export default function SignupPage() {
  const router = useRouter()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const passwordValid = PASSWORD_RULES.every((r) => r.test(password))

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!passwordValid) return
    setError('')
    setLoading(true)

    try {
      const { error: authErr } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      })
      if (authErr) throw authErr

      // Try to sign in immediately (works when email confirmation is disabled in Supabase)
      const { error: loginErr } = await supabase.auth.signInWithPassword({ email, password })

      if (loginErr) {
        // Email confirmation required — show success message
        setDone(true)
      } else {
        router.push('/onboarding')
      }
    } catch (e: unknown) {
      setError(
        e instanceof Error
          ? e.message.replace('User already registered', 'An account with this email already exists.')
          : 'Signup failed. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_10%_0%,rgba(70,72,212,0.13),transparent_32%),radial-gradient(circle_at_85%_15%,rgba(129,39,207,0.09),transparent_28%),#f7f9fb] px-4 py-10">
        <div className="w-full max-w-md">
          <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
            <div className="grid h-8 w-8 rotate-45 place-items-center rounded bg-[#4648d4]">
              <div className="h-3 w-3 -rotate-45 bg-white" />
            </div>
            <span className="font-serif text-lg font-bold text-[#191c1e]">Freeside</span>
          </Link>
          <section className="rounded-2xl border border-white/70 bg-white/80 p-8 text-center shadow-[0_28px_90px_rgba(70,72,212,0.13)] backdrop-blur-2xl">
            <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-xl bg-green-100 text-green-600">
              <Check className="h-7 w-7" />
            </div>
            <h1 className="font-serif text-2xl font-bold text-[#191c1e]">Check your email</h1>
            <p className="mt-3 text-sm leading-6 text-[#6b7080]">
              We sent a confirmation link to <span className="font-semibold text-[#2f3040]">{email}</span>.
              Click the link to activate your account, then come back to sign in.
            </p>
            <Link
              href="/login"
              className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[#4648d4] hover:underline"
            >
              Go to login <ArrowRight className="h-4 w-4" />
            </Link>
          </section>
        </div>
      </main>
    )
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
          <div className="mb-7 text-center">
            <h1 className="font-serif text-3xl font-bold text-[#191c1e]">Create your account</h1>
            <p className="mt-2 text-sm text-[#6b7080]">Start working in sync with your energy</p>
          </div>

          <form onSubmit={handleSignup} className="space-y-5">
            {error && (
              <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-[#2f3040]">
                Email
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

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-semibold text-[#2f3040]">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
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

              {/* Password strength indicators */}
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

            <button
              type="submit"
              disabled={loading || !email || !passwordValid}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating account…' : <>Create account <ArrowRight className="h-4 w-4" /></>}
            </button>

            <p className="text-center text-xs text-[#8183a0]">
              By signing up, you agree to our{' '}
              <a href="#" className="underline hover:text-[#464554]">Terms of Service</a>{' '}
              and{' '}
              <a href="#" className="underline hover:text-[#464554]">Privacy Policy</a>.
            </p>
          </form>

          <p className="mt-6 text-center text-sm text-[#6b7080]">
            Already have an account?{' '}
            <Link href="/login" className="font-semibold text-[#4648d4] hover:underline">
              Sign in
            </Link>
          </p>
        </section>
      </div>
    </main>
  )
}
