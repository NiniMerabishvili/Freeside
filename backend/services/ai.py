"""
AI service — Google Gemini (google-genai SDK) for energy inference and co-pilot chat.
"""
import json
import logging
import os
import re
from pathlib import Path

from google import genai
from google.genai import types
from dotenv import load_dotenv

from services import model_router

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
_MODEL = "gemini-2.5-flash"
logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a Gemini response string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in Gemini response:\n{text}")
    return json.loads(match.group())


def _extract_json_array(text: str) -> list:
    """Extract the first JSON array from a Gemini response string."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in Gemini response:\n{text}")
    return json.loads(match.group())


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


# ---------------------------------------------------------------------------
# Task-quality normalisation
# ---------------------------------------------------------------------------

# Vague verbs that signal a low-quality, non-actionable task title.
_WEAK_STARTS = (
    "work on", "work through", "do ", "handle", "deal with", "look at",
    "think about", "figure out", "stuff", "things", "misc", "various",
)


def _title_quality_ok(title: str) -> bool:
    """A usable title is specific, non-trivial, and not a vague catch-all."""
    t = (title or "").strip()
    if len(t) < 4 or len(t.split()) < 2:
        return False
    return not t.lower().startswith(_WEAK_STARTS)


def _clean_title(title: str, max_words: int = 14) -> str:
    """Trim, collapse whitespace, capitalise, and cap length of a task title."""
    t = re.sub(r"\s+", " ", str(title or "").strip()).strip(" .")
    if not t:
        return t
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words])
    return t[0].upper() + t[1:]


def _reconcile_load_and_minutes(load: int, minutes: int) -> tuple[int, int]:
    """
    Keep cognitive load and duration internally consistent.

    Deep work (high load) cannot be a 10-minute task; trivial admin (low load)
    should not be booked as a 3-hour block. Nudges outliers into a sane band.
    """
    load = max(1, min(10, int(load)))
    minutes = max(10, min(240, int(minutes)))
    if load >= 7 and minutes < 45:
        minutes = 45
    elif load <= 3 and minutes > 60:
        minutes = 60
    elif 4 <= load <= 6 and minutes > 120:
        minutes = 120
    return load, minutes


def normalize_task_specs(
    raw: list[dict],
    *,
    default_load: int = 5,
    default_minutes: int = 45,
    max_items: int | None = None,
    keep_reasoning: bool = False,
) -> list[dict]:
    """
    Clean, validate, and de-duplicate AI/fallback task specs.

    - Drops vague or duplicate titles.
    - Clamps and reconciles cognitive_load_score ↔ estimated_minutes.
    - Preserves optional fields (reasoning) when requested.
    """
    seen: set[str] = set()
    cleaned: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        title = _clean_title(item.get("title") or item.get("text") or "")
        if not _title_quality_ok(title):
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        try:
            load = int(item.get("cognitive_load_score", default_load))
        except (TypeError, ValueError):
            load = default_load
        try:
            minutes = int(item.get("estimated_minutes", default_minutes))
        except (TypeError, ValueError):
            minutes = default_minutes
        load, minutes = _reconcile_load_and_minutes(load, minutes)

        spec: dict = {
            "title": title,
            "cognitive_load_score": load,
            "estimated_minutes": minutes,
        }
        if keep_reasoning and item.get("reasoning"):
            spec["reasoning"] = _clean_title(item["reasoning"], max_words=14)
        cleaned.append(spec)

    if max_items:
        cleaned = cleaned[:max_items]
    return cleaned


def _profile_context_block(profile: dict) -> str:
    """Shared profile snippet so decomposition reflects how the user actually works."""
    parts = [f"- Role: {profile.get('role', 'professional')}"]
    if profile.get("work_style"):
        parts.append(f"- Work style: {profile['work_style']}")
    if profile.get("peak_focus_time"):
        parts.append(f"- Peak focus window: {profile['peak_focus_time']}")
    if profile.get("daily_work_hours"):
        parts.append(f"- Typical focused hours/day: {profile['daily_work_hours']}")
    if profile.get("productive_day_description"):
        parts.append(f"- Their idea of a productive day: {profile['productive_day_description']}")
    return "\n".join(parts)


def fallback_decompose_goal(goal_title: str) -> list[dict]:
    """Rule-based milestones when Gemini is unavailable (still normalised downstream)."""
    short = goal_title.strip().rstrip(".")[:60]
    return normalize_task_specs([
        {
            "title": f"Clarify scope and success criteria for {short}",
            "cognitive_load_score": 6,
            "estimated_minutes": 75,
            "reasoning": "Define what done looks like before building",
        },
        {
            "title": f"Research and outline the approach for {short}",
            "cognitive_load_score": 6,
            "estimated_minutes": 90,
            "reasoning": "Reduce uncertainty and pick a direction",
        },
        {
            "title": f"Build the core of {short}",
            "cognitive_load_score": 8,
            "estimated_minutes": 150,
            "reasoning": "The main deliverable that moves the goal",
        },
        {
            "title": f"Test, review, and refine {short}",
            "cognitive_load_score": 6,
            "estimated_minutes": 90,
            "reasoning": "Validate quality and close gaps",
        },
    ], default_load=6, default_minutes=90, keep_reasoning=True)


def fallback_milestone_tasks(milestone_title: str, load: int, est: int) -> list[dict]:
    """Rule-based child tasks when Gemini is unavailable (still normalised downstream)."""
    short = milestone_title.strip().rstrip(".")[:50]
    chunk = max(20, min(60, est // 3))
    return normalize_task_specs([
        {"title": f"Gather inputs and set up for {short}", "cognitive_load_score": max(1, load - 2), "estimated_minutes": chunk},
        {"title": f"Complete the main work of {short}", "cognitive_load_score": load, "estimated_minutes": chunk},
        {"title": f"Review and wrap up {short}", "cognitive_load_score": max(1, load - 1), "estimated_minutes": chunk},
    ], default_load=load, default_minutes=chunk)


def normalize_copilot_milestones(data: dict) -> list[dict]:
    """Ensure Co-Pilot output is milestone-shaped (milestone → tasks)."""
    milestones = data.get("suggested_milestones") or []
    parsed: list[dict] = []
    for m in milestones:
        if not isinstance(m, dict) or not m.get("title"):
            continue
        tasks = []
        for t in m.get("tasks") or []:
            if isinstance(t, dict) and t.get("title"):
                score = int(t.get("cognitive_load_score") or 5)
                tasks.append({
                    "title": str(t["title"]).strip()[:80],
                    "cognitive_load_score": max(1, min(10, score)),
                    "estimated_minutes": int(t.get("estimated_minutes") or 30),
                })
        load = int(m.get("cognitive_load_score") or (max((t["cognitive_load_score"] for t in tasks), default=5)))
        parsed.append({
            "title": str(m["title"]).strip()[:100],
            "cognitive_load_score": max(1, min(10, load)),
            "estimated_minutes": int(m.get("estimated_minutes") or sum(t["estimated_minutes"] for t in tasks) or 60),
            "tasks": tasks or [{
                "title": str(m["title"]).strip()[:80],
                "cognitive_load_score": load,
                "estimated_minutes": 45,
            }],
        })

    if parsed:
        return parsed

    flat = data.get("suggested_tasks") or []
    if not flat:
        return []

    tasks = []
    for t in flat:
        if isinstance(t, dict) and t.get("title"):
            score = int(t.get("cognitive_load_score") or 5)
            tasks.append({
                "title": str(t["title"]).strip()[:80],
                "cognitive_load_score": max(1, min(10, score)),
                "estimated_minutes": int(t.get("estimated_minutes") or 30),
            })
    if not tasks:
        return []
    return [{
        "title": "Co-Pilot focus",
        "cognitive_load_score": max(t["cognitive_load_score"] for t in tasks),
        "estimated_minutes": sum(t["estimated_minutes"] for t in tasks),
        "tasks": tasks,
    }]


# ---------------------------------------------------------------------------
# Energy inference
# ---------------------------------------------------------------------------

def infer_energy_from_calendar(calendar_summary: dict, user_profile: dict) -> dict:
    """
    Ask Gemini to infer the user's likely cognitive energy level based on
    today's calendar schedule and their work profile.

    Returns: { suggested_score: int, suggested_level: str, reasoning: str }
    """
    prompt = f"""You are analyzing a user's calendar to estimate their cognitive energy available for focused work today.

