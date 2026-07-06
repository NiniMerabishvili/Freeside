-- ============================================================
-- FREESIDE — XP SYSTEM MIGRATION
-- Paste into Supabase Dashboard → SQL Editor → Run
-- Formula: XP = GREATEST(cognitive_load_score, 1) × 10
-- ============================================================


-- ── 1. Columns ──────────────────────────────────────────────────────────────

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS xp_total INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS avatar_url TEXT;

ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS xp_earned INTEGER;

ALTER TABLE public.session_logs
  ADD COLUMN IF NOT EXISTS xp_earned INTEGER,
  ADD COLUMN IF NOT EXISTS task_title TEXT,
  ADD COLUMN IF NOT EXISTS cognitive_load_score INTEGER;


-- ── 2. XP helper functions ────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.compute_task_xp(load_score INTEGER)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN load_score IS NULL THEN 0
    ELSE GREATEST(load_score, 1) * 10
  END;
$$;

CREATE OR REPLACE FUNCTION public.sync_profile_xp(p_user_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  new_total INTEGER;
BEGIN
  SELECT COALESCE(SUM(public.compute_task_xp(cognitive_load_score)), 0)
  INTO new_total
  FROM public.tasks
  WHERE user_id = p_user_id
    AND status = 'completed';

  UPDATE public.profiles
  SET xp_total = new_total
  WHERE id = p_user_id;

  RETURN new_total;
END;
$$;


-- ── 3. Backfill existing completed tasks ────────────────────────────────────

UPDATE public.tasks
SET xp_earned = public.compute_task_xp(cognitive_load_score)
WHERE status = 'completed'
  AND cognitive_load_score IS NOT NULL
  AND (xp_earned IS NULL OR xp_earned <> public.compute_task_xp(cognitive_load_score));

UPDATE public.session_logs AS sl
SET
  task_title = t.title,
  cognitive_load_score = t.cognitive_load_score,
  xp_earned = COALESCE(t.xp_earned, public.compute_task_xp(t.cognitive_load_score))
FROM public.tasks AS t
WHERE sl.task_id = t.id
  AND (
    sl.task_title IS NULL
    OR sl.cognitive_load_score IS NULL
    OR sl.xp_earned IS NULL
  );

-- Sync every user's profile XP from completed tasks
DO $$
DECLARE
  uid UUID;
BEGIN
  FOR uid IN SELECT id FROM public.profiles LOOP
    PERFORM public.sync_profile_xp(uid);
  END LOOP;
END;
$$;


-- ── 4. Auto-set XP when a task is marked completed ──────────────────────────

CREATE OR REPLACE FUNCTION public.handle_task_completion_xp()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.status = 'completed'
     AND (OLD.status IS DISTINCT FROM 'completed')
     AND NEW.cognitive_load_score IS NOT NULL THEN

    NEW.xp_earned := public.compute_task_xp(NEW.cognitive_load_score);

    IF NEW.completed_at IS NULL THEN
      NEW.completed_at := NOW();
    END IF;

    PERFORM public.sync_profile_xp(NEW.user_id);
  END IF;

  IF OLD.status = 'completed'
     AND NEW.status IS DISTINCT FROM 'completed' THEN
    NEW.xp_earned := NULL;
    PERFORM public.sync_profile_xp(NEW.user_id);
  END IF;

  IF TG_OP = 'DELETE' AND OLD.status = 'completed' THEN
    PERFORM public.sync_profile_xp(OLD.user_id);
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_task_completion_xp ON public.tasks;

CREATE TRIGGER trg_task_completion_xp
BEFORE INSERT OR UPDATE OR DELETE ON public.tasks
FOR EACH ROW
EXECUTE FUNCTION public.handle_task_completion_xp();


-- ── 5. Enrich session_logs on insert (activity audit trail) ─────────────────

CREATE OR REPLACE FUNCTION public.handle_session_log_activity()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  t RECORD;
BEGIN
  IF NEW.task_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT title, cognitive_load_score, xp_earned
  INTO t
  FROM public.tasks
  WHERE id = NEW.task_id;

  IF FOUND THEN
    NEW.task_title := COALESCE(NEW.task_title, t.title);
    NEW.cognitive_load_score := COALESCE(NEW.cognitive_load_score, t.cognitive_load_score);
    NEW.xp_earned := COALESCE(
      NEW.xp_earned,
      t.xp_earned,
      public.compute_task_xp(t.cognitive_load_score)
    );
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_session_log_activity ON public.session_logs;

CREATE TRIGGER trg_session_log_activity
BEFORE INSERT OR UPDATE ON public.session_logs
FOR EACH ROW
EXECUTE FUNCTION public.handle_session_log_activity();


-- ── 6. Reload PostgREST schema cache (fixes "column not found" errors) ────────

NOTIFY pgrst, 'reload schema';


-- ── 7. Verify (optional — check output in SQL Editor) ─────────────────────────

SELECT
  p.id,
  p.name,
  p.xp_total,
  COUNT(t.id) FILTER (WHERE t.status = 'completed') AS completed_tasks
FROM public.profiles p
LEFT JOIN public.tasks t ON t.user_id = p.id
GROUP BY p.id, p.name, p.xp_total
ORDER BY p.xp_total DESC;
