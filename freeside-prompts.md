# Freeside — Sonnet 4.6 Build Prompts (Security → RAG → ML/Burnout)

Grounded in the actual repo state (not just the roadmap doc):
- `profiles.google_refresh_token` and `user_integrations.api_token` are plain `TEXT` (schema.sql), read/written as raw strings in `integrations.py`.
- `day_context.py` / `calendar.py` swallow errors via bare `except Exception: return None` / `clickup_connected = False`.
- `model_router.py` routes every tier to `gemini-2.5-flash`; `_run_anthropic()` is a stub (`NotImplementedError`).
- No pgvector migration, no embeddings code, nothing under `analysis/services`.
- No ML/burnout code yet, but `energy_logs` already has `ai_suggested_score` + `confirmed_score`, and `sleep_logs` / `routing_logs` / `session_logs` are populated.
- No CI, no pytest suite — just `scripts/test_freeside_copilot.py`.
- RLS is solid everywhere already — every prompt below says "preserve/extend this pattern," not "add RLS from scratch."

Order: **Security → RAG → ML personalization/burnout.** Security first because RAG and ML are about to store and embed more sensitive behavioral data than exists today — cheaper to close the gaps before widening the attack surface. RAG second because the ML feature pipeline and the embedding pipeline share storage/retrieval patterns worth establishing once.

Hand each prompt to Sonnet 4.6 as its own task/session. Each is self-contained (states the repo context Sonnet needs) so you don't have to re-explain the codebase every time.

---

## Prompt 1 — Encrypt OAuth tokens at rest

```
You're working in the Freeside repo (FastAPI backend + Supabase/Postgres, RLS already
enabled on all user tables). Two columns currently store secrets as plain TEXT and are
read/written as raw strings:

- profiles.google_refresh_token
- user_integrations.api_token

Task: migrate both to pgcrypto-encrypted storage without breaking existing integrations.

1. Write a new file in database/migrations/ that:
   - enables pgcrypto if not already enabled
   - adds new bytea columns (e.g. google_refresh_token_enc, api_token_enc)
   - backfills them from the existing plaintext columns using pgp_sym_encrypt with a
     key pulled from a Postgres setting (not hardcoded in SQL), e.g.
     current_setting('app.settings.encryption_key')
   - leaves the old plaintext columns in place but adds a comment marking them
     deprecated (do not drop them in this migration — that's a follow-up once the
     app code is confirmed working end to end)
   - preserves existing RLS policies; add equivalent policies for the new columns if
     RLS is column-aware anywhere, otherwise confirm row-level policies already cover it

2. Add a service-role-only decrypt path:
   - In backend/services/calendar.py and backend/services/clickup.py (or a new shared
     backend/services/token_vault.py if that's cleaner), add functions
     get_google_refresh_token(user_id) and get_api_token(user_id) that decrypt via
     pgp_sym_decrypt using the service-role Postgres connection only — never expose
     decryption to anon-key/client-side paths.
   - Add corresponding set_google_refresh_token / set_api_token functions that encrypt
     on write.

3. Update every call site in routes/integrations.py, calendar.py, clickup.py, and
   day_context.py that currently reads/writes the plaintext columns directly — route
   them through the new vault functions instead.

4. Add a config value ENCRYPTION_KEY to backend/.env.example and document it in the
   README security section.

5. Write a pytest (new tests/ dir if none exists near this code) that:
   - inserts a fake token, confirms the raw plaintext column is unreadable garbage
     without the key, and confirms the vault function returns the original value.

Do not change the external API contracts of routes/integrations.py — this should be
invisible to the frontend. Show me the migration file and the diffs for each changed
file before considering this done.
```

---

## Prompt 2 — Typed errors instead of silent failure