USER PROFILE:
- Peak focus time: {user_profile.get('peak_focus_time', 'unknown')}
- Work style: {user_profile.get('work_style', 'unknown')}
- Typical daily hours: {user_profile.get('daily_work_hours', 'unknown')}

TODAY'S CALENDAR:
- Timed meetings (actual scheduled calls/meetings): {calendar_summary['event_count']}
- Total time in timed meetings: {calendar_summary['total_meeting_minutes']} minutes
- Back-to-back meetings (< 15 min gap): {calendar_summary['back_to_back_count']}
- All-day markers (holidays, travel, birthdays — NOT meetings): {calendar_summary.get('all_day_event_count', 0)}
- Schedule detail:
{calendar_summary['event_list']}

IMPORTANT RULES FOR SCORING:
- Base cognitive load ONLY on timed meetings (calls, appointments, classes).
- All-day entries like holidays, birthdays, travel markers, or "Fathers' Day" are NOT meetings — ignore them for load scoring.
- 0 timed meetings = high available energy for deep work (score 7–9).
- 1–2 short meetings = balanced energy (score 5–7).
- 3+ meetings or >2h in meetings = low energy for deep work (score 2–5).
- Back-to-back meetings add 1–2 points of extra load.

Respond ONLY with this exact JSON — no explanation, no markdown fences:
{{"suggested_score": <integer 1-10>, "suggested_level": "<high|balanced|low>", "reasoning": "<one sentence, max 20 words, conversational tone>"}}"""

    return model_router.generate_json("energy_inference", contents=prompt)


def infer_energy_from_day_context(day_context: dict, user_profile: dict) -> dict:
    """
    Infer energy from Google Calendar + ClickUp workload + recent Co-Pilot activity.
    Returns: { suggested_score, suggested_level, reasoning }
    """
    cal = day_context.get("calendar_summary")
    calendar_block = "Calendar not connected."
    if cal:
        calendar_block = f"""- Timed meetings: {cal.get('event_count', 0)}
