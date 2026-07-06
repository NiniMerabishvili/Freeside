-- Enrich session_logs with completion activity details (run in Supabase SQL Editor)

ALTER TABLE public.session_logs
  ADD COLUMN IF NOT EXISTS xp_earned INTEGER,
  ADD COLUMN IF NOT EXISTS task_title TEXT,
  ADD COLUMN IF NOT EXISTS cognitive_load_score INTEGER;

-- Backfill session rows from linked tasks where possible
UPDATE public.session_logs AS sl
SET
  task_title = t.title,
  cognitive_load_score = t.cognitive_load_score,
  xp_earned = COALESCE(t.xp_earned, t.cognitive_load_score * 10)
FROM public.tasks AS t
WHERE sl.task_id = t.id
  AND sl.task_title IS NULL;
