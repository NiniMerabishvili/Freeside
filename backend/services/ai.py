"""
AI service — Google Gemini (google-genai SDK) for energy inference and co-pilot chat.
"""
import json
import os
import re
from pathlib import Path

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
_MODEL = "gemini-2.5-flash"


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

    response = _client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=300,
            temperature=0.4,
            # Disable thinking for structured JSON inference — saves tokens
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return _extract_json(response.text)


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

RECENT CO-PILOT CHAT ACTIVITY:
{copilot_block}

SCORING RULES (combine ALL sources):
- Heavy meeting day + many urgent/overdue ClickUp items → lower score (2-5)
- Open calendar + moderate ClickUp → balanced (5-7)
- Light meetings + few tasks + user recently asked for light work in Co-Pilot → higher (7-9)
- If Co-Pilot shows repeated low-energy or break-down requests, reduce score by 1-2
- All-day calendar markers are NOT meetings

Respond ONLY with this exact JSON — no markdown fences:
{{"suggested_score": <integer 1-10>, "suggested_level": "<high|balanced|low>", "reasoning": "<one sentence max 25 words mentioning calendar and/or ClickUp if relevant>"}}"""

    response = _client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=300,
            temperature=0.4,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return _extract_json(response.text)


# ---------------------------------------------------------------------------
# Co-pilot context builder
# ---------------------------------------------------------------------------

def build_copilot_context(user_id: str, supabase) -> str:
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
            .select("*")
            .eq("user_id", user_id)
            .eq("is_connected", True)
            .execute()
        )
        integrations_text = _format_integrations(
            integrations_result.data if integrations_result.data else []
        )
    except Exception:
        integrations_text = "No external tools connected yet."

    energy_level = energy["confirmed_level"] if energy else "unknown"
    energy_score = energy["confirmed_score"] if energy else "unknown"

    calendar_block = "No calendar data logged today."
    if energy:
        event_count = energy.get("calendar_event_count")
        calendar_ctx = energy.get("calendar_context")
        if event_count is not None or calendar_ctx:
            calendar_block = f"""- Meetings today: {event_count or 0}
- Schedule summary:
{calendar_ctx or 'Not available'}"""

    from services.clickup import get_clickup_context_from_db
    clickup_block = get_clickup_context_from_db(supabase, user_id)

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
- Reference the user's actual tasks, goals, energy level, calendar, and ClickUp workload in every response.
- When planning the day, prioritise ClickUp items that are due today or overdue IF they match current energy.
- Prefer ClickUp + calendar together: schedule deep work in open calendar blocks, light ClickUp admin in low-energy windows.
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
        if intg.get("api_token"):
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

def decompose_goal(goal_title: str, category: str, timeframe: str, profile: dict) -> list[dict]:
    """
    Break a user goal into 5–8 structured tasks with cognitive load scores.

    Returns: [{ title, cognitive_load_score, reasoning }, ...]
    """
    prompt = f"""You are a productivity AI helping a user break down a goal into concrete tasks.

GOAL: "{goal_title}"
CATEGORY: {category}
TIMEFRAME: {timeframe}
USER ROLE: {profile.get('role', 'professional')}

Generate 5–8 specific, immediately actionable tasks that would help achieve this goal.
Assign each a cognitive_load_score (1–10):
  - 1–3: Light  (admin, research, reading, quick emails)
  - 4–6: Moderate (meetings, planning, standard work)
  - 7–10: Deep work (strategic writing, complex building, design decisions)

Respond ONLY with a JSON array — no markdown, no explanation:
[{{"title": "<task title, max 10 words>", "cognitive_load_score": <int 1-10>, "reasoning": "<why this load score, max 8 words>"}}]"""

    response = _client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=800,
            temperature=0.5,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return _extract_json_array(response.text)


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

    response = _client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=600,
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return _extract_json_array(response.text)


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

    response = _client.models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=400,
            temperature=0.4,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    raw = _extract_json_array(response.text)
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
        response = _client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=500,
                temperature=0.4,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = _extract_json_array(response.text)
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
    Returns { reply: str, suggested_tasks: [{ title, cognitive_load_score }] }.
    """
    format_rules = """
RESPONSE FORMAT (mandatory):
Reply with ONLY valid JSON — no markdown fences, no text outside the JSON:
{"reply": "<warm conversational message, max 120 words>", "suggested_tasks": [{"title": "<max 10 words>", "cognitive_load_score": <1-10>}]}

Rules for suggested_tasks:
- Include 2-4 tasks when the user asks for ideas, planning help, what to focus on, light options, or proactive energy guidance.
- Match loads to current energy: low (1-3), balanced (3-6), high (6-10).
- Each task must be actionable today and distinct.
- Use an empty array [] for pure Q&A or when no new tasks are appropriate.
"""

    try:
        response = _client.models.generate_content(
            model=_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_context + format_rules,
                max_output_tokens=700,
                temperature=0.7,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        data = _extract_json(response.text)
        tasks = []
        for t in data.get("suggested_tasks") or []:
            if isinstance(t, dict) and t.get("title"):
                score = t.get("cognitive_load_score", 5)
                try:
                    score = int(score)
                except (TypeError, ValueError):
                    score = 5
                tasks.append({
                    "title": str(t["title"]).strip()[:80],
                    "cognitive_load_score": max(1, min(10, score)),
                })
        reply = str(data.get("reply", "")).strip()
        if not reply:
            reply = "Here's what I'd suggest for today."
        return {"reply": reply, "suggested_tasks": tasks}
    except Exception:
        # Fallback: plain-text reply, no structured tasks
        response = _client.models.generate_content(
            model=_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_context,
                max_output_tokens=500,
                temperature=0.7,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return {"reply": response.text.strip(), "suggested_tasks": []}
