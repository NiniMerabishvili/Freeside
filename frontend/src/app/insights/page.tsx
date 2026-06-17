import { Calendar, Download, Info, TrendingUp } from "lucide-react";
import AppShell from "@/components/AppShell";

export default function InsightsPage() {
  return (
    <AppShell active="analytics">
      <div className="min-h-screen bg-[radial-gradient(circle_at_45%_0%,rgba(70,72,212,0.18),transparent_26%),#f7f9fb] px-6 py-10 md:px-12 lg:px-16">
        <div className="mx-auto max-w-[1500px]">
          <div className="mb-10 flex flex-col justify-between gap-6 2xl:flex-row 2xl:items-start">
            <div>
              <h1 className="text-5xl font-extrabold leading-tight md:text-7xl">Evidence & Performance</h1>
              <p className="mt-3 text-2xl font-semibold text-[#464554]">Academic rigor applied to your workflow efficiency.</p>
            </div>
            <div className="flex gap-5">
              <button className="flex h-14 items-center gap-4 rounded-lg border border-[#232333] bg-white px-8 text-lg font-bold">
                <Calendar className="h-6 w-6" /> This Week
              </button>
              <button className="flex h-14 items-center gap-4 rounded-lg bg-[#4648d4] px-8 text-lg font-bold text-white shadow-lg">
                <Download className="h-6 w-6" /> Export Report
              </button>
            </div>
          </div>

          <section className="mb-8 grid gap-8 2xl:grid-cols-3">
            <article className="rounded-lg border border-[#dfe2e8] bg-white p-12 shadow-[0_34px_75px_rgba(70,72,212,0.28)]">
              <div className="text-label mb-5 text-[#464554]">Productivity Gain</div>
              <div className="flex items-end gap-4 text-[#4648d4]">
                <span className="text-7xl font-extrabold">+24.8%</span>
                <TrendingUp className="mb-4 h-10 w-10" />
              </div>
              <p className="mt-6 text-2xl text-[#464554]">Versus 30-day moving average.</p>
              <div className="my-12 h-px bg-[#dfe2e8]" />
              <div className="flex justify-between text-xl font-bold">
                <span className="text-[#464554]">Cognitive Load Index</span>
                <span className="text-[#4648d4]">Optimal</span>
              </div>
            </article>

            <article className="rounded-lg border border-[#dfe2e8] bg-white p-12 shadow-[0_22px_45px_rgba(0,0,0,0.08)]">
              <div className="text-label mb-7 text-[#464554]">Peak Focus Times</div>
              <div className="space-y-7">
                <div>
                  <div className="mb-2 flex justify-between text-2xl font-bold">
                    <span>08:00 - 11:30 AM</span>
                    <span className="text-[#4648d4]">High Energy</span>
                  </div>
                  <div className="h-3 rounded-full bg-[#dfe2e3]">
                    <div className="h-full w-[86%] rounded-full bg-[#4648d4]" />
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex justify-between text-2xl font-bold">
                    <span>02:00 - 04:00 PM</span>
                    <span className="text-[#8127cf]">Moderate</span>
                  </div>
                  <div className="h-3 rounded-full bg-[#dfe2e3]">
                    <div className="h-full w-[61%] rounded-full bg-[#8127cf]" />
                  </div>
                </div>
              </div>
              <p className="mt-28 flex gap-3 text-xl font-bold leading-5 text-[#464554]">
                <Info className="h-5 w-5 shrink-0" /> Based on biometric and keystroke analysis.
              </p>
            </article>

            <article className="rounded-lg border border-[#dfe2e8] bg-white p-12 text-center shadow-[0_22px_45px_rgba(0,0,0,0.08)]">
              <div className="text-label mb-7 text-left text-[#464554]">Burnout Prevention</div>
              <div className="relative mx-auto grid h-40 w-40 place-items-center rounded-full border-[8px] border-[#dfe2e3]">
                <div className="absolute inset-[-8px] rounded-full border-[8px] border-[#8127cf] border-l-transparent border-b-transparent" />
                <span className="text-5xl font-extrabold">82%</span>
              </div>
              <p className="mx-auto mt-10 max-w-sm text-2xl leading-9 text-[#464554]">
                Recovery metrics are stable. No immediate intervention required.
              </p>
            </article>
          </section>

          <section className="rounded-lg bg-white p-10 shadow-[0_28px_65px_rgba(0,0,0,0.12)]">
            <div className="mb-12 flex flex-col justify-between gap-5 md:flex-row md:items-center">
              <h2 className="text-4xl font-extrabold">Task Completion Rate vs. Energy Levels</h2>
              <div className="flex gap-8 text-xl font-bold text-[#464554]">
                <span className="flex items-center gap-3"><i className="h-5 w-5 rounded-full bg-[#4648d4]" /> Task Volume</span>
                <span className="flex items-center gap-3"><i className="h-5 w-5 rounded-full bg-[#8127cf]" /> Energy Capacity</span>
              </div>
            </div>

            <svg className="h-[430px] w-full" viewBox="0 0 1300 430" role="img" aria-label="Task completion and energy level chart">
              {[0, 1, 2, 3, 4].map((line) => (
                <line
                  key={line}
                  x1="35"
                  x2="1280"
                  y1={390 - line * 90}
                  y2={390 - line * 90}
                  stroke="#eceef4"
                  strokeWidth="1"
                />
              ))}
              <line x1="35" x2="35" y1="30" y2="390" stroke="#dfe2e8" strokeWidth="2" />
              <path d="M35 315 L250 235 L470 270 L690 120 L900 155 L1280 80 L1280 390 L35 390 Z" fill="#4648d4" opacity=".08" />
              <path d="M35 315 L250 235 L470 270 L690 120 L900 155 L1280 80" fill="none" stroke="#4648d4" strokeLinecap="round" strokeLinejoin="round" strokeWidth="9" />
              <path d="M35 275 C170 240 230 205 360 185 C520 160 665 235 780 208 C930 170 1000 60 1280 120" fill="none" stroke="#8127cf" strokeDasharray="55 32" strokeLinecap="round" strokeWidth="9" />
              <circle cx="690" cy="120" r="27" fill="white" stroke="#4648d4" strokeWidth="10" />
              <circle cx="1000" cy="70" r="27" fill="white" stroke="#8127cf" strokeWidth="10" />
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day, index) => (
                <text fill="#8b8d98" fontSize="20" fontWeight="700" key={day} x={45 + index * 240} y="420">
                  {day}
                </text>
              ))}
              {[0, 25, 50, 75, 100].map((tick, index) => (
                <text fill="#8b8d98" fontSize="20" fontWeight="700" key={tick} x="0" y={395 - index * 90}>
                  {tick}
                </text>
              ))}
            </svg>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