- Meeting minutes: {cal.get('total_meeting_minutes', 0)}
- Back-to-back blocks: {cal.get('back_to_back_count', 0)}
- Schedule:
{cal.get('event_list', 'None')}"""

    clickup_block = day_context.get("clickup_block") or "ClickUp not connected."
    copilot_block = day_context.get("copilot_summary") or "No recent Co-Pilot activity."

    prompt = f"""You are analyzing a user's full day context to estimate cognitive energy for focused work TODAY.

USER PROFILE:
- Peak focus time: {user_profile.get('peak_focus_time', 'unknown')}
- Work style: {user_profile.get('work_style', 'unknown')}
- Typical daily hours: {user_profile.get('daily_work_hours', 'unknown')}

GOOGLE CALENDAR:
{calendar_block}

CLICKUP WORKLOAD:
{clickup_block}

RECENT CO-PILOT CONVERSATION:
{copilot_block}

SCORING RULES (combine ALL sources):
- Heavy meeting day + many urgent/overdue ClickUp items → lower score (2-5)
- Open calendar + moderate ClickUp → balanced (5-7)
- Light meetings + few tasks + user recently asked for light work in Co-Pilot → higher (7-9)
- If Co-Pilot conversation shows product/implementation goals, factor that into available focus (not lower energy unless user said they are tired)
- If Co-Pilot shows repeated low-energy or break-down requests, reduce score by 1-2
- All-day calendar markers are NOT meetings

