├── analysis/          # Thesis data analysis
└── thesis/            # Thesis document generation
```

---

## Getting started (development)

### Prerequisites
- Node.js 20+
- Python 3.11+
- Supabase project ([supabase.com](https://supabase.com))
- Google Cloud OAuth credentials (Calendar API)
- ClickUp OAuth app (optional)
- Gemini API key ([Google AI Studio](https://aistudio.google.com))

### 1. Database
Run `database/schema.sql` in Supabase SQL Editor, then apply migrations in `database/migrations/` in order.

### 2. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in keys (see below)
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
# Freeside

Energy-aware productivity for freelancers, students, founders, and knowledge workers.

Freeside is a full-stack AI productivity system that helps people plan work around their real cognitive energy, calendar load, goals, and project context. It combines an energy-aware task router, a context-rich AI Co-Pilot, semantic project memory, Google Calendar and ClickUp integrations, goal/milestone planning, and wellbeing analytics into one workflow.

The project began as a bachelor's thesis proof-of-concept and is being productized as a B2C application for people who manage complex work without a traditional team structure.

## What Freeside Does

Freeside answers a simple but painful question:

> What should I realistically work on right now?

Most productivity tools treat every task and hour as equal. Freeside does not. It uses the user's current energy, peak-focus window, meeting load, task difficulty, goals, and recent AI conversation context to decide what should be active, what should wait, and what should be split into lighter pieces.

## Core Product Features

### Energy Check-In

Users start the day by confirming their cognitive energy.

Freeside supports:

- Manual energy check-ins from 1 to 10
- Energy level classification: low, balanced, high
- AI-suggested energy from Google Calendar, ClickUp workload, and recent Co-Pilot context
- Manual override so the user always stays in control
- Per-user calibration that tracks the gap between AI suggestions and confirmed energy
- Sleep logging as additional wellbeing context

### CLCS Task Routing

Freeside includes a custom Cognitive Load Contextual Scheduling algorithm, or CLCS.

Each task has a cognitive load score from 1 to 10. CLCS compares this score against the user's effective capacity for the day.

The router considers:

- Confirmed energy score
- Peak-focus time boost
- Cognitive load score
- Goal alignment
- Day-plan focus
- Quick-win potential
- Existing milestone/task hierarchy

The router returns:

- Active tasks that fit the user's current capacity
- Deferred tasks that require higher energy
- Unlock scores for blocked tasks
- Explanations for rerouting
- Milestone task groups
- Future tasks that can unlock later

### Task Management

Freeside supports standard task workflows plus AI-assisted task creation.

Users can:

- Create tasks manually
- Add descriptions and cognitive load scores
- Edit task title, description, and load
- Delete tasks
- Complete tasks
- Earn XP based on task difficulty
- View completed task history
- Split difficult tasks into subtasks
- See blocked subtasks separately from doable subtasks
- Review tasks routed by energy level

### Brain Dump Parsing

Users can paste a messy list of everything on their mind. Freeside parses it into structured tasks.

The brain-dump parser:

- Extracts concrete tasks from free text
- Assigns cognitive load scores
- Removes duplicates and vague items
- Suggests links to semantically similar active goals
- Lets users review and select tasks before saving

### Goals And Milestones

Freeside supports multi-day planning through goals, milestones, and child tasks.

Users can:

- Create up to three active goals
- Generate AI milestone proposals for a goal
- Preview a schedule across predicted energy capacity
- Confirm milestones before saving
- Track milestone progress
- Track goal progress
- Break milestones into child tasks
- Route milestone tasks through CLCS

The goal planner uses:

- User profile
- Work style
- Peak focus time
- Energy history
- Calendar availability
- AI decomposition
- Rule-based fallback when AI quota is unavailable

### AI Co-Pilot

The Freeside Co-Pilot is a context-aware planning assistant built around the user's actual work state.

It can:

- Answer planning questions
- Suggest what to work on today
- Generate task cards
- Generate milestones and child tasks
- Break tasks into micro-steps
- Adjust suggestions to current energy
- Speak in the user's language, including Georgian or English
- Use recent conversation as context
- Include structured output for the UI to parse
- Propose actions without writing back until the user confirms

The Co-Pilot context includes:

- User profile
- Energy history
- Google Calendar data
- ClickUp tasks
- Active goals
- Pending tasks
- Recent Co-Pilot turns
- Semantic memory
- Burnout risk context

### Project Memory And Planning Agent

Project Memory is Freeside's RAG-powered planning layer.

Users can paste messy work context such as:

- Client briefs
- Product notes
- Thesis notes
- Meeting summaries
- Requirements
- Personal project plans
- Brainstorming notes

Freeside stores this context as chunked, embedded memory. Later, the user can ask a planning question such as:

- "What should I move forward next?"
- "What am I forgetting?"
- "Turn this project context into milestones."
- "What can I do with low energy today?"
- "Which parts are blocked?"

The Project Memory agent retrieves relevant context and produces:
