"""
AI service — Anthropic Claude integration for energy inference and co-pilot chat.
"""
import anthropic
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def infer_energy_from_calendar(calendar_summary: dict, user_profile: dict) -> dict:
    """
    Ask Claude to infer the user's likely energy level based on today's schedule.
    Returns: { suggested_score, suggested_level, reasoning }
    """

    prompt = f"""
You are analyzing a user's calendar to estimate their cognitive energy level for today.

USER PROFILE:
- Peak focus time: {user_profile.get('peak_focus_time', 'unknown')}
- Work style: {user_profile.get('work_style', 'unknown')}
- Typical daily hours: {user_profile.get('daily_work_hours', 'unknown')}

TODAY'S CALENDAR:
- Number of meetings/events: {calendar_summary['event_count']}
- Total time in meetings: {calendar_summary['total_meeting_minutes']} minutes
- Back-to-back meetings (less than 15 min gap): {calendar_summary['back_to_back_count']}
- Events:
{calendar_summary['event_list']}

Based on this schedule, estimate the user's available cognitive energy for focused work today.

Consider:
- More meetings = less energy for deep work
- Back-to-back meetings = high mental load
- Heavy meeting days leave little energy for strategic tasks
- Light calendars = more capacity for complex work

Respond ONLY in this exact JSON format, nothing else:
{{
  "suggested_score": <integer 1-10>,
  "suggested_level": "<high|balanced|low>",
  "reasoning": "<one sentence explanation, max 20 words, conversational tone>"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )

    return json.loads(response.content[0].text)  # type: ignore


def build_copilot_context(user_id: str, supabase) -> str:
    """
    Build a rich context string from the user's current state for the co-pilot.
    Includes profile, energy, goals, tasks, and all connected integrations.
    """
    # Get user profile
    profile = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

    # Get current energy
    energy_log = (
        supabase.table("energy_logs")
        .select("*")
        .eq("user_id", user_id)
        .order("logged_at", desc=True)
        .limit(1)
        .execute()
    )
    energy = energy_log.data[0] if energy_log.data else None

    # Get active goals
    goals = (
        supabase.table("goals")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .execute()
    )
    goals_text = (
        "\n".join([f"- {g['title']} ({g.get('category', 'general')}, {g.get('timeframe', '')})" for g in goals.data])
        if goals.data
        else "Not set yet"
    )

    # Get pending tasks
    tasks = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )
    task_list = (
        "\n".join(
            [f"- {t['title']} (load: {t.get('cognitive_load_score', '?')}/10)" for t in tasks.data]
        )
        if tasks.data
        else "No pending tasks"
    )

    # Get connected integrations for richer personal context
    integrations_result = (
        supabase.table("user_integrations")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_connected", True)
        .execute()
    )
    integrations_text = _format_integrations(integrations_result.data if integrations_result.data else [])

    energy_level = energy["confirmed_level"] if energy else "unknown"
    energy_score = energy["confirmed_score"] if energy else "unknown"
    work_style = profile.get("work_style", "unknown")
    peak_focus = profile.get("peak_focus_time", "unknown")
    daily_hours = profile.get("daily_work_hours", "unknown")
    role = profile.get("role", "unknown")

    return f"""You are the Freeside AI Co-Pilot. You are a calm, empathetic, highly personalised productivity coach.

USER PROFILE:
- Name: {profile.get('name', 'User')}
- Role: {role}
- What a productive day looks like for them: {profile.get('productive_day_description', 'Not specified')}
- Peak focus time: {peak_focus}
- Work style: {work_style}
- Daily working hours: {daily_hours}h

CURRENT STATE:
- Energy level: {energy_level} ({energy_score}/10)
- Active goals:
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
- Reference their actual tasks, goals, energy level, and tools in your responses.
- Use the user's work style and peak focus time to time your suggestions appropriately.
- If the user has connected tools (ClickUp, Asana, Obsidian, AI agents), reference them naturally.
"""


def _format_integrations(integrations: list) -> str:
    """Format connected integrations into a readable context block for the AI."""
    if not integrations:
        return "No external tools connected yet."

    lines = []
    labels = {
        "clickup": "ClickUp (task management)",
        "asana": "Asana (project management)",
        "obsidian": "Obsidian (knowledge base)",
        "notes": "Notes & personal context",
        "ai_agents": "AI Agents",
    }

    for intg in integrations:
        itype = intg.get("integration_type", "")
        label = labels.get(itype, itype)
        workspace = intg.get("workspace_name", "")
        notes = intg.get("context_notes", "")
        has_token = bool(intg.get("api_token"))

        line = f"- {label}"
        if workspace:
            line += f" | Workspace: {workspace}"
        if has_token:
            line += " | API connected"
        if notes:
            line += f"\n  Context: {notes}"
        lines.append(line)

    return "\n".join(lines)


def chat_with_copilot(system_context: str, user_message: str) -> str:
    """Send a message to the AI co-pilot with full user context."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=system_context,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text  # type: ignore