Respond ONLY with this exact JSON — no markdown fences:
{{"suggested_score": <integer 1-10>, "suggested_level": "<high|balanced|low>", "reasoning": "<one sentence max 25 words mentioning calendar and/or ClickUp if relevant>"}}"""

    return model_router.generate_json("energy_inference", contents=prompt)


# ---------------------------------------------------------------------------
# Co-pilot context builder
# ---------------------------------------------------------------------------

def build_copilot_context(
    user_id: str,
    supabase,
    *,
    energy_score: int | None = None,
    energy_level: str | None = None,
) -> str:
    """
    Build a rich system-prompt from the user's current state.
    Includes profile, energy, goals, tasks, and connected integrations.
    """
    profile = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

    energy_log = (
        supabase.table("energy_logs")
        .select("*")
        .eq("user_id", user_id)
        .order("logged_at", desc=True)
        .limit(1)
        .execute()
    )
    energy = energy_log.data[0] if energy_log.data else None

    goals = (
        supabase.table("goals")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .execute()
    )
    goals_text = (
        "\n".join(
            [
                f"- {g['title']} ({g.get('category', 'general')}, {g.get('timeframe', '')})"
                for g in goals.data
            ]
        )
        if goals.data
        else "Not set yet"
    )

    tasks = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )
    task_list = (
        "\n".join(
            [
                f"- {t['title']} (load: {t.get('cognitive_load_score', '?')}/10)"
                for t in tasks.data
            ]
        )
        if tasks.data
        else "No pending tasks"
    )

    try:
        integrations_result = (
            supabase.table("user_integrations")
            .select(
                "integration_type, is_connected, context_notes, workspace_name, "
                "external_team_id, account_label"
            )
            .eq("user_id", user_id)
            .eq("is_connected", True)
            .execute()
        )
        integrations_text = _format_integrations(
            integrations_result.data if integrations_result.data else []
        )
    except Exception:
        integrations_text = "No external tools connected yet."

    energy_level = energy_level or (energy["confirmed_level"] if energy else "unknown")
    energy_score = energy_score if energy_score is not None else (
        energy["confirmed_score"] if energy else "unknown"
    )

    from services.copilot_history import fetch_recent_copilot_conversation
    copilot_conversation = fetch_recent_copilot_conversation(supabase, user_id)

    calendar_block = "No calendar data logged today."
    if energy:
        event_count = energy.get("calendar_event_count")
        calendar_ctx = energy.get("calendar_context")
        if event_count is not None or calendar_ctx:
            calendar_block = f"""- Meetings today: {event_count or 0}
- Schedule summary:
{calendar_ctx or 'Not available'}"""

    from services.clickup import get_clickup_context_from_db
    try:
        clickup_block = get_clickup_context_from_db(supabase, user_id)
    except Exception as exc:
        logger.warning(
            "ClickUp context unavailable for user_id=%s: %s",
            user_id,
            str(exc)[:200],
        )
        clickup_block = f"ClickUp unavailable: {str(exc)[:120]}"

    return f"""You are the Freeside AI Co-Pilot — a calm, empathetic, highly personalised productivity coach.

USER PROFILE:
- Name: {profile.get('name', 'User')}
- Role: {profile.get('role', 'unknown')}
- What a productive day looks like for them: {profile.get('productive_day_description', 'Not specified')}
- Peak focus time: {profile.get('peak_focus_time', 'unknown')}
- Work style: {profile.get('work_style', 'unknown')}
- Daily working hours: {profile.get('daily_work_hours', 'unknown')}h

CURRENT STATE:
- Energy level: {energy_level} ({energy_score}/10)