```
In the Freeside FastAPI backend, day_context.py, calendar.py, and clickup.py currently
swallow failures with patterns like:

    except Exception:
        return None
    clickup_connected = False

This hides real failures (expired OAuth, API rate limits, network errors) from both
logs and the Co-Pilot context that gets built from these functions.

There's already a partial pattern started in backend/services/integration_errors.py
(SyncWarning / SyncErrorCode) — extend that rather than inventing a new error taxonomy.

Task:
1. Read integration_errors.py fully and identify the existing SyncWarning/SyncErrorCode
   shape.
2. Add typed exceptions that fit that pattern: CalendarSyncError, ClickUpAuthError,
   ClickUpSyncError — each carrying an error code from (or added to) SyncErrorCode,
   a user-facing message, and the underlying exception for logging.
3. Replace every bare `except Exception: return None` / silent boolean flip in
   day_context.py, calendar.py, and clickup.py with:
   - catching the specific expected exceptions (OAuth token expiry, HTTP errors,
     timeouts) and raising the typed error
   - logging the underlying exception with context (user_id, integration name)
   - only at the boundary where day_context.py assembles the Co-Pilot context should
     these be caught and converted into a SyncWarning surfaced to the user
     ("Calendar sync failed, using last known state") — not swallowed silently
4. Confirm routes that call these services propagate a sensible HTTP error (401/424/503
   as appropriate) instead of returning empty/default data with a 200.
5. Add a short section to integration_errors.py's docstring or a README describing the
   error taxonomy so future integrations follow the same pattern.

Show me the before/after for each of the three files plus the new/extended exception
classes.
```

---

## Prompt 3 — Validate model_router outputs + bounded retries

```
Freeside's backend/services/model_router.py dispatches AI calls via generate_json and
generate_json_array. Every TASK_MODELS tier currently points at gemini-2.5-flash, and
_run_anthropic() is a stub that raises NotImplementedError — Claude Sonnet isn't wired
in yet despite the README describing a "Co-Pilot tier."

Task (this prompt is about validation/reliability, not wiring in Sonnet yet):

1. Add Pydantic models describing the expected shape of every distinct JSON contract
   currently produced by generate_json / generate_json_array call sites (task
   suggestions, energy inference, brain-dump parsing, etc. — grep all call sites first
   and enumerate them before writing schemas).
2. Wrap every call site with:
   - schema validation against the matching Pydantic model
   - one bounded retry (single retry, not a loop) with a stricter re-prompt
     ("Return ONLY valid JSON matching this shape: ...") if validation fails
   - a typed ModelResponseError (fits the integration_errors.py pattern if that's
     shared, otherwise a local equivalent) raised if the retry also fails, instead of
     letting a malformed response silently propagate into route handlers
3. Do NOT implement _run_anthropic() in this pass — that's separate work. Just make
   sure the stub raising NotImplementedError is caught cleanly upstream so it doesn't
   crash a request path if some tier config accidentally points at "anthropic" today.
4. Add a small pytest suite for model_router.py covering: valid response passes,
   malformed response triggers retry then succeeds, malformed response fails twice and
   raises ModelResponseError.

List every call site you found before making changes, so I can confirm you covered all
of them.
```

---

## Prompt 4 — CI + real pytest suite

```
Freeside currently has no .github/workflows and no pytest suite — only a manual script
at backend/scripts/test_freeside_copilot.py. Set up baseline CI.

Task:
1. Add .github/workflows/ci.yml that on push/PR runs:
   - backend: ruff check, pytest (create backend/tests/ if it doesn't exist)
   - frontend: eslint, next build
   - fail the workflow on any of these failing
2. Write a real pytest suite (not a manual script) covering, at minimum:
   - backend/services/xp.py — XP calculation given cognitive load + completion
   - backend/services/clcs (the routing module) — the core routing edge cases:
     task load above effective capacity gets deferred, goal-aligned tasks get priority
     boost, peak-hour boost applied correctly, low-energy day defers correctly
   - model_router.py — reuse/extend the tests from Prompt 3 if that's already merged
3. Use pytest fixtures for a fake Supabase client / in-memory data rather than hitting
   a real database in CI.
4. Keep scripts/test_freeside_copilot.py as-is for manual/interactive testing — this is
   additive, not a replacement.

Show me the workflow file and a summary of test coverage added per module.
```

---

## Prompt 5 — Rate-limit Co-Pilot tool-calling turns

