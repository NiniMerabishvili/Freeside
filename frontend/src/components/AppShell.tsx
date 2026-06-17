'use client'

import Link from "next/link"
import type { ReactNode } from "react"
import {
  BarChart3,
  CircleHelp,
  Home,
  LogOut,
  Plus,
  Settings,
  Zap,
} from "lucide-react"
import { supabase } from "@/lib/supabase"

type AppShellProps = {
  active: "home" | "focus" | "analytics" | "settings"
  children: ReactNode
  rightRail?: ReactNode
}

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: Home, key: "home" },
  { label: "Focus Zone", href: "/dashboard", icon: Zap, key: "focus" },
  { label: "Analytics", href: "/insights", icon: BarChart3, key: "analytics" },
] as const

export default function AppShell({ active, children, rightRail }: AppShellProps) {
  const handleSignOut = async () => {
    await supabase.auth.signOut()
    window.location.href = '/login'
  }

  return (
    <div className="min-h-screen bg-[#f7f9fb] text-[#191c1e]">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 z-30 hidden h-screen w-72 flex-col border-r border-[#eceef4] bg-white px-5 py-7 shadow-sm lg:flex">
        <Link href="/" className="mb-10 flex items-center gap-3">
          <Zap className="h-7 w-7 text-[#4648d4]" strokeWidth={2.4} />
          <span className="text-xl font-extrabold text-[#4648d4]">Freeside</span>
        </Link>

        <button className="mb-8 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#4648d4] text-sm font-bold text-white shadow-[0_6px_18px_rgba(70,72,212,0.22)] transition hover:bg-[#3f3dc6]">
          <Plus className="h-5 w-5" />
          New Task
        </button>

        <nav className="flex flex-1 flex-col gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = item.key === active
            return (
              <Link
                key={item.label}
                href={item.href}
                className={`flex h-11 items-center gap-3 rounded-lg px-4 text-sm font-semibold transition ${
                  isActive
                    ? "bg-[#e8e7ff] text-[#4648d4]"
                    : "text-[#4a4a58] hover:bg-[#f4f4f8]"
                }`}
              >
                <Icon className="h-5 w-5" strokeWidth={2} />
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="border-t border-[#eceef4] pt-5 space-y-1">
          <Link
            href="#"
            className="flex h-11 items-center gap-3 rounded-lg px-4 text-sm font-semibold text-[#4a4a58] hover:bg-[#f4f4f8]"
          >
            <CircleHelp className="h-5 w-5" strokeWidth={2} />
            Help
          </Link>
          <Link
            href="/settings"
            className={`flex h-11 items-center gap-3 rounded-lg px-4 text-sm font-semibold transition ${
              active === "settings" ? "bg-[#e8e7ff] text-[#4648d4]" : "text-[#4a4a58] hover:bg-[#f4f4f8]"
            }`}
          >
            <Settings className="h-5 w-5" strokeWidth={2} />
            Settings
          </Link>
          <button
            onClick={handleSignOut}
            className="flex h-11 w-full items-center gap-3 rounded-lg px-4 text-sm font-semibold text-[#4a4a58] hover:bg-[#f4f4f8]"
          >
            <LogOut className="h-5 w-5" strokeWidth={2} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-72">
        <main className={rightRail ? "grid min-h-screen 2xl:grid-cols-[1fr_380px]" : "min-h-screen"}>
          <section>{children}</section>
          {rightRail}
        </main>
      </div>
    </div>
  )
}
