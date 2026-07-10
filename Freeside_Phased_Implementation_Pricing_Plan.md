# Freeside — Detailed Implementation & Pricing Plan (B2C Launch)

Working assumption, stated explicitly since it drives everything below: **B2C**, single product, primary wedge = **freelancers and independent knowledge workers**, with ADHD/neurodivergent-adjacent communities as a secondary high-intent acquisition channel for the same product (not a separate SKU). If that's not the right wedge, the onboarding copy and Phase 6 channel choices change, but the technical phases (0–4) don't.

All AI/infra prices below were checked against current provider pages (July 2026) rather than pulled from memory, since token pricing moves often. Infra prices (Vercel/Railway/Stripe/domains) are standard published rates but worth a quick re-check before you commit a budget, since they move too, just less frequently.

---

## AI Model Cost Baseline (verify-once, use-everywhere)

| Model | Input $/1M tok | Output $/1M tok | Use in Freeside |
|---|---|---|---|
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | Energy inference, classification/routing |
| Gemini 2.5 Flash | $0.30 | $2.50 | Goal decomposition, brain-dump parsing, micro-step generation |
| Claude Haiku 4.5 | $1.00 | $5.00 | Budget conversational tier / proactive nudges |
| Claude Sonnet 4.6 | $3.00 | $15.00 | Co-Pilot open-ended chat, agentic tool-calling |
| Gemini text-embedding-001 | $0.15 (batch: $0.075) | — | RAG embeddings (goals, tasks, chat history) |

**Per-active-user monthly AI cost, worked out from realistic usage:**

| Feature | Usage assumption | Model | Monthly cost/user |
|---|---|---|---|
| Energy inference | 1×/day, ~600 in + 120 out tokens | Flash-Lite | ~$0.003 |
| Co-Pilot chat | 10 messages/mo, ~2,500 in + 350 out tokens | Sonnet 4.6 | ~$0.13 |
| Goal decomposition / brain dump | 4×/mo, ~1,800 in + 400 out tokens | Flash | ~$0.006 |
| RAG embeddings | ~5,000 tokens/mo indexed | Embedding | ~$0.001 |
| **Total** | | | **~$0.14–0.20/active user/month** |

This is the number to put in a pitch deck: **even a heavy user costs well under $0.25/month in model inference**, against a subscription price of $6–15/month (see pricing tiers below). AI cost is not the constraint on this business — acquisition and retention are. Budget lines below use $0.20/user/month as a conservative planning figure, then round up generously for safety margin.

---

## Phase 0 — Trust & Reliability Foundation
**Goal:** stop shipping on a prototype's assumptions before real strangers' calendars and payment info touch this.

### Implementation detail
1. **Encrypt secrets at rest.** Migrate `profiles.google_refresh_token` and `user_integrations.api_token` from plain `TEXT` to `pgcrypto`-encrypted columns (Supabase supports this natively), or move them to a dedicated `secrets` table with column-level encryption and a service-role-only read policy. Write the migration, update the two read paths (`services/calendar.py`, `services/clickup.py`) to decrypt on fetch.
2. **Typed error surfacing.** Replace the `except Exception: return None/False` patterns in `day_context.py`/`calendar.py` with typed results (`CalendarSyncError`, `ClickUpAuthError`) that the frontend renders as a visible, dismissible banner ("Calendar sync failed — using manual energy today") instead of silently degrading.
3. **Pydantic schema validation on every AI JSON response**, with one bounded retry (re-prompt including the validation error) before falling back to a safe default.
4. **Test suite.** Unit tests for `route_tasks` (pure function, trivial to cover exhaustively), `xp.py`, `router.py` edge cases (empty task list, all-rerouted, peak-window boundary). Integration test for the energy → routing → completion → XP pipeline against a test Supabase project.
5. **CI.** GitHub Actions: lint (ruff/eslint) + pytest + `next build` on every push; block merge on failure.

### Timeline
2–3 weeks solo, working around existing coursework/other commitments.

### Cost

| Item | Type | Cost |
|---|---|---|
| GitHub Actions | recurring | $0 (public repo, or within free private-repo minutes) |
| pgcrypto / Supabase encryption | recurring | $0 (included in Supabase plan) |
| Developer time | one-time | 2–3 weeks, your own time — no cash cost if solo |
| **Phase 0 total** | | **$0 cash, ~2–3 weeks time** |

---

## Phase 1 — Model Tiering, Structured Output, Cost Control