```
backend/routes/copilot.py handles Co-Pilot chat turns that can trigger tool calls
(task creation, calendar write-back once that ships). This needs rate limiting before
Phase 2's calendar write-back lands, to bound both cost (model calls) and blast radius
of any single user's tool-calling loop.

Task:
1. Add per-user rate limiting on routes/copilot.py — a sliding window (e.g. N turns per
   minute, M tool-calls per hour) backed by Supabase or an in-memory store if Redis
   isn't already in the stack (check requirements.txt / infra first and tell me which
   you're using and why).
2. Return a clear 429 with a retry-after hint when the limit is hit, and make sure the
   frontend Co-Pilot rail (check frontend for how it consumes this route) can surface
   that as a user-facing message rather than a generic error.
3. Make the limits configurable per pricing tier (Free/Pro/Premium) since the README
   describes tiered access — even if tier enforcement elsewhere isn't built yet, this
   rate limiter should accept a tier parameter so it's ready.
4. Add a test confirming the limit triggers correctly and resets after the window.

Tell me what rate-limit backend you chose and why before implementing.
```

---

## Prompt 6 — pgvector migration + embed-on-write

```
Freeside has no pgvector migration, no embeddings, nothing under analysis/services yet.
This is the first RAG prompt — infra only, no retrieval logic yet.

Context: schema.sql has an established RLS pattern on every user table — match it
exactly for new tables.

Task:
1. Write a migration in database/migrations/ that:
   - enables the pgvector extension
   - adds an embedding vector column to tasks and goals (confirm the right dimension
     for the embedding model you'll use — text-embedding-001 — and document it in the
     migration comment)
   - creates a new copilot_message_embeddings table (message_id, user_id, embedding,
     created_at, source reference back to the originating Co-Pilot turn)
   - adds RLS policies on copilot_message_embeddings matching the exact pattern used
     for other user-owned tables in schema.sql (read the file first, copy the pattern,
     don't invent a new one)
   - do NOT add ivfflat/hnsw indexing yet — defer until row counts justify it; add a
     comment in the migration noting this is intentional
2. Add an embedding helper in a new backend/services/embeddings.py:
   - a single embed_text(text: str) -> list[float] function wrapping the Gemini
     text-embedding-001 call, with basic retry/error handling consistent with how
     model_router.py handles Gemini failures
3. Hook embed-on-write into three places (find the right function in each file first):
   - task completion handler
   - goal creation handler
   - the Co-Pilot turn handler in routes/copilot.py / services/copilot.py
   Each should call embed_text and upsert into the relevant embedding column/table
   asynchronously if possible, so it doesn't block the user-facing response.
4. Add a pytest that mocks the embedding call and confirms the upsert happens on each
   of the three triggers.

Show me the migration file, the new embeddings.py, and the diff at each of the three
hook points.
```

---

## Prompt 7 — Semantic retrieval in Co-Pilot context

```
This builds on the pgvector migration (Prompt 6) — confirm that's merged before
starting. backend/services/context_builder.py already assembles Co-Pilot context via
build_context_for_user with profile/calendar/clickup/energy sections.

Task:
1. Add a 5th retrieval step to build_context_for_user: given the current user turn,
   embed it (reuse embed_text from Prompt 6), run a cosine-similarity query against
   copilot_message_embeddings and tasks/goals embeddings scoped to that user_id
   (RLS + explicit user_id filter — don't rely on RLS alone for a service-role query),
   and pull the top-k (start with k=5) most relevant prior messages/tasks/goals.
2. Add this as a "relevant history" section in the <freeside_context> XML the Co-Pilot
   prompt already builds — match the existing XML structure/tagging conventions in
   context_builder.py exactly.
3. Add semantic goal-matching in the brain-dump parser (backend/services/
   goal_planning.py): when a new brain-dump item comes in, embed it and check
   similarity against existing goals before creating a new one; if similarity is above
   a threshold (start at 0.85, make it configurable), suggest linking to the existing
   goal instead of creating a duplicate.
4. Add tests: one confirming relevant history retrieval returns results scoped only to
   the requesting user (critical — verify no cross-user leakage even with a
   service-role client), one confirming the brain-dump similarity threshold correctly
   suggests linking vs creating new.

The cross-user isolation test in step 4 is the most important one — show me that test
explicitly and don't mark this done without it passing.
```

---

## Prompt 8 — Burnout feature pipeline