TODAY'S GOOGLE CALENDAR (from morning check-in):
{calendar_block}

CLICKUP TASKS (live from connected workspace):
{clickup_block}

RECENT CO-PILOT CONVERSATION (use this to infer what the user is building and wants today):
{copilot_conversation}

Active goals:
{goals_text}
- Pending tasks:
{task_list}

CONNECTED TOOLS & CONTEXT:
{integrations_text}

BEHAVIOR RULES:
- If energy is low, NEVER suggest heavy work. Always suggest rest or light tasks.
- When asked to break down a task, return exactly 3-5 micro-steps, each under 15 words.
- Be warm and encouraging, never critical.
- Keep responses under 150 words unless breaking down a task.
- Reference the user's actual tasks, goals, energy level, calendar, ClickUp workload, and Co-Pilot conversation in every response.
- When the user discussed product features, roadmap, or implementation in Co-Pilot chat, suggested tasks MUST advance those goals — never generic admin/email unless they asked.
- When planning the day, prioritise ClickUp items that are due today or overdue IF they match current energy AND user-stated priorities from chat.
- Prefer ClickUp + calendar together: schedule deep work in open calendar blocks, light ClickUp admin in low-energy windows.
- Match cognitive load to CURRENT energy ({energy_level}, {energy_score}/10): low energy → loads 1-4 only; high → can include 6-10.
- Use their work style and peak focus time to time suggestions appropriately.

When the user asks what to do, wants ideas, planning help, or proactive energy guidance, include concrete task suggestions in suggested_tasks (see response format)."""


def _format_integrations(integrations: list) -> str:
    if not integrations:
        return "No external tools connected yet."
    labels = {
        "clickup": "ClickUp (task management)",
        "asana": "Asana (project management)",
        "obsidian": "Obsidian (knowledge base)",
        "notes": "Notes & personal context",
        "ai_agents": "AI Agents",
    }
    lines = []
    for intg in integrations:
        itype = intg.get("integration_type", "")
        label = labels.get(itype, itype)
        workspace = intg.get("workspace_name", "")
        notes = intg.get("context_notes", "")
        line = f"- {label}"
        if workspace:
            line += f" | Workspace: {workspace}"
        if intg.get("is_connected"):
            line += " | API connected"
        if notes:
            line += f"\n  Context: {notes}"
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Co-pilot chat
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AI goal decomposition
# ---------------------------------------------------------------------------

def decompose_goal(goal_title: str, category: str, timeframe: str, profile: dict) -> tuple[list[dict], bool]:
    """
    Break a user goal into 4–6 substantive milestones (~1+ hour each).

    Returns: (milestones, used_fallback)
    """
    prompt = f"""You are a productivity strategist helping a user plan a meaningful goal — not a checkbox list.

GOAL: "{goal_title}"
CATEGORY: {category}
TIMEFRAME: {timeframe}

USER CONTEXT:
{_profile_context_block(profile)}

Decompose this goal into 4–6 MILESTONES — each a substantive chunk of focused work (roughly 60–180 minutes).

QUALITY BAR (important):
- Each title starts with a strong action verb and names a CONCRETE deliverable or outcome
  (e.g. "Draft the landing-page copy and hero section", NOT "Work on marketing").
- No trivial micro-tasks ("send one email", "open a doc", "5-minute review").
- No vague filler ("work on", "handle", "think about", "misc").
- Milestones must be distinct — no overlap or duplication.
- Sequence them logically: foundation → research/design → execution → validation/polish.

For each milestone assign:
- cognitive_load_score (1–10): most should be 5–9 (real work, not admin crumbs). Heavier build/strategy work = higher.
- estimated_minutes: realistic focused time (60–180), consistent with the load.
- reasoning: the concrete outcome / definition of done (max 12 words).

