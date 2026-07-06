"use client";

import {
  Award,
  Camera,
  CircleUserRound,
  Download,
  Flag,
  Loader2,
  Lock,
  Medal,
  Moon,
  Pencil,
  Save,
  Settings2,
  Sun,
  Sunrise,
  Umbrella,
  UserRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, Suspense } from "react";
import AppShell from "@/components/AppShell";
import ClickUpIntegrationPanel from "@/components/ClickUpIntegrationPanel";
import { supabase } from "@/lib/supabase";
import { effectiveTaskXp } from "@/lib/xp";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type PeakFocus = "early_bird" | "morning" | "afternoon" | "evening";

type ProfileForm = {
  name: string;
  productive_day_description: string;
  peak_focus_time: PeakFocus | "";
};

type NotificationPrefs = {
  focusUrgentOnly: boolean;
  dailyDigestEmail: boolean;
};

type CompletedTask = {
  id: string;
  title: string;
  cognitive_load_score: number;
  xp_earned: number | null;
  completed_at: string | null;
};

type ActivitySummary = {
  tasks_completed: number;
  total_xp_earned: number;
  energy_checkins: number;
  average_energy_score: number;
};

type ExportRange = "7d" | "30d" | "90d" | "custom";

const focusTimes: {
  value: PeakFocus;
  label: string;
  time: string;
  Icon: typeof Sunrise;
}[] = [
  { value: "early_bird", label: "Early Bird", time: "5am - 9am", Icon: Sunrise },
  { value: "morning", label: "Morning", time: "9am - 1pm", Icon: Sun },
  { value: "afternoon", label: "Afternoon", time: "1pm - 5pm", Icon: Umbrella },
  { value: "evening", label: "Night Owl", time: "8pm - 2am", Icon: Moon },
];

const exportRangeOptions: { value: ExportRange; label: string }[] = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "custom", label: "Custom range" },
];

const badges = [
  ["Deep Diver", "bg-[#dbeafe] text-[#3377f6]", Medal],
  ["Early Riser", "bg-[#fff1b8] text-[#d88a00]", Sunrise],
  ["Architect", "bg-[#e4e8ff] text-[#6470ff]", Award],
  ["Sprinter", "bg-[#ccf6df] text-[#11a96b]", Flag],
] as const;

const NOTIFICATION_KEY = "freeside_notification_prefs";
const XP_PER_LEVEL = 250;

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function normalizePeakFocus(value: string | null | undefined): PeakFocus | "" {
  if (!value) return "";
  if (value === "night") return "evening";
  if (focusTimes.some((option) => option.value === value)) {
    return value as PeakFocus;
  }
  return "";
}

function loadNotificationPrefs(): NotificationPrefs {
  if (typeof window === "undefined") {
    return { focusUrgentOnly: true, dailyDigestEmail: false };
  }
  try {
    const raw = window.localStorage.getItem(NOTIFICATION_KEY);
    if (!raw) return { focusUrgentOnly: true, dailyDigestEmail: false };
    return JSON.parse(raw) as NotificationPrefs;
  } catch {
    return { focusUrgentOnly: true, dailyDigestEmail: false };
  }
}

function saveNotificationPrefs(prefs: NotificationPrefs) {
  window.localStorage.setItem(NOTIFICATION_KEY, JSON.stringify(prefs));
}

function computeLevel(xp: number) {
  return Math.max(1, Math.floor(xp / XP_PER_LEVEL) + 1);
}

function computeFocusStreak(dates: string[]) {
  if (dates.length === 0) return 0;

  const daySet = new Set(dates.map((date) => date.slice(0, 10)));
  const cursor = new Date();
  const today = cursor.toISOString().slice(0, 10);

  if (!daySet.has(today)) {
    cursor.setDate(cursor.getDate() - 1);
  }

  let streak = 0;
  while (daySet.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }

  return streak;
}

function cognitiveLoadLabel(scores: number[]) {
  if (scores.length === 0) return "No data yet";
  const average = scores.reduce((sum, score) => sum + score, 0) / scores.length;
  if (average >= 7) return "High";
  if (average >= 4) return "Optimal";
  return "Low";
}

function formatDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

function resolveExportWindow(range: ExportRange, customStart: string, customEnd: string) {
  const end = new Date();
  const start = new Date();

  if (range === "7d") start.setDate(end.getDate() - 6);
  else if (range === "30d") start.setDate(end.getDate() - 29);
  else if (range === "90d") start.setDate(end.getDate() - 89);
  else {
    return { start: customStart, end: customEnd };
  }

  return { start: formatDateInput(start), end: formatDateInput(end) };
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [userId, setUserId] = useState<string | null>(null);

  const [savedForm, setSavedForm] = useState<ProfileForm>({
    name: "",
    productive_day_description: "",
    peak_focus_time: "",
  });
  const [form, setForm] = useState<ProfileForm>(savedForm);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [savedAvatarUrl, setSavedAvatarUrl] = useState<string | null>(null);

  const [savedNotifications, setSavedNotifications] = useState<NotificationPrefs>({
    focusUrgentOnly: true,
    dailyDigestEmail: false,
  });
  const [notifications, setNotifications] = useState<NotificationPrefs>(savedNotifications);

  const [xpTotal, setXpTotal] = useState(0);
  const [focusStreak, setFocusStreak] = useState(0);
  const [energyScores, setEnergyScores] = useState<number[]>([]);
  const [completedTasks, setCompletedTasks] = useState<CompletedTask[]>([]);

  const [exportRange, setExportRange] = useState<ExportRange>("30d");
  const [customStart, setCustomStart] = useState(formatDateInput(new Date(Date.now() - 29 * 86400000)));
  const [customEnd, setCustomEnd] = useState(formatDateInput(new Date()));
  const [activitySummary, setActivitySummary] = useState<ActivitySummary | null>(null);

  const photoInputRef = useRef<HTMLInputElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const descriptionInputRef = useRef<HTMLTextAreaElement>(null);

  const exportWindow = useMemo(
    () => resolveExportWindow(exportRange, customStart, customEnd),
    [exportRange, customStart, customEnd]
  );

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) throw new Error("Not logged in");

      setUserId(user.id);

      const { data: profile, error: profileError } = await supabase
        .from("profiles")
        .select("name, productive_day_description, peak_focus_time, avatar_url")
        .eq("id", user.id)
        .single();

      if (profileError) throw profileError;

      const statsRes = await fetch(`${API}/profile/stats?user_id=${user.id}`);
      if (!statsRes.ok) throw new Error("Could not load profile stats.");
      const stats = await statsRes.json();

      const nextForm: ProfileForm = {
        name: profile?.name ?? "",
        productive_day_description: profile?.productive_day_description ?? "",
        peak_focus_time: normalizePeakFocus(profile?.peak_focus_time),
      };

      const nextNotifications = loadNotificationPrefs();

      const { data: energyLogs, error: energyError } = await supabase
        .from("energy_logs")
        .select("confirmed_score, logged_at")
        .eq("user_id", user.id)
        .order("logged_at", { ascending: false })
        .limit(30);

      if (energyError) throw energyError;

      const scores = (energyLogs ?? [])
        .map((log) => log.confirmed_score)
        .filter((score): score is number => typeof score === "number")
        .slice(0, 7)
        .reverse();

      const streakDates = (energyLogs ?? [])
        .map((log) => log.logged_at)
        .filter((date): date is string => typeof date === "string");

      setSavedForm(nextForm);
      setForm(nextForm);
      setAvatarUrl(profile?.avatar_url ?? null);
      setSavedAvatarUrl(profile?.avatar_url ?? null);
      setSavedNotifications(nextNotifications);
      setNotifications(nextNotifications);
      setXpTotal(stats.xp_total ?? 0);
      setFocusStreak(computeFocusStreak(streakDates));
      setEnergyScores(scores);
      setCompletedTasks(
        (stats.recent_completions ?? []).map((row: {
          id?: string;
          task_id?: string;
          task_title?: string;
          cognitive_load_score?: number;
          xp_earned?: number | null;
          completed_at?: string | null;
        }) => ({
          id: row.task_id ?? row.id ?? crypto.randomUUID(),
          title: row.task_title ?? "Completed task",
          cognitive_load_score: row.cognitive_load_score ?? 0,
          xp_earned: row.xp_earned ?? null,
          completed_at: row.completed_at ?? null,
        }))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadActivitySummary = useCallback(async () => {
    if (!userId) return;
    if (exportRange === "custom" && (!customStart || !customEnd || customStart > customEnd)) {
      setActivitySummary(null);
      return;
    }

    setSummaryLoading(true);
    try {
      const params = new URLSearchParams({
        user_id: userId,
        start_date: exportWindow.start,
        end_date: exportWindow.end,
      });
      const res = await fetch(`${API}/profile/activity/summary?${params.toString()}`);
      if (!res.ok) throw new Error("Could not load activity summary.");
      const data = await res.json();
      setActivitySummary(data.summary as ActivitySummary);
    } catch {
      setActivitySummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [userId, exportRange, customStart, customEnd, exportWindow.start, exportWindow.end]);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    if (!loading && userId) {
      void loadActivitySummary();
    }
  }, [loading, userId, loadActivitySummary]);

  const isDirty = useMemo(() => {
    return (
      form.name !== savedForm.name ||
      form.productive_day_description !== savedForm.productive_day_description ||
      form.peak_focus_time !== savedForm.peak_focus_time ||
      avatarUrl !== savedAvatarUrl ||
      notifications.focusUrgentOnly !== savedNotifications.focusUrgentOnly ||
      notifications.dailyDigestEmail !== savedNotifications.dailyDigestEmail
    );
  }, [form, notifications, savedForm, savedNotifications, avatarUrl, savedAvatarUrl]);

  const level = computeLevel(xpTotal);
  const levelProgress = ((xpTotal % XP_PER_LEVEL) / XP_PER_LEVEL) * 100;
  const hasEnergyData = energyScores.length > 0;
  const chartHeights = hasEnergyData
    ? energyScores.map((score) => Math.max(18, (score / 10) * 100))
    : [34, 52, 70, 84, 43, 26, 62];

  const handleCancel = () => {
    setForm(savedForm);
    setNotifications(savedNotifications);
    setAvatarUrl(savedAvatarUrl);
    setError("");
    setSavedMessage("");
  };

  const handleSave = async () => {
    if (!userId) return;

    if (!form.name.trim()) {
      setError("Full name is required.");
      return;
    }

    if (!form.productive_day_description.trim()) {
      setError("Productive day description is required.");
      return;
    }

    if (!form.peak_focus_time) {
      setError("Select your peak focus time.");
      return;
    }

    setSaving(true);
    setError("");
    setSavedMessage("");

    try {
      const { error: updateError } = await supabase
        .from("profiles")
        .update({
          name: form.name.trim(),
          productive_day_description: form.productive_day_description.trim(),
          peak_focus_time: form.peak_focus_time,
          avatar_url: avatarUrl,
        })
        .eq("id", userId);

      if (updateError) throw updateError;

      saveNotificationPrefs(notifications);
      setSavedForm(form);
      setSavedNotifications(notifications);
      setSavedAvatarUrl(avatarUrl);
      setSavedMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  };

  const handlePhotoSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !userId) return;

    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("Profile photo must be 5 MB or smaller.");
      return;
    }

    setPhotoUploading(true);
    setError("");
    setSavedMessage("");

    try {
      const ext = file.name.split(".").pop()?.toLowerCase() || "jpg";
      const filePath = `${userId}/avatar.${ext}`;

      const { error: uploadError } = await supabase.storage
        .from("avatars")
        .upload(filePath, file, { upsert: true, contentType: file.type });

      if (uploadError) throw uploadError;

      const {
        data: { publicUrl },
      } = supabase.storage.from("avatars").getPublicUrl(filePath);
      const nextUrl = `${publicUrl}?t=${Date.now()}`;

      const { error: updateError } = await supabase
        .from("profiles")
        .update({ avatar_url: nextUrl })
        .eq("id", userId);

      if (updateError) throw updateError;

      setAvatarUrl(nextUrl);
      setSavedAvatarUrl(nextUrl);
      setSavedMessage("Profile photo updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload profile photo.");
    } finally {
      setPhotoUploading(false);
      event.target.value = "";
    }
  };

  const handleExportCsv = async () => {
    if (!userId) return;
    if (exportRange === "custom" && customStart > customEnd) {
      setError("Custom range start must be before end.");
      return;
    }

    setExporting(true);
    setError("");

    try {
      const params = new URLSearchParams({
        user_id: userId,
        start_date: exportWindow.start,
        end_date: exportWindow.end,
      });
      const res = await fetch(`${API}/profile/activity/export?${params.toString()}`);
      if (!res.ok) throw new Error("Could not export activity summary.");

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `freeside_activity_${exportWindow.start}_${exportWindow.end}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
      setSavedMessage("Activity summary downloaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not export activity summary.");
    } finally {
      setExporting(false);
    }
  };

  const toggleNotification = (key: keyof NotificationPrefs) => {
    setNotifications((current) => ({ ...current, [key]: !current[key] }));
  };

  return (
    <AppShell active="settings">
      <div className="min-h-screen bg-[linear-gradient(120deg,#fbfcff,#f2f5fa)] px-6 py-10 md:px-12 lg:px-16">
        <div className="mb-12 flex flex-col items-end gap-3">
          <div className="flex gap-4">
            <button
              type="button"
              onClick={handleCancel}
              disabled={loading || saving || !isDirty}
              className="rounded-lg border border-[#c7c4d7] bg-white px-8 py-3 text-lg font-bold text-[#464554] transition enabled:hover:bg-[#f7f7fb] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={loading || saving || !isDirty}
              className="flex items-center gap-3 rounded-lg bg-[#4648d4] px-8 py-3 text-lg font-bold text-white shadow-lg transition enabled:hover:bg-[#3f3dc6] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
              Save Changes
            </button>
          </div>
          {error && <p className="text-sm font-semibold text-[#ba1a1a]">{error}</p>}
          {savedMessage && <p className="text-sm font-semibold text-[#2d7a3a]">{savedMessage}</p>}
        </div>

        {loading ? (
          <div className="flex min-h-[420px] items-center justify-center">
            <Loader2 className="h-10 w-10 animate-spin text-[#4648d4]" />
          </div>
        ) : (
          <div className="mx-auto grid max-w-[1380px] gap-10 2xl:grid-cols-[1.2fr_.8fr]">
            <section className="space-y-10">
              <article className="ui-card rounded-lg p-12">
                <h1 className="mb-10 flex items-center gap-5 text-4xl font-extrabold">
                  <UserRound className="h-8 w-8 text-[#4648d4]" /> Profile Overview
                </h1>
                <div className="grid gap-12 md:grid-cols-[160px_1fr]">
                  <div className="relative mx-auto md:mx-0">
                    <div
                      className="grid h-36 w-36 place-items-center overflow-hidden rounded-full border-8 border-white bg-[#4648d4] text-4xl font-extrabold text-white shadow-lg"
                      aria-label="Profile avatar"
                    >
                      {avatarUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={avatarUrl} alt="Profile" className="h-full w-full object-cover" />
                      ) : getInitials(form.name) ? (
                        getInitials(form.name)
                      ) : (
                        <CircleUserRound className="h-14 w-14 text-white/80" />
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => photoInputRef.current?.click()}
                      disabled={photoUploading}
                      className="absolute bottom-1 right-1 grid h-10 w-10 place-items-center rounded-full border-2 border-white bg-[#4648d4] text-white shadow-lg transition hover:bg-[#3f3dc6] disabled:opacity-60"
                      title="Add profile photo"
                    >
                      {photoUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
                    </button>
                    <input
                      ref={photoInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(event) => void handlePhotoSelect(event)}
                    />
                  </div>
                  <div className="space-y-6">
                    <label className="block">
                      <span className="mb-2 flex items-center justify-between text-lg font-bold text-[#464554]">
                        Full Name
                        <button
                          type="button"
                          onClick={() => nameInputRef.current?.focus()}
                          className="flex items-center gap-1 text-sm font-semibold text-[#4648d4] hover:underline"
                        >
                          <Pencil className="h-4 w-4" /> Edit
                        </button>
                      </span>
                      <input
                        ref={nameInputRef}
                        className="h-14 w-full rounded-lg border border-[#c7c4d7] bg-white/60 px-5 text-xl outline-none focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20"
                        value={form.name}
                        onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                        placeholder="Your name"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-2 flex items-center justify-between text-lg font-bold text-[#464554]">
                        Productive Day Description
                        <button
                          type="button"
                          onClick={() => descriptionInputRef.current?.focus()}
                          className="flex items-center gap-1 text-sm font-semibold text-[#4648d4] hover:underline"
                        >
                          <Pencil className="h-4 w-4" /> Edit
                        </button>
                      </span>
                      <textarea
                        ref={descriptionInputRef}
                        className="h-28 w-full resize-none rounded-lg border border-[#c7c4d7] bg-white/60 px-5 py-3 text-xl leading-8 outline-none focus:border-[#4648d4] focus:ring-2 focus:ring-[#4648d4]/20"
                        value={form.productive_day_description}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            productive_day_description: event.target.value,
                          }))
                        }
                        placeholder="Describe what a productive day looks like for you"
                      />
                    </label>
                  </div>
                </div>
              </article>

              <article className="ui-card rounded-lg p-12">
                <h2 className="mb-8 flex items-center gap-5 text-4xl font-extrabold">
                  <Flag className="h-8 w-8 text-[#4648d4]" /> Task XP History
                </h2>
                <p className="mb-6 text-lg text-[#464554]">
                  Each completed task earns XP based on difficulty: load score × 10 (e.g. load 8 = 80 XP).
                </p>
                {completedTasks.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-[#dfe2e8] px-6 py-10 text-center text-lg text-[#8183a0]">
                    Complete tasks on the dashboard to earn XP.
                  </p>
                ) : (
                  <div className="overflow-hidden rounded-lg border border-[#dfe2e8]">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-[#f7f8fc] text-[#464554]">
                        <tr>
                          <th className="px-4 py-3 font-bold">Task</th>
                          <th className="px-4 py-3 font-bold">Load</th>
                          <th className="px-4 py-3 font-bold">XP</th>
                          <th className="px-4 py-3 font-bold">Completed</th>
                        </tr>
                      </thead>
                      <tbody>
                        {completedTasks.map((task) => (
                          <tr className="border-t border-[#eceef4]" key={task.id}>
                            <td className="px-4 py-3 font-medium text-[#191c1e]">{task.title}</td>
                            <td className="px-4 py-3 text-[#464554]">{task.cognitive_load_score}/10</td>
                            <td className="px-4 py-3 font-bold text-[#4648d4]">+{effectiveTaskXp(task)} XP</td>
                            <td className="px-4 py-3 text-[#8183a0]">
                              {task.completed_at
                                ? new Date(task.completed_at).toLocaleDateString(undefined, {
                                    month: "short",
                                    day: "numeric",
                                    year: "numeric",
                                  })
                                : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </article>

              <article className="ui-card rounded-lg p-12">
                <h2 className="mb-8 flex items-center gap-5 text-4xl font-extrabold">
                  <Settings2 className="h-8 w-8 text-[#4648d4]" /> Integrations
                </h2>
                <p className="mb-8 text-lg text-[#464554]">
                  Connected tools feed Google Calendar, ClickUp, and Co-Pilot chat into your daily plan when you
                  start the day.
                </p>
                <Suspense
                  fallback={
                    <div className="flex items-center gap-2 text-sm text-[#6b7080]">
                      <Loader2 className="h-4 w-4 animate-spin" /> Loading integrations…
                    </div>
                  }
                >
                  <ClickUpIntegrationPanel userId={userId} />
                </Suspense>
              </article>

              <article className="ui-card rounded-lg p-12">
                <h2 className="mb-8 flex items-center gap-5 text-4xl font-extrabold">
                  <Download className="h-8 w-8 text-[#4648d4]" /> Activity Summary Export
                </h2>
                <p className="mb-6 text-lg text-[#464554]">
                  Download a CSV summary of completed tasks, XP earned, and energy check-ins for any time period.
                </p>

                <div className="mb-6 flex flex-wrap gap-3">
                  {exportRangeOptions.map((option) => (
                    <button
                      type="button"
                      key={option.value}
                      onClick={() => setExportRange(option.value)}
                      className={`rounded-lg border px-4 py-2 text-sm font-bold transition ${
                        exportRange === option.value
                          ? "border-[#4648d4] bg-[#f5f4ff] text-[#4648d4]"
                          : "border-[#c7c4d7] bg-white text-[#464554] hover:border-[#4648d4]/40"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>

                {exportRange === "custom" && (
                  <div className="mb-6 grid gap-4 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-2 block text-sm font-bold text-[#464554]">Start date</span>
                      <input
                        type="date"
                        value={customStart}
                        onChange={(event) => setCustomStart(event.target.value)}
                        className="h-12 w-full rounded-lg border border-[#c7c4d7] bg-white px-4 outline-none focus:border-[#4648d4]"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-2 block text-sm font-bold text-[#464554]">End date</span>
                      <input
                        type="date"
                        value={customEnd}
                        onChange={(event) => setCustomEnd(event.target.value)}
                        className="h-12 w-full rounded-lg border border-[#c7c4d7] bg-white px-4 outline-none focus:border-[#4648d4]"
                      />
                    </label>
                  </div>
                )}

                <div className="mb-6 rounded-lg border border-[#dfe2e8] bg-white p-6">
                  <div className="mb-4 text-sm font-bold uppercase tracking-wide text-[#8183a0]">
                    {exportWindow.start} → {exportWindow.end}
                  </div>
                  {summaryLoading ? (
                    <div className="flex items-center gap-2 text-[#464554]">
                      <Loader2 className="h-4 w-4 animate-spin" /> Loading summary…
                    </div>
                  ) : activitySummary ? (
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <div className="text-sm text-[#8183a0]">Tasks completed</div>
                        <div className="text-2xl font-extrabold text-[#191c1e]">{activitySummary.tasks_completed}</div>
                      </div>
                      <div>
                        <div className="text-sm text-[#8183a0]">Total XP earned</div>
                        <div className="text-2xl font-extrabold text-[#4648d4]">{activitySummary.total_xp_earned}</div>
                      </div>
                      <div>
                        <div className="text-sm text-[#8183a0]">Energy check-ins</div>
                        <div className="text-2xl font-extrabold text-[#191c1e]">{activitySummary.energy_checkins}</div>
                      </div>
                      <div>
                        <div className="text-sm text-[#8183a0]">Avg energy</div>
                        <div className="text-2xl font-extrabold text-[#8127cf]">{activitySummary.average_energy_score}/10</div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[#8183a0]">No activity data for this period.</p>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => void handleExportCsv()}
                  disabled={exporting || summaryLoading}
                  className="flex items-center gap-3 rounded-lg bg-[#4648d4] px-6 py-3 text-lg font-bold text-white shadow-lg transition enabled:hover:bg-[#3f3dc6] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {exporting ? <Loader2 className="h-5 w-5 animate-spin" /> : <Download className="h-5 w-5" />}
                  Download CSV
                </button>
              </article>

              <article className="ui-card rounded-lg p-12">
                <h2 className="mb-10 flex items-center gap-5 text-4xl font-extrabold">
                  <Settings2 className="h-8 w-8 text-[#8127cf]" /> Focus Preferences
                </h2>
                <div className="rounded-lg border border-[#dfe2e8] bg-white p-7">
                  <h3 className="text-2xl font-medium">Peak Focus Time</h3>
                  <p className="mt-2 text-lg text-[#464554]">When are you most cognitively alert?</p>
                  <div className="mt-7 grid gap-4 md:grid-cols-4">
                    {focusTimes.map(({ value, label, time, Icon }) => {
                      const active = form.peak_focus_time === value;
                      return (
                        <button
                          type="button"
                          className={`rounded-lg border p-5 text-center transition ${
                            active ? "border-[#4648d4] bg-[#f5f4ff] text-[#4648d4]" : "border-[#c7c4d7] bg-white hover:border-[#4648d4]/40"
                          }`}
                          key={value}
                          onClick={() => setForm((current) => ({ ...current, peak_focus_time: value }))}
                        >
                          <Icon className="mx-auto mb-4 h-7 w-7" />
                          <div className="text-lg font-bold text-[#191c1e]">{label}</div>
                          <div className="mt-1 text-sm text-[#464554]">{time}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-8 rounded-lg border border-[#dfe2e8] bg-white p-7">
                  <h3 className="mb-6 text-2xl font-medium">Notification Intensity</h3>
                  <div className="space-y-6">
                    {(
                      [
                        ["focusUrgentOnly", "Focus Mode Interruption (Urgent Only)"],
                        ["dailyDigestEmail", "Daily Digest Email"],
                      ] as const
                    ).map(([key, label]) => {
                      const on = notifications[key];
                      return (
                        <div className="flex items-center justify-between text-xl text-[#464554]" key={key}>
                          <span>{label}</span>
                          <button
                            type="button"
                            role="switch"
                            aria-checked={on}
                            onClick={() => toggleNotification(key)}
                            className={`flex h-9 w-16 items-center rounded-full p-1 transition ${on ? "justify-end bg-[#4648d4]" : "justify-start bg-[#dfe2e3]"}`}
                          >
                            <span className="h-7 w-7 rounded-full bg-white shadow-sm" />
                          </button>
                        </div>
                      );
                    })}
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
                    <div className="mt-4 text-7xl font-extrabold text-[#4648d4]">{level}</div>
                    <div className="mx-auto mt-5 h-3 w-32 rounded-full bg-[#dfe2e3]">
                      <div
                        className="h-full rounded-full bg-[linear-gradient(90deg,#4648d4,#8127cf)]"
                        style={{ width: `${levelProgress}%` }}
                      />
                    </div>
                    <p className="mt-3 text-[#464554]">
                      {xpTotal % XP_PER_LEVEL} / {XP_PER_LEVEL} XP · {xpTotal} total
                    </p>
                  </div>
                  <div className="rounded-lg bg-white p-7 text-center shadow-sm">
                    <div className="text-label text-[#464554]">Focus Streak</div>
                    <div className="mt-4 text-7xl font-extrabold text-[#ff7a1a]">{focusStreak}</div>
                    <p className="mt-6 text-[#464554]">Days in Focus Zone</p>
                  </div>
                </div>
                <div className="mb-5 flex justify-between text-lg font-bold">
                  <span className="text-[#464554]">Cognitive Load (7 Days)</span>
                  <span className="text-[#1f22f0]">{cognitiveLoadLabel(energyScores)}</span>
                </div>
                <div className="flex h-28 items-end gap-2">
                  {chartHeights.map((height, index) => (
                    <div
                      className={`flex-1 rounded-t ${index === chartHeights.length - 1 && hasEnergyData ? "bg-[#b574e2]" : "bg-[#9697df]"}`}
                      key={`${height}-${index}`}
                      style={{
                        height: `${height}%`,
                        opacity: hasEnergyData ? 1 : index === 0 || index === chartHeights.length - 2 ? 0.4 : 1,
                      }}
                    />
                  ))}
                </div>
              </article>

              <article className="ui-card rounded-lg p-12">
                <div className="mb-8 flex items-center justify-between">
                  <h2 className="flex items-center gap-5 text-4xl font-extrabold">
                    <Medal className="h-8 w-8 text-[#8127cf]" /> Evidence Badges
                  </h2>
                  <span className="text-lg font-bold text-[#464554]">Coming soon</span>
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
                <button
                  type="button"
                  disabled
                  className="mt-6 h-12 w-full cursor-not-allowed rounded-lg border border-[#e25151] bg-white text-lg font-bold text-[#ba1a1a] opacity-60"
                >
                  Delete Account
                </button>
              </article>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}
