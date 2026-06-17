import {
  Award,
  CircleUserRound,
  Flag,
  Lock,
  Medal,
  Moon,
  Save,
  Settings2,
  Sun,
  Sunrise,
  Umbrella,
  UserRound,
} from "lucide-react";
import AppShell from "@/components/AppShell";

const focusTimes = [
  ["Early Bird", "5am - 9am", Sunrise, false],
  ["Morning", "9am - 1pm", Sun, true],
  ["Afternoon", "1pm - 5pm", Umbrella, false],
  ["Night Owl", "8pm - 2am", Moon, false],
] as const;

const badges = [
  ["Deep Diver", "bg-[#dbeafe] text-[#3377f6]", Medal],
  ["Early Riser", "bg-[#fff1b8] text-[#d88a00]", Sunrise],
  ["Architect", "bg-[#e4e8ff] text-[#6470ff]", Award],
  ["Sprinter", "bg-[#ccf6df] text-[#11a96b]", Flag],
] as const;

export default function SettingsPage() {
  return (
    <AppShell active="settings">
      <div className="min-h-screen bg-[linear-gradient(120deg,#fbfcff,#f2f5fa)] px-6 py-10 md:px-12 lg:px-16">
        <div className="mb-12 flex justify-end gap-4">
          <button className="rounded-lg border border-[#c7c4d7] bg-white px-8 py-3 text-lg font-bold text-[#464554]">Cancel</button>
          <button className="flex items-center gap-3 rounded-lg bg-[#4648d4] px-8 py-3 text-lg font-bold text-white shadow-lg">
            <Save className="h-5 w-5" /> Save Changes
          </button>
        </div>

        <div className="mx-auto grid max-w-[1380px] gap-10 2xl:grid-cols-[1.2fr_.8fr]">
          <section className="space-y-10">
            <article className="ui-card rounded-lg p-12">
              <h1 className="mb-10 flex items-center gap-5 text-4xl font-extrabold">
                <UserRound className="h-8 w-8 text-[#4648d4]" /> Profile Overview
              </h1>
              <div className="grid gap-12 md:grid-cols-[160px_1fr]">
                <div className="grid h-36 w-36 place-items-center rounded-full border-8 border-white bg-[#e2e3e8] shadow-lg">
                  <CircleUserRound className="h-14 w-14 text-[#6f7180]" />
                </div>
                <div className="space-y-6">
                  <label className="block">
                    <span className="mb-2 block text-lg font-bold text-[#464554]">Full Name</span>
                    <input className="h-14 w-full rounded-lg border border-[#c7c4d7] bg-white/60 px-5 text-xl outline-none" defaultValue="Dr. Alex Vance" />
                  </label>
                  <label className="block">
                    <span className="mb-2 block text-lg font-bold text-[#464554]">Productive Day Description</span>
                    <textarea
                      className="h-28 w-full resize-none rounded-lg border border-[#c7c4d7] bg-white/60 px-5 py-3 text-xl leading-8 outline-none"
                      defaultValue="Deep work blocks focusing on complex system architecture, interrupted only by brief analytical reviews and a strong"
                    />
                  </label>
                </div>
              </div>
            </article>

            <article className="ui-card rounded-lg p-12">
              <h2 className="mb-10 flex items-center gap-5 text-4xl font-extrabold">
                <Settings2 className="h-8 w-8 text-[#8127cf]" /> Focus Preferences
              </h2>
              <div className="rounded-lg border border-[#dfe2e8] bg-white p-7">
                <h3 className="text-2xl font-medium">Peak Focus Time</h3>
                <p className="mt-2 text-lg text-[#464554]">When are you most cognitively alert?</p>
                <div className="mt-7 grid gap-4 md:grid-cols-4">
                  {focusTimes.map(([label, time, Icon, active]) => (
                    <button
                      className={`rounded-lg border p-5 text-center ${
                        active ? "border-[#4648d4] bg-[#f5f4ff] text-[#4648d4]" : "border-[#c7c4d7] bg-white"
                      }`}
                      key={label}
                    >
                      <Icon className="mx-auto mb-4 h-7 w-7" />
                      <div className="text-lg font-bold text-[#191c1e]">{label}</div>
                      <div className="mt-1 text-sm text-[#464554]">{time}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-8 rounded-lg border border-[#dfe2e8] bg-white p-7">
                <h3 className="mb-6 text-2xl font-medium">Notification Intensity</h3>
                <div className="space-y-6">
                  {[
                    ["Focus Mode Interruption (Urgent Only)", true],
                    ["Daily Digest Email", false],
                  ].map(([label, on]) => (
                    <div className="flex items-center justify-between text-xl text-[#464554]" key={String(label)}>
                      <span>{label}</span>
                      <span className={`flex h-9 w-16 items-center rounded-full p-1 ${on ? "justify-end bg-[#4648d4]" : "justify-start bg-[#dfe2e3]"}`}>
                        <span className="h-7 w-7 rounded-full bg-white shadow-sm" />
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </article>
          </section>

          <section className="space-y-10">
            <article className="ui-card rounded-lg p-12">
              <h2 className="mb-8 flex items-center gap-5 text-4xl font-extrabold">
                <Flag className="h-8 w-8 text-[#4648d4]" /> Performance Status
              </h2>
              <div className="mb-10 grid gap-6 md:grid-cols-2">
                <div className="rounded-lg bg-white p-7 text-center shadow-sm">
                  <div className="text-label text-[#464554]">Current Level</div>
                  <div className="mt-4 text-7xl font-extrabold text-[#4648d4]">42</div>
                  <div className="mx-auto mt-5 h-3 w-32 rounded-full bg-[#dfe2e3]">
                    <div className="h-full w-[78%] rounded-full bg-[linear-gradient(90deg,#4648d4,#8127cf)]" />
                  </div>
                  <p className="mt-3 text-[#464554]">8,450 / 10,000 XP</p>
                </div>
                <div className="rounded-lg bg-white p-7 text-center shadow-sm">
                  <div className="text-label text-[#464554]">Focus Streak</div>
                  <div className="mt-4 text-7xl font-extrabold text-[#ff7a1a]">14</div>
                  <p className="mt-6 text-[#464554]">Days in Focus Zone</p>
                </div>
              </div>
              <div className="mb-5 flex justify-between text-lg font-bold">
                <span className="text-[#464554]">Cognitive Load (7 Days)</span>
                <span className="text-[#1f22f0]">Optimal</span>
              </div>
              <div className="flex h-28 items-end gap-2">
                {[34, 52, 70, 84, 43, 26, 62].map((height, index) => (
                  <div
                    className={`flex-1 rounded-t ${index === 3 ? "bg-[#b574e2]" : "bg-[#9697df]"}`}
                    key={height}
                    style={{ height: `${height}%`, opacity: index === 0 || index === 5 ? 0.4 : 1 }}
                  />
                ))}
              </div>
            </article>

            <article className="ui-card rounded-lg p-12">
              <div className="mb-8 flex items-center justify-between">
                <h2 className="flex items-center gap-5 text-4xl font-extrabold">
                  <Medal className="h-8 w-8 text-[#8127cf]" /> Evidence Badges
                </h2>
                <a className="text-lg font-bold text-[#4648d4]" href="#">
                  View All
                </a>
              </div>
              <div className="grid grid-cols-3 gap-5">
                {badges.map(([label, color, Icon]) => (
                  <div className="rounded-lg border border-[#dfe2e8] bg-white p-6 text-center shadow-sm" key={label}>
                    <span className={`mx-auto mb-5 grid h-16 w-16 place-items-center rounded-full ${color}`}>
                      <Icon className="h-8 w-8" />
                    </span>
                    <div className="text-sm font-bold">{label}</div>
                  </div>
                ))}
                {[1, 2].map((item) => (
                  <div className="grid min-h-32 place-items-center rounded-lg border border-dashed border-[#dfe2e8] text-[#b8bac4]" key={item}>
                    <Lock className="h-9 w-9" />
                  </div>
                ))}
              </div>
            </article>

            <article className="ui-card rounded-lg p-7">
              <h2 className="text-xl font-bold text-[#ba1a1a]">DANGER ZONE</h2>
              <p className="mt-4 text-lg text-[#464554]">Permanently erase your account and all associated productivity data.</p>
              <button className="mt-6 h-12 w-full rounded-lg border border-[#e25151] bg-white text-lg font-bold text-[#ba1a1a]">
                Delete Account
              </button>
            </article>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