Respond ONLY with a JSON array — no markdown, no explanation:
[{{"title": "<verb-first milestone, max 14 words>", "cognitive_load_score": <int 5-9>, "estimated_minutes": <int 60-180>, "reasoning": "<definition of done, max 12 words>"}}]"""

    try:
        raw = model_router.generate_json_array("goal_decompose", contents=prompt)
        milestones = normalize_task_specs(
            raw,
            default_load=6,
            default_minutes=90,
            max_items=6,
            keep_reasoning=True,
        )
        if len(milestones) < 2:
            return fallback_decompose_goal(goal_title), True
        return milestones, False
    except Exception as exc:
        if _is_quota_error(exc):
            return fallback_decompose_goal(goal_title), True
        raise


def decompose_milestone_tasks(
    milestone_title: str,
    cognitive_load_score: int,
    estimated_minutes: int,
    profile: dict,
    goal_title: str | None = None,
) -> list[dict]:
    """
    Break a milestone into 3–5 actionable tasks that fit within the milestone scope.

    Returns: [{ title, cognitive_load_score, estimated_minutes }, ...]
    """
    goal_line = f'PARENT GOAL: "{goal_title}"\n' if goal_title else ""
    prompt = f"""You are a productivity strategist breaking a milestone into concrete, do-able tasks.

{goal_line}MILESTONE: "{milestone_title}"
MILESTONE LOAD: {cognitive_load_score}/10
TOTAL TIME BUDGET: ~{estimated_minutes} minutes across all tasks

USER CONTEXT:
{_profile_context_block(profile)}

Create 3–5 tasks that, done in order, COMPLETE this milestone.

QUALITY BAR (important):
- Each title starts with an action verb and names a concrete step or artefact
  (e.g. "Write the API endpoint for task routing", NOT "Work on backend").
- Each task is finishable in ONE focused session (15–60 minutes).
- Order tasks so each builds on the previous one.
- No vague filler ("work on", "handle", "misc"), no duplicates, no trivial 5-minute busywork.
- Lighter setup/review tasks get lower load; the core build step gets the highest load.

Assign cognitive_load_score (1–10) and estimated_minutes (15–60) per task.
The sum of estimated_minutes should be roughly {estimated_minutes} (±20%).

Respond ONLY with a JSON array — no markdown:
[{{"title": "<verb-first task, max 12 words>", "cognitive_load_score": <int 1-10>, "estimated_minutes": <int 15-60>}}]"""

    try:
        raw = model_router.generate_json_array("goal_decompose", contents=prompt)
        tasks = normalize_task_specs(
            raw,
            default_load=max(1, min(10, cognitive_load_score)),
            default_minutes=max(15, min(60, estimated_minutes // 3 or 30)),
            max_items=5,
        )
        if len(tasks) < 2:
            return fallback_milestone_tasks(milestone_title, cognitive_load_score, estimated_minutes)
        return tasks
    except Exception as exc:
        if _is_quota_error(exc):
            return fallback_milestone_tasks(milestone_title, cognitive_load_score, estimated_minutes)
        raise


# ---------------------------------------------------------------------------
# Brain dump parser
# ---------------------------------------------------------------------------

def parse_brain_dump(raw_text: str, profile: dict) -> list[dict]:
    """
    Parse free-form brain dump text into structured tasks with load scores.

    Returns: [{ title, cognitive_load_score }, ...]
    """
    prompt = f"""You are a productivity AI that parses a user's messy brain dump into clean, structured tasks.

USER ROLE: {profile.get('role', 'professional')}

BRAIN DUMP:
\"\"\"{raw_text}\"\"\"

Parse this into individual, concrete tasks. Assign each a cognitive_load_score (1–10):
  - 1–3: Light  (quick replies, admin, reading)
  - 4–6: Moderate (regular work, meetings prep)
  - 7–10: Deep work (writing, building, strategy)

Rules:
- Ignore vague mentions that aren't real tasks (e.g. "figure out" → make it concrete)
- Merge duplicates
- Max 10 tasks

