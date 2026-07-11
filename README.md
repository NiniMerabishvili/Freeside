# Freeside

**Energy-aware productivity for freelancers, students, founders, and knowledge workers.**

Freeside is a full-stack AI productivity system that helps people plan their work around real cognitive energy, calendar load, goals, and project context — rather than a flat to-do list. It combines an energy-aware task router, a context-rich AI Co-Pilot, semantic project memory, Google Calendar and ClickUp integrations, goal and milestone planning, and wellbeing analytics into a single workflow.

Freeside began as a bachelor's thesis proof-of-concept and is now being productized as a B2C application for people who manage complex, self-directed work without the structure of a traditional team.

---

## What Freeside Does

Freeside is built around one question:

> *What should I realistically work on right now?*

Most productivity tools treat every task and every hour as equal. Freeside doesn't. It weighs the user's current energy, peak-focus window, meeting load, task difficulty, goals, and recent conversation context to decide what should be active, what should wait, and what should be broken into lighter pieces.

---

## Core Product Features

### Energy Check-In

Each day starts with a quick confirmation of cognitive energy, which drives everything downstream.

- Manual check-ins on a 1–10 scale, classified as low, balanced, or high
- AI-suggested energy inferred from Google Calendar, ClickUp workload, and recent Co-Pilot context
- Manual override always available — the user stays in control
- Per-user calibration that learns the gap between AI-suggested and confirmed energy over time
- Optional sleep logging for additional wellbeing context

### CLCS Task Routing

Freeside's core scheduling logic is a custom algorithm — Cognitive Load Contextual Scheduling (CLCS).

Every task carries a cognitive load score from 1 to 10, which CLCS compares against the user's effective capacity for the day. Routing accounts for:

- Confirmed energy score
- Peak-focus time boost
- Task cognitive load
- Goal alignment
- Day-plan focus
- Quick-win potential
- Existing milestone and task hierarchy

Based on this, CLCS returns:

- Active tasks that fit current capacity
- Deferred tasks that require more energy, with unlock scores
- Explanations for why a task was rerouted
- Milestone task groupings
- Future tasks that unlock as capacity changes

### Task Management

Standard task workflows are extended with AI assistance throughout.

- Create, edit, and delete tasks, including title, description, and cognitive load
- Complete tasks and earn XP scaled to difficulty
- View completed task history
- Split difficult tasks into subtasks, with blocked and doable subtasks shown separately
- Review tasks routed by current energy level

### Brain Dump Parsing

Users can paste an unstructured list of everything on their mind, and Freeside turns it into structured tasks.

- Extracts concrete, actionable tasks from free text
- Assigns cognitive load scores automatically
- Removes duplicates and vague or non-actionable items
- Suggests links to semantically similar existing goals
- Lets users review and select which extracted tasks to save

### Goals and Milestones

Freeside supports multi-day planning through a goal → milestone → task hierarchy.

- Up to three active goals at a time
- AI-generated milestone proposals for each goal
- Schedule preview across predicted energy capacity
- User confirmation required before milestones are saved
- Goal and milestone progress tracking
- Milestones broken into child tasks, which route through CLCS like any other task

The goal planner draws on the user's profile, work style, peak focus time, energy history, and calendar availability, using AI-driven decomposition with a rule-based fallback when AI quota is unavailable.

### AI Co-Pilot

The Co-Pilot is a context-aware planning assistant built around the user's actual, current work state — not a generic chat interface.

It can:

- Answer planning questions and suggest what to work on today
- Generate task cards, milestones, and child tasks
- Break tasks into micro-steps
- Adjust suggestions to current energy
- Respond in the user's language, including Georgian and English
- Use recent conversation history as context
- Return structured output the UI can parse directly
- Propose actions for confirmation rather than writing them back automatically

Each Co-Pilot turn is grounded in a live context bundle covering the user's profile, energy history, Google Calendar data, ClickUp tasks, active goals, pending tasks, recent Co-Pilot turns, semantic memory, and burnout risk.

### Project Memory and Planning Agent

Project Memory is Freeside's RAG-powered planning layer.

Users can paste in messy work context — client briefs, product notes, thesis notes, meeting summaries, requirements, personal project plans, or brainstorming notes — and Freeside stores it as chunked, embedded memory tied to their account.

From there, users can ask planning questions such as:

- "What should I move forward next?"
- "What am I forgetting?"
- "Turn this project context into milestones."
- "What can I do with low energy today?"
- "Which parts are blocked?"

The Project Memory agent retrieves the most relevant stored context for the question, then returns a grounded answer that references the specific notes it drew from, along with concrete suggested next actions, milestones, or task links back into the user's existing goals — rather than a generic response disconnected from their actual project state.

---

## Getting Started (Development)

### Prerequisites

- Node.js 20+
- Python 3.11+
- A Supabase project ([supabase.com](https://supabase.com))
- Google Cloud OAuth credentials (Calendar API)
- A ClickUp OAuth app (optional)
- A Gemini API key ([Google AI Studio](https://aistudio.google.com))

### 1. Database

Run `database/schema.sql` in the Supabase SQL Editor, then apply the migrations in `database/migrations/` in order.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # fill in keys below
uvicorn main:app --reload --port 8000
```

**`backend/.env` keys:**

```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
GEMINI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
CLICKUP_CLIENT_ID=
CLICKUP_CLIENT_SECRET=
```
