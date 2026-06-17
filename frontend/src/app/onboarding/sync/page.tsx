import Link from "next/link";
import { ArrowRight, BarChart3, Calendar, Check, ClipboardCheck, KanbanSquare, ListChecks, Zap } from "lucide-react";

const integrations = [
  { name: "Google Calendar", icon: Calendar, connected: true },
  { name: "ClickUp", icon: ClipboardCheck },
  { name: "Asana", icon: ListChecks },
  { name: "Monday.com", icon: KanbanSquare },
  { name: "Pipedrive", icon: BarChart3 },
  { name: "Zapier", icon: Zap },
];

export default function SyncPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_50%_0%,rgba(70,72,212,0.18),transparent_32%),#f7f9fb] px-5 py-10">
      <section className="w-full max-w-7xl rounded-lg border border-white/80 bg-white/78 px-8 py-28 text-center shadow-[0_28px_90px_rgba(70,72,212,0.12)] backdrop-blur-2xl">
        <div className="mx-auto mb-7 flex w-28 gap-4">
          <span className="h-1.5 flex-1 rounded-full bg-[#dfe2e3]" />
          <span className="h-1.5 flex-1 rounded-full bg-[#4648d4]" />
        </div>
        <div className="text-label mb-5 text-[#4648d4]">Step 2 of 2: Ecosystem Sync</div>
        <h1 className="text-4xl font-extrabold md:text-6xl">Connect your brain&apos;s extensions.</h1>
        <p className="mx-auto mt-6 max-w-3xl text-2xl leading-9 text-[#464554]">
          Sync your calendars and CRMs to give Freeside the context it needs to manage your workflows autonomously.
        </p>

        <div className="mx-auto mt-16 grid max-w-5xl gap-7 md:grid-cols-3">
          {integrations.map((integration) => {
            const Icon = integration.icon;
            return (
              <button
                className={`relative min-h-48 rounded-lg bg-white/82 p-8 shadow-[0_14px_32px_rgba(31,34,54,0.04)] transition hover:shadow-[0_18px_38px_rgba(70,72,212,0.1)] ${
                  integration.connected ? "border border-white" : "border border-transparent"
                }`}
                key={integration.name}
              >
                {integration.connected && (
                  <span className="absolute right-6 top-6 grid h-9 w-9 place-items-center rounded-full bg-[#4648d4] text-white">
                    <Check className="h-6 w-6" />
                  </span>
                )}
                <span className="mx-auto mb-7 grid h-18 w-18 place-items-center rounded-full border-2 border-[#c7c4d7] bg-[#f7f9fb] text-[#4c4c58]">
                  <Icon className={`h-8 w-8 ${integration.connected ? "text-[#4648d4]" : ""}`} />
                </span>
                <span className="block text-2xl font-medium">{integration.name}</span>
                <span className={`mt-2 block text-xl font-bold ${integration.connected ? "text-[#4648d4]" : "text-[#464554]"}`}>
                  {integration.connected ? "Connected" : "Connect"}
                </span>
              </button>
            );
          })}
        </div>

        <div className="mx-auto mt-16 max-w-5xl border-t border-[#dfe2e8] pt-8">
          <Link
            href="/dashboard"
            className="mx-auto flex h-18 max-w-lg items-center justify-center gap-6 rounded-lg bg-[#4648d4] text-2xl font-bold text-white shadow-xl"
          >
            Launch Freeside Workspace <ArrowRight className="h-9 w-9" />
          </Link>
          <Link href="/dashboard" className="mt-8 block text-xl font-bold text-[#464554]">
            Skip for now
          </Link>
        </div>
      </section>
    </main>
  );
}