Respond ONLY with a JSON array — no markdown, no explanation:
[{{"title": "<task title, max 10 words>", "cognitive_load_score": <int 1-10>}}]"""

    return model_router.generate_json_array("brain_dump_parse", contents=prompt)


def break_down_task(
    task_title: str,
    energy_level: str,
    energy_score: int,
    profile: dict,
) -> list[dict]:
    """
    Split a task into 3–5 micro-steps sized to the user's current cognitive energy.

    Returns: [{ text: str }, ...]
    """
    if energy_score <= 3 or energy_level == "low":
        sizing = (
            "User has LOW energy. Each step must be tiny (2–5 minutes), purely mechanical, "
            "no deep thinking. Prefer 3 steps max."
        )
    elif energy_score <= 6 or energy_level == "balanced":
        sizing = (
            "User has BALANCED energy. Each step should take 10–20 minutes and stay concrete."
        )
    else:
        sizing = (
            "User has HIGH energy. Steps can be substantive (20–40 minutes) but still sequential."
        )

    prompt = f"""Break this task into micro-steps for immediate execution.

TASK: "{task_title}"
USER ROLE: {profile.get('role', 'professional')}
CURRENT ENERGY: {energy_level} ({energy_score}/10)
{sizing}

Rules:
- Return 3–5 steps (fewer for low energy)
- Each step: one line, max 15 words, starts with a verb
- No intro text, no encouragement — steps only
- Steps must be distinct and completable in order

Respond ONLY with a JSON array:
[{{"text": "<step>"}}]"""

    raw = model_router.generate_json_array("micro_step", contents=prompt)
    steps = []
    for item in raw:
        if isinstance(item, dict):
            text = item.get("text") or item.get("title") or item.get("step")
            if text:
                steps.append({"text": str(text).strip()[:120]})
        elif isinstance(item, str) and item.strip():
            steps.append({"text": item.strip()[:120]})
    return steps[:5] if steps else [{"text": f"Start: {task_title[:60]}"}]


def split_task_for_energy(
    task_title: str,
    parent_load: int,
    energy_score: int,
    effective_capacity: int,
    profile: dict,
) -> list[dict]:
    """
    Split an overloaded task into ordered subtasks with individual cognitive loads.

    Returns: [{ title, cognitive_load_score, step_order }, ...]
    """
    prompt = f"""Split this task into 3-5 sequential subtasks, each with its own cognitive load.

PARENT TASK: "{task_title}" (overall difficulty {parent_load}/10)
USER ENERGY NOW: {energy_score}/10
EFFECTIVE CAPACITY: {effective_capacity}/10 (CLCS routing threshold: subtasks with load > capacity+2 are blocked)

USER ROLE: {profile.get('role', 'professional')}

Rules:
- Return 3-5 subtasks in execution order (step_order 1, 2, 3…)
- Include BOTH light parts doable now (load ≤ {effective_capacity + 2}) AND heavier parts for a future high-energy window
- At least one subtask must be doable at current capacity
- At least one subtask must require noticeably more energy than today
- Each title: max 12 words, starts with a verb
- cognitive_load_score must be integer 1-10

