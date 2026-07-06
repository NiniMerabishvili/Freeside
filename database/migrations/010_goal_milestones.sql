-- Goal-level planning: milestones scheduled across a multi-day horizon
ALTER TABLE public.goals
  ADD COLUMN IF NOT EXISTS progress_percent INTEGER DEFAULT 0;

ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS scheduled_date DATE,
  ADD COLUMN IF NOT EXISTS milestone_order INTEGER,
  ADD COLUMN IF NOT EXISTS is_milestone BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS estimated_minutes INTEGER;

CREATE INDEX IF NOT EXISTS tasks_user_scheduled_idx
  ON public.tasks (user_id, scheduled_date)
  WHERE scheduled_date IS NOT NULL;
