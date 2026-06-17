'use client'

import { useState, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Eye, EyeOff, AlertCircle, ArrowRight } from 'lucide-react'
import { supabase } from '@/lib/supabase'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const next = searchParams.get('next') || '/dashboard'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { error: authErr } = await supabase.auth.signInWithPassword({ email, password })
      if (authErr) throw authErr

      // Check onboarding status
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        const { data: profile } = await supabase
          .from('profiles')
          .select('onboarding_completed')
          .eq('id', user.id)
          .single()

        if (!profile?.onboarding_completed) {
          router.push('/onboarding')
        } else {
          router.push(next)
        }
      }
    } catch (e: unknown) {
      setError(
        e instanceof Error
          ? e.message.replace('Invalid login credentials', 'Incorrect email or password.')
          : 'Login failed. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleLogin} className="space-y-5">
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
        <div className="mb-1.5 flex items-center justify-between">
          <label htmlFor="password" className="text-sm font-semibold text-[#2f3040]">
            Password
          </label>
          <Link href="/forgot-password" className="text-xs text-[#4648d4] hover:underline">
            Forgot password?
          </Link>
        </div>
        <div className="relative">
          <input
            id="password"
            type={showPassword ? 'text' : 'password'}
            required
            autoComplete="current-password"
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
      </div>

      <button
        type="submit"
        disabled={loading || !email || !password}
        className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-base font-bold text-white shadow-lg transition hover:bg-[#3a3cc0] disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Signing in…' : <>Sign in <ArrowRight className="h-4 w-4" /></>}
      </button>
    </form>
  )
}

export default function LoginPage() {
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
            <h1 className="font-serif text-3xl font-bold text-[#191c1e]">Welcome back</h1>
            <p className="mt-2 text-sm text-[#6b7080]">Sign in to your Freeside account</p>
          </div>

          <Suspense fallback={<div className="h-64 animate-pulse rounded-lg bg-[#f0f1f3]" />}>
            <LoginForm />
          </Suspense>

          <p className="mt-6 text-center text-sm text-[#6b7080]">
            Don&apos;t have an account?{' '}
            <Link href="/signup" className="font-semibold text-[#4648d4] hover:underline">
              Sign up free
            </Link>
          </p>
        </section>
      </div>
    </main>
  )
}