Respond ONLY with a JSON array:
[{{"title": "<subtask>", "cognitive_load_score": <int>, "step_order": <int>}}]"""

    try:
        raw = model_router.generate_json_array("task_split", contents=prompt)
    except Exception:
        raw = []

    subtasks: list[dict] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("text")
        if not title:
            continue
        try:
            load = int(item.get("cognitive_load_score", 5))
        except (TypeError, ValueError):
            load = 5
        order = item.get("step_order")
        try:
            order = int(order)
        except (TypeError, ValueError):
            order = i + 1
        subtasks.append({
            "title": str(title).strip()[:120],
            "cognitive_load_score": max(1, min(10, load)),
            "step_order": order,
        })

    if len(subtasks) >= 2:
        subtasks.sort(key=lambda s: s["step_order"])
        return subtasks[:5]

    return _heuristic_split(task_title, parent_load, effective_capacity)


def _heuristic_split(task_title: str, parent_load: int, effective_capacity: int) -> list[dict]:
    """Rule-based fallback when AI split is unavailable."""
    light = max(1, min(effective_capacity, parent_load - 3))
    medium = max(1, min(effective_capacity + 1, parent_load - 1))
    heavy = min(10, max(parent_load, effective_capacity + 3))
    deep = min(10, max(parent_load, effective_capacity + 4))
    return [
        {"title": f"Gather materials for: {task_title[:40]}", "cognitive_load_score": light, "step_order": 1},
        {"title": f"Draft outline for: {task_title[:45]}", "cognitive_load_score": medium, "step_order": 2},
        {"title": f"Work through core of: {task_title[:40]}", "cognitive_load_score": heavy, "step_order": 3},
        {"title": f"Finish and review: {task_title[:45]}", "cognitive_load_score": deep, "step_order": 4},
    ]


def chat_with_copilot(system_context: str, user_message: str) -> dict:
    """
    Send a user message to Gemini with the full co-pilot system context.
    Returns { reply, suggested_tasks, suggested_milestones, ai_fallback }.
    """
    format_rules = """
RESPONSE FORMAT (mandatory):
Reply with ONLY valid JSON — no markdown fences, no text outside the JSON:
{"reply": "<warm conversational message, max 120 words>", "suggested_milestones": [{"title": "<milestone, max 12 words>", "cognitive_load_score": <1-10>, "estimated_minutes": <30-120>, "tasks": [{"title": "<task, max 12 words>", "cognitive_load_score": <1-10>, "estimated_minutes": <15-60>}]}]}

Rules for suggested_milestones:
- Include 1-2 milestones when the user asks for ideas, planning help, what to focus on, or proactive guidance.
- Each milestone groups 2-4 related tasks that together complete meaningful work today.
- Tasks MUST connect to the user's active goals and recent Co-Pilot conversation.
- Do NOT suggest unrelated busywork unless explicitly asked.
- Match loads to CURRENT energy in context: low (1-4), balanced (3-6), high (6-10).
- Use an empty array [] for pure Q&A when no new work is appropriate.
"""

    try:
        text = model_router.generate_text(
            "copilot_chat",
            contents=user_message,
            system_instruction=system_context + format_rules,
        )
        data = _extract_json(text)
        milestones = normalize_copilot_milestones(data)
        flat_tasks = []
        for m in milestones:
            flat_tasks.extend(m.get("tasks") or [])
        reply = str(data.get("reply", "")).strip()
        if not reply:
            reply = "Here's what I'd suggest for today."
        return {
            "reply": reply,
            "suggested_tasks": flat_tasks,
            "suggested_milestones": milestones,
            "ai_fallback": False,
        }
    except Exception as exc:
        if _is_quota_error(exc):
            milestones = normalize_copilot_milestones({
                "suggested_milestones": [{
                    "title": "Today's focus",
                    "cognitive_load_score": 5,
                    "estimated_minutes": 60,
                    "tasks": [
                        {"title": "Continue highest-priority goal work", "cognitive_load_score": 5, "estimated_minutes": 30},
                        {"title": "Ship one visible progress item", "cognitive_load_score": 6, "estimated_minutes": 30},
                    ],
                }],
            })
            return {
                "reply": (
                    "AI quota reached for today — here are rule-based milestone suggestions. "
                    "They'll reset tomorrow, or enable billing in Google AI Studio."
                ),
                "suggested_tasks": [t for m in milestones for t in m.get("tasks", [])],
                "suggested_milestones": milestones,
                "ai_fallback": True,
            }
        return {
            "reply": "I had trouble generating a structured plan. Try again in a moment.",
            "suggested_tasks": [],
            "suggested_milestones": [],
            "ai_fallback": True,
        }