### Implementation detail
1. **Model router module** (`services/model_router.py`): a small config-driven dispatcher mapping task type → provider/model, so switching a tier later is a one-line config change, not a code hunt. Task types: `energy_inference`, `goal_decompose`, `brain_dump_parse`, `micro_step`, `copilot_chat`, `copilot_action`.
2. **Structured output via native schema/tool-forcing** instead of prompt-level "respond only in JSON" — use Gemini's `response_schema` param for the Flash-tier calls, and Claude's forced tool-use pattern for anything routed to Sonnet.
3. **Caching layer.** Redis (or Supabase's own Postgres as a cheap substitute at this scale) caches same-day energy suggestions keyed by `user_id + date`; invalidate on calendar reconnect or manual override.
4. **Fallback chain.** If Gemini errors/times out on `energy_inference`, retry once against Claude Haiku with the same schema before surfacing a manual-entry fallback to the user.
5. **Cost/latency logging.** Every AI call writes `{task_type, model, tokens_in, tokens_out, latency_ms, cache_hit}` to a new `ai_usage_logs` table — cheap to build now, and it's the data source for the observability dashboard in a later phase.

### Timeline
2 weeks.

### Cost

| Item | Type | Cost |
|---|---|---|
| Redis (Upstash free tier, or skip and use Postgres) | recurring | $0–10/mo |
| AI inference (see baseline table above) | recurring, scales with users | ~$0.20/active user/mo |
| Developer time | one-time | 2 weeks |
| **Phase 1 total (at 100 users)** | | **~$20–30/mo** |

---

## Phase 2 — Agentic Co-Pilot (tool-calling + calendar write-back)

### Implementation detail
1. **Define tool schemas**: `create_task`, `reschedule_task`, `break_down_task`, `query_completion_history`, `write_calendar_event`. Use Claude's native tool-use (function calling) format, since Sonnet is the routed model for chat.
2. **Confirmation UX, not silent action.** Every state-changing tool call (create/reschedule/calendar-write) returns a proposed action to the frontend for one-tap confirm/edit/reject before it executes — this is both a trust requirement and a legal/consent requirement once you're writing to someone's real calendar.
3. **Google Calendar write scope.** Extend the existing OAuth flow from `calendar.readonly` to `calendar.events` (write); this requires re-consent from existing connected users and, if you exceed Google's unverified-app user cap, an OAuth verification review submission (see cost table — this is a real line item, not just engineering time).
4. **Tool-call loop.** Standard multi-turn loop: send message + tool defs → model requests a tool → backend executes against Supabase/Calendar API → result returned to model → model produces final natural-language confirmation.
5. **Guardrails specific to this feature:** rate-limit tool calls per session (stop a runaway loop from creating 50 tasks), and explicitly refuse calendar-write actions outside a sanity window (e.g., won't schedule into the past, won't double-book an existing event).

### Timeline
3–4 weeks (calendar write-back and the confirmation UX are the fiddly parts, not the tool-calling loop itself).

### Cost

| Item | Type | Cost |
|---|---|---|
| Google OAuth verification review (once you exceed ~100 test users or request sensitive scopes) | one-time | $0 (Google doesn't charge, but budget 2–6 weeks calendar time for review — plan this early, it's a timeline risk, not a cash one) |
| Additional Sonnet-tier tokens for tool-calling overhead (~+30% tokens per chat turn vs. plain chat) | recurring | ~+$0.04/active user/mo |
| Developer time | one-time | 3–4 weeks |
| **Phase 2 total (at 100 users)** | | **~$17/mo incremental** |

---

## Phase 3 — RAG over pgvector

### Implementation detail
1. **Embed on write, not on read.** Every completed task, every Co-Pilot exchange, every goal gets embedded (Gemini `text-embedding-001`, batched) and upserted into a `pgvector` column at write-time — avoids embedding-on-every-query latency and cost.
2. **Semantic goal-matching for brain dump.** When a brain-dump item is parsed, embed it and cosine-match against the user's existing goal embeddings instead of relying on manual category tags; auto-link above a similarity threshold, otherwise prompt the user to confirm.
3. **Retrieval in the Co-Pilot context builder.** Add a fifth query alongside the existing four (profile, goals, energy, tasks): top-k semantically similar past conversations/completed tasks, injected as a short "relevant history" block in the system prompt.
4. **Index maintenance.** `ivfflat` or `hnsw` index on the embedding column once row counts justify it (a few thousand rows per user is fine unindexed; add the index before it's needed, not after a slow-query complaint).

### Timeline
1.5–2 weeks — most of the plumbing (pgvector, Supabase) already exists per the current schema.

### Cost

| Item | Type | Cost |
|---|---|---|
| Embedding tokens | recurring | ~$0.001/user/mo (negligible, see baseline table) |
| Supabase storage (vector columns add modest storage) | recurring | folded into existing Supabase Pro plan up to tens of thousands of rows |
| Developer time | one-time | 1.5–2 weeks |
| **Phase 3 total** | | **effectively $0 incremental** |

---

## Phase 4 — Burnout Prediction + Personalization ML

### Implementation detail
1. **Feature pipeline first, model second.** Build the ETL turning `energy_logs`/`sleep_logs`/`routing_logs`/`session_logs` into rolling 14-day feature windows per user — this is buildable and testable immediately, independent of having enough data to train on yet.
2. **Baseline model.** Logistic regression / gradient-boosted trees (scikit-learn/XGBoost) on the feature windows, trained against a behavioral composite label (sustained reroute rate + declining energy trend + rising abandonment) — cheap to train, easy to explain, good enough to ship first.
3. **LSTM as a later upgrade**, trained and compared against the baseline only once there's enough longitudinal data (meaningfully more than a handful of users over a few weeks) — don't reach for it before the baseline earns its keep.
4. **Per-user calibration layer.** A simple per-user bias-correction term (running average of AI-suggested-vs-confirmed energy delta) applied as a post-processing step on the raw model output — this is a few dozen lines of code, not a new service.
5. **Serving.** Run inference as a nightly batch job (Supabase Edge Function cron or a small scheduled script) rather than real-time — burnout risk doesn't need sub-second latency, and batch keeps this phase cheap.

### Timeline
3–4 weeks for the pipeline + baseline model; treat the LSTM itself as a stretch goal gated on data volume, not a fixed-date deliverable.

### Cost

| Item | Type | Cost |
|---|---|---|
| Training compute | one-time/occasional | $0 (a laptop or free-tier Colab handles this scale of data comfortably) |
| Batch inference job | recurring | $0 (folded into existing Supabase Edge Functions quota) |
| Developer time | one-time | 3–4 weeks |
| **Phase 4 total** | | **$0 cash cost** |

---

## Phase 5 — B2C Productization

### Implementation detail
1. **Billing.** Stripe Checkout + Customer Portal (don't build custom billing UI — use Stripe's hosted flows). Webhook handler updates `profiles.subscription_tier` and `subscription_status` on `checkout.session.completed` / `customer.subscription.updated`/`deleted`.
2. **Pricing tiers in the data model.** Add a `plan` enum (`free`, `pro`, `premium`) to `profiles`; gate features (ClickUp integration, Co-Pilot message volume, calendar write-back) behind plan checks in the relevant route handlers.
3. **Legal.** Terms of Service, Privacy Policy, and a Data Processing note specific to calendar/energy/sleep data (this product handles wellbeing-adjacent signals — treat this as non-optional, not boilerplate). Use a generator (Termly/Rocket Lawyer) for the base documents, then hand-edit the sections describing AI processing and burnout-risk inference specifically, since generic templates won't cover that.
4. **Installable PWA.** Web app manifest + service worker for offline-tolerant shell and "Add to Home Screen" — covers the "used on a phone in practice" reality without native app cost yet.
5. **Onboarding polish.** Turn the existing 4-screen wizard's output into a shareable one-line "work-style profile" result screen (e.g., "Steady Sprinter — morning peak, moderate stretch tolerance") — same data, better first-session feeling.
6. **Referral loop.** Simple "give a free month, get a free month" mechanic — cheap to build (a referral code column + Stripe coupon), disproportionately effective for B2C word-of-mouth in tight communities (ADHD/freelancer forums specifically reward this).

### Timeline
3–4 weeks.

### Cost

| Item | Type | Cost |
|---|---|---|
| Stripe fees | recurring, per-transaction | 2.9% + $0.30 per successful charge (standard published rate — confirm against Georgia-specific Stripe availability/Stripe Atlas needs before committing, since Stripe's direct country support varies) |
| Legal doc generator (Termly Pro or similar) | one-time or recurring | ~$0–200 (many one-time-purchase generators exist in this range; a free generator + your own edits is a viable $0 path at this stage) |
| Domain | recurring (annual) | ~$12–15/yr |
| Design tool (Canva Pro, for onboarding/marketing assets) | recurring | ~$13/mo (or skip — Figma free tier covers most of this) |
| Developer time | one-time | 3–4 weeks |
| **Phase 5 total** | | **~$15–30/mo + Stripe's per-transaction cut** |

---

## Phase 6 — Go-To-Market Launch

### Implementation detail
1. **Landing page** separate from the app shell — one clear page: problem statement, the CLCS routing concept explained in one sentence, screenshots, pricing, waitlist/signup CTA. Ship as a static Next.js page, not a separate stack.
2. **Analytics.** PostHog (generous free tier — product analytics + session replay + feature flags in one tool) instrumented on signup → onboarding-complete → first-task-completed → day-7-return, the funnel that actually matters for a B2C productivity tool.
3. **Support tooling.** Crisp (free tier) or self-hosted Chatwoot for a lightweight chat-support widget — necessary the moment strangers (not friends doing you a favor) start using this.
4. **Launch channels, sequenced:**
   - Product Hunt launch (free, but needs a genuinely polished asset kit — screenshots, a 30-second demo video, a founder comment ready on day one).
   - Targeted posts in freelancer communities (r/freelance, Indie Hackers) and ADHD-productivity communities (r/ADHD productivity threads, ADHD-focused Discord/Slack communities) — framed as "I built this because X," not an ad.
   - A small paid-acquisition test ($200–500) on Meta/Reddit ads targeted at the wedge, purely to get a CAC signal before committing more — treat this as a measurement exercise, not a growth channel yet.
5. **Metrics one-pager**, built from PostHog + Stripe data directly: WAU, D7/D30 retention, activation rate, MRR, CAC (from the paid test) — this is both an internal decision tool and the artifact a grant reviewer or accelerator wants to see.

### Timeline
2–3 weeks for the launch assets/instrumentation; the community/PH launch itself is a single week, high-intensity.

### Cost

| Item | Type | Cost |
|---|---|---|
| PostHog | recurring | $0 (free tier covers early-stage volume comfortably) |
| Crisp / Chatwoot | recurring | $0 (free tier / self-hosted) |
| Product Hunt launch | one-time | $0 |
| Paid acquisition test | one-time | $200–500 (optional, but worth budgeting as a deliberate experiment) |
| Developer/marketing time | one-time | 2–3 weeks |
| **Phase 6 total** | | **$200–500 one-time, ~$0/mo recurring** |

---

## Product Subscription Pricing (what to actually charge)

Given the AI-cost baseline above (~$0.20/active user/month), margin is not the constraint — perceived value and willingness-to-pay for the wedge market are. Freelancers and ADHD-adjacent professionals are price-sensitive but will pay for something that demonstrably protects their output and energy.

| Tier | Price | What's gated |
|---|---|---|
| **Free** | $0 | Manual energy entry only (no calendar AI inference), basic CLCS routing, no Co-Pilot chat, no integrations — functional enough to prove the core loop, not enough to be the whole product |
| **Pro** | $8–10/month (or $80–90/year, ~2 months free) | AI energy inference from calendar, full Co-Pilot chat, goal decomposition, ClickUp integration, XP/gamification |
| **Premium** | $15–18/month | Everything in Pro + calendar write-back, burnout-risk insights (once Phase 4 ships), priority support, multiple integrations (Asana/Notion once built) |

This sits below Sunsama (~$20/mo) and above nothing-comparable-exists-at-this-price for the energy-routing feature specifically — reasonable initial positioning, to be validated against actual willingness-to-pay data from the first 100 users rather than treated as fixed.

---

## Master Summary — Cost & Timeline Across All Phases

| Phase | Timeline | One-time cash cost | Recurring cost (at ~100 users) |
|---|---|---|---|
| 0 — Trust & reliability | 2–3 wks | $0 | $0 |
| 1 — Model tiering | 2 wks | $0 | ~$20–30/mo |
| 2 — Agentic Co-Pilot | 3–4 wks | $0 (+ OAuth review lead time) | +~$17/mo |
| 3 — RAG/pgvector | 1.5–2 wks | $0 | ~$0 |
| 4 — Burnout/calibration ML | 3–4 wks | $0 | $0 |
| 5 — B2C productization | 3–4 wks | ~$0–200 (legal) | ~$15–30/mo + Stripe % |
| 6 — Go-to-market | 2–3 wks | $200–500 (optional ad test) | ~$0/mo |
| **Total** | **~4–5 months solo, sequential** | **~$200–700** | **~$50–80/mo at 100 users** |

Add baseline infra not broken out above (Supabase Pro $25/mo once you outgrow free tier, Vercel Pro ~$20/mo once you outgrow hobby tier, domain ~$12–15/yr) — realistic all-in recurring cost at ~100 paying users is roughly **$100–150/month**, against potential MRR at even a modest 100 paying Pro-tier users of **$800–1,000/month**. That gap is the number worth putting in front of a grant reviewer.

---

## What I'd want to know before locking this further
- Do you want to build phases 0–4 solo on your own timeline, or is there budget (grant, savings, co-founder) to parallelize — e.g., hire a designer for Phase 5/6 assets while you keep building the AI layer?
- Should I draft the actual Stripe product/price objects and webhook handler code next, or start with the model-router module from Phase 1 since everything downstream depends on it?