```
No ML/burnout code exists yet. The raw material does: energy_logs, sleep_logs,
routing_logs, and session_logs all exist and are populated — this is pure ETL, no
schema changes needed to start.

Task:
1. Create backend/services/ml_features.py with a function
   build_user_feature_window(user_id, window_days=14) that:
   - pulls the last N days from energy_logs, sleep_logs, routing_logs, session_logs
     for that user
   - computes a rolling feature set: average confirmed energy, energy trend (slope),
     reroute rate (from routing_logs), task abandonment rate (from session_logs),
     sleep consistency/duration trend (from sleep_logs)
   - returns a flat feature dict/row ready for a model input
2. Add a pytest with synthetic log data covering: a user with fully populated 14 days,
   a user with sparse/missing days (confirm sensible handling — don't silently zero-fill
   in a way that fakes a stable trend), and a brand new user with <3 days of data
   (confirm this returns a clear "insufficient data" signal rather than a garbage
   feature row).
3. Do not build the model itself in this prompt — this is the feature pipeline only.
   Stop here and show me sample output for a real user_id from a dev/staging Supabase
   instance if one is available, or synthetic data otherwise.
```

---

## Prompt 9 — Baseline burnout model + calibration

```
Builds on Prompt 8's feature pipeline. Task: train and serve a baseline burnout model,
plus per-user energy calibration.

Part A — baseline model:
1. Define a composite label for training: combine reroute rate, energy trend, and
   task-abandonment rate from build_user_feature_window into a single burnout_risk
   label (document the exact formula/thresholds you choose and why).
2. Train a scikit-learn logistic regression (start simple — not GBM yet) on
   historical feature windows, offline, in a script under analysis/ or a new
   backend/ml/train_burnout.py.
3. Serialize the trained model (joblib) and write a loader that a nightly job can call.
4. Set up the nightly job as a Supabase Edge Function (or note clearly if a different
   scheduler is already in use in this repo — check infra first) that runs
   build_user_feature_window + model inference for every active user and writes the
   result to a new burnout_scores table (user_id, score, computed_at) with RLS
   matching the existing pattern.

Part B — per-user energy calibration:
1. energy_logs.ai_suggested_score and confirmed_score are already populated but unused
   for this. Add a small function (aim for ~30 lines) that computes a running per-user
   bias term: average(confirmed_score - ai_suggested_score) over a rolling window.
2. Feed that bias term back into wherever AI energy inference currently happens
   (find the call site — likely in day_context.py or a dedicated energy service) so
   the next AI-suggested score is adjusted by the user's historical bias before being
   shown.
3. Add a test confirming the bias term converges toward the right correction given
   synthetic suggested/confirmed pairs with a consistent offset.

Show me the label formula, the trained model's basic validation metrics (even on
synthetic/small data), and the calibration function.
```

---

## Prompt 10 — Surface burnout risk to the Co-Pilot

```
Builds on Prompt 9. burnout_scores now exists. Task: make the Co-Pilot aware of it.

1. Add a burnout_risk block to the <freeside_context> XML built in
   context_builder.py's build_context_for_user — pull the latest row from
   burnout_scores for the user, include the score and a plain-language risk band
   (low/moderate/high) — match the existing XML tagging style in that file exactly.
2. Update the Co-Pilot system prompt (backend/prompts/) to describe how to use this
   signal: proactively nudge (suggest lighter day, defer non-critical tasks) when risk
   is high, but never block the user or refuse requests based on it — it's advisory,
   the user stays in control, consistent with the "manual override always available"
   principle already in the README.
3. Add a test confirming the burnout_risk block only appears when a score exists for
   that user (don't fabricate a score for users with insufficient data — should show
   "insufficient data" or omit the block, matching what build_user_feature_window
   returns from Prompt 8).

Show me the updated context XML output for a sample user and the prompt diff.
```

---

## Notes on sequencing

- Prompts 1–5 (security) can mostly run in parallel once Prompt 1 (encryption) is
  merged, since 2–5 don't depend on each other.
- Prompt 6 must land before 7. Prompt 8 must land before 9, and 9 before 10.
- Security and RAG can overlap in time — they don't block each other. ML/burnout
  (8–10) is the one track that benefits from RAG's embedding infra existing first,
  but only loosely (it doesn't consume embeddings directly, just benefits from the
  same review/testing conventions being established).
- Give Sonnet 4.6 one prompt per session/task, not the whole file at once — each is
  scoped to be reviewable as a single PR.
