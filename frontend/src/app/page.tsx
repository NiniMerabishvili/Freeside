import Link from "next/link";
import { ArrowRight, CheckCircle2, CircleX, Network, Zap } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen overflow-hidden bg-[#f7f9fb] text-[#191c1e]">
      <header className="sticky top-0 z-30 border-b border-[#e7e9f0] bg-white/74 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <div className="grid h-8 w-8 rotate-45 place-items-center rounded bg-[#4648d4]">
              <div className="h-3 w-3 -rotate-45 bg-white" />
            </div>
            <span className="font-serif text-lg font-bold">Freeside</span>
          </Link>
          <nav className="hidden items-center gap-10 text-sm font-medium text-[#191c1e] md:flex">
            <a href="#methodology">Methodology</a>
            <a href="#intelligence">Intelligence</a>
            <a href="#copilot">Co-Pilot</a>
            <a href="#pricing">Pricing</a>
          </nav>
          <div className="flex items-center gap-5">
            <Link className="hidden text-sm font-medium text-[#191c1e] sm:block" href="/login">
              Log In
            </Link>
            <Link className="rounded-full bg-[#4648d4] px-6 py-2 text-sm font-bold text-white shadow-lg" href="/signup">
              Start for Free
            </Link>
          </div>
        </div>
      </header>

      <section className="relative bg-[linear-gradient(90deg,#f1f2ff_0%,#fbfcff_55%,#eef2f7_100%)] px-6 pb-24 pt-28 text-center">
        <div className="mx-auto max-w-6xl">
          <div className="mx-auto mb-7 inline-flex items-center gap-2 rounded-full border border-[#dfe2ee] bg-white/65 px-4 py-2 text-xs text-[#464554]">
            <span className="h-2 w-2 rounded-full bg-[#4648d4]" />
            Freeside Intelligence 2.0 is live
          </div>
          <h1 className="mx-auto max-w-3xl font-serif text-4xl font-bold leading-tight md:text-6xl">
            Work in sync with your energy,
            <br className="hidden md:block" /> not against it.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-[#464554]">
            Freeside AI maps your cognitive load and automatically restructures your workflow. Achieve peak focus,
            eliminate burnout, and execute with precision.
          </p>
          <div className="mx-auto mt-8 flex max-w-xs flex-col items-center gap-4 sm:flex-row sm:max-w-sm">
            <Link
              className="h-12 w-full rounded-full bg-[#4648d4] px-8 text-sm font-bold text-white shadow-xl flex items-center justify-center"
              href="/signup"
            >
              Start for Free
            </Link>
            <Link
              className="h-12 w-full rounded-full border border-[#d7d9e1] bg-white px-8 text-sm font-bold text-[#191c1e] flex items-center justify-center"
              href="/login"
            >
              Log In
            </Link>
          </div>

          <div className="mx-auto mt-20 max-w-5xl rounded-lg border border-white/70 bg-white/78 p-5 text-left shadow-[0_28px_70px_rgba(28,31,48,0.16)] backdrop-blur-2xl">
            <div className="mb-5 flex gap-2">
              <span className="h-3 w-3 rounded-full bg-[#ff4b3e]" />
              <span className="h-3 w-3 rounded-full bg-[#f4bd42]" />
              <span className="h-3 w-3 rounded-full bg-[#32b65f]" />
            </div>
            <div className="grid gap-8 rounded-lg bg-white/50 p-6 md:grid-cols-[260px_1fr]">
              <div className="hidden border-r border-[#e2e5ed] pr-8 md:block">
                <div className="mb-8 h-8 w-44 rounded bg-[#eceef0]" />
                <div className="mb-3 h-3 w-28 rounded bg-[#eceef0]" />
                <div className="mb-3 h-3 w-40 rounded bg-[#eceef0]" />
                <div className="mb-3 h-3 w-32 rounded bg-[#eceef0]" />
                <div className="mt-12 h-4 w-36 overflow-hidden rounded bg-[#d9d9f4]">
                  <div className="h-full w-2/3 rounded bg-[#8c86e8]" />
                </div>
              </div>
              <div>
                <div className="mb-7 flex items-center justify-between">
                  <div className="h-5 w-48 rounded bg-[#eceef0]" />
                  <div className="h-8 w-8 rounded-full bg-[#eceef0]" />
                </div>
                <div className="grid gap-5 md:grid-cols-2">
                  <div className="h-32 rounded-lg border border-[#eceef5] bg-white p-5 shadow-sm">
                    <div className="h-4 w-24 rounded bg-[#eceef0]" />
                    <div className="mt-16 h-1 rounded bg-[#eceef0]">
                      <div className="h-full w-3/4 rounded bg-[#8127cf]" />
                    </div>
                  </div>
                  <div className="grid h-32 place-items-center rounded-lg border border-[#eceef5] bg-white shadow-sm">
                    <div className="h-16 w-16 rounded-full border-4 border-[#dbddff] border-t-[#4648d4]" />
                  </div>
                </div>
                <div className="mt-5 rounded-lg border border-[#eceef5] bg-white p-4 shadow-sm">
                  <div className="mb-3 flex items-center gap-3">
                    <div className="h-4 w-4 rounded border border-[#c7c4d7]" />
                    <div className="h-3 w-2/3 rounded bg-[#eceef0]" />
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-4 w-4 rounded bg-[#c0c1ff]" />
                    <div className="h-3 w-1/2 rounded bg-[#eceef0]" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-white px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <h2 className="font-serif text-3xl font-bold">Evolution from Chaos to Clarity</h2>
            <p className="mt-3 text-[#464554]">Stop managing tasks. Start managing your cognitive energy.</p>
          </div>
          <div className="grid gap-10 md:grid-cols-2">
            <div className="rounded-lg border border-[#dfe2e8] bg-[#f0f1f3] p-8">
              <div className="mb-6 flex items-center gap-3 font-serif text-xl font-bold">
                <CircleX className="h-5 w-5 text-[#ba1a1a]" /> Traditional Chaos
              </div>
              <ul className="space-y-6 text-sm text-[#464554]">
                <li>
                  <span className="font-bold text-[#191c1e]">Overwhelming Lists</span>
                  <br /> Endless backlogs that create anxiety and decision fatigue.
                </li>
                <li>
                  <span className="font-bold text-[#191c1e]">Energy Blindness</span>
                  <br /> Tackling deep-work tasks when cognitively depleted.
                </li>
              </ul>
            </div>
            <div className="rounded-lg border border-[#c0c1ff] bg-white p-8 shadow-[0_14px_40px_rgba(70,72,212,0.08)]">
              <div className="mb-6 flex items-center gap-3 font-serif text-xl font-bold">
                <CheckCircle2 className="h-5 w-5 text-[#4648d4]" /> Freeside Intelligence
              </div>
              <ul className="space-y-6 text-sm text-[#464554]">
                <li>
                  <span className="font-bold text-[#191c1e]">Micro-Step Breakdown</span>
                  <br /> AI auto-structures massive projects into effortless next actions.
                </li>
                <li>
                  <span className="font-bold text-[#191c1e]">Energy Synchronization</span>
                  <br /> Surfaces the right task precisely when your cognitive state matches it.
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="intelligence" className="bg-[linear-gradient(120deg,#f7f9fb,#f2f2ff)] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <h2 className="font-serif text-3xl font-bold">The Productivity Ecosystem</h2>
            <p className="mt-3 text-[#464554]">Engineered components designed to harmonize with human psychology.</p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="ui-card md:col-span-2 rounded-lg p-8">
              <h3 className="font-serif text-xl font-bold">Energy Intelligence</h3>
              <p className="mt-2 max-w-md text-[#464554]">
                Calibrate your day. We monitor your execution cadence and adapt your schedule dynamically.
              </p>
              <div className="mt-9 flex justify-end">
                <div className="relative grid h-44 w-44 place-items-center rounded-full border-[10px] border-[#e4e5ee]">
                  <div className="absolute inset-[-10px] rounded-full border-[10px] border-[#4648d4] border-l-transparent border-b-transparent" />
                  <div className="text-center">
                    <div className="text-3xl font-bold">74%</div>
                    <div className="text-sm font-bold text-[#464554]">Peak</div>
                  </div>
                </div>
              </div>
            </div>
            <div id="copilot" className="ui-card rounded-lg p-8">
              <div className="mb-8 grid h-11 w-11 place-items-center rounded-lg bg-[#f0dbff] text-[#8127cf]">
                <Zap className="h-6 w-6" />
              </div>
              <h3 className="font-serif text-xl font-bold">AI Co-Pilot</h3>
              <p className="mt-2 text-[#464554]">Instant task decomposition.</p>
              <div className="mt-8 space-y-3">
                {[1, 2, 3].map((item) => (
                  <div className="h-9 rounded bg-[#eceef0]" key={item} />
                ))}
              </div>
            </div>
            <div className="ui-card rounded-lg p-8">
              <h3 className="font-serif text-xl font-bold">Rewarding Progress</h3>
              <p className="mt-2 text-sm text-[#464554]">Gamified momentum. Build streaks and level up your cognitive capacity.</p>
              <div className="mt-8 h-2 rounded bg-[#e2e3ec]">
                <div className="h-full w-3/4 rounded bg-[#4648d4]" />
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 text-center text-sm font-bold">
                <div className="rounded bg-[#f7f9fb] p-3">Streak<br />14</div>
                <div className="rounded bg-[#f7f9fb] p-3">Focus<br />32.5</div>
              </div>
            </div>
            <div className="ui-card relative overflow-hidden rounded-lg p-8 md:col-span-2">
              <h3 className="font-serif text-xl font-bold">Ecosystem Sync</h3>
              <p className="mt-2 max-w-md text-sm text-[#464554]">
                Seamlessly integrates with the tools you already use. Freeside acts as the intelligence layer on top of your existing stack.
              </p>
              <div className="absolute right-12 top-12 hidden items-center gap-6 md:flex">
                <div className="grid h-10 w-10 place-items-center rounded bg-white shadow-md">D</div>
                <div className="grid h-24 w-24 place-items-center rounded-lg bg-white text-[#4648d4] shadow-xl">
                  <Network className="h-9 w-9" />
                </div>
                <div className="grid h-10 w-10 place-items-center rounded bg-white shadow-md">M</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="methodology" className="bg-[#f7f9fb] px-6 py-24">
        <div className="mx-auto grid max-w-6xl items-center gap-12 md:grid-cols-2">
          <div>
            <div className="text-label mb-5 text-[#4648d4]">Methodology</div>
            <h2 className="font-serif text-3xl font-bold">Data-Driven Performance</h2>
            <p className="mt-5 max-w-lg leading-7 text-[#464554]">
              Built on principles of cognitive psychology and behavioral science. Freeside users experience a
              measurable increase in deep-work completion while simultaneously reporting lower levels of burnout and
              stress.
            </p>
            <Link className="mt-8 inline-flex items-center gap-2 text-sm font-bold text-[#4648d4]" href="/insights">
              Read the Research <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="rounded-lg bg-white p-6 shadow-[0_18px_50px_rgba(32,34,55,0.14)]">
            <div className="mb-5 flex justify-between text-sm font-bold">
              <span>Impact Over Time</span>
              <span className="text-[#767586]">Month 1 - 3</span>
            </div>
            <svg className="h-56 w-full" viewBox="0 0 520 220" role="img" aria-label="Impact over time chart">
              <rect width="520" height="220" fill="white" />
              <path d="M30 150 L170 112 L310 68 L490 32" fill="none" stroke="#1f22f0" strokeWidth="4" />
              <path d="M30 70 C160 96 220 128 310 150 C385 170 440 160 490 155" fill="none" stroke="#d64242" strokeDasharray="7 7" strokeWidth="3" />
              <path d="M310 68 L490 32 L490 178 L310 178 Z" fill="#4648d4" opacity=".1" />
            </svg>
          </div>
        </div>
      </section>

      <section id="pricing" className="bg-[linear-gradient(110deg,#f7f9fb,#f1ebff)] px-6 py-24">
        <div className="mx-auto max-w-4xl rounded-lg border border-black/50 bg-[linear-gradient(135deg,#11171b,#252033)] px-8 py-16 text-center text-white shadow-2xl">
          <h2 className="font-serif text-4xl font-bold">Ready to upgrade your operating system?</h2>
          <p className="mt-5">Join high-performers optimizing their output with Freeside Intelligence.</p>
          <div className="mx-auto mt-8 flex max-w-xs justify-center">
            <Link className="h-12 rounded-full bg-white px-10 py-3 text-sm font-bold text-[#191c1e] flex items-center" href="/signup">
              Get Started
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-[#dfe2e8] bg-white px-6 py-7">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-5 text-xs text-[#464554] md:flex-row">
          <div className="flex items-center gap-2 font-serif font-bold text-[#191c1e]">
            <div className="h-4 w-4 rotate-45 bg-[#191c1e]" /> Freeside AI
          </div>
          <div className="flex gap-8">
            <a href="#">Privacy Policy</a>
            <a href="#">Terms of Service</a>
            <a href="#">Scientific Papers</a>
            <a href="#">API Docs</a>
          </div>
          <div>© 2026 Freeside AI. Cognitive energy-aware productivity.</div>
        </div>
      </footer>
    </div>
  );
}
