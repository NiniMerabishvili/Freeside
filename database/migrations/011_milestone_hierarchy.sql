-- Milestone entity: parent container for related tasks (Goal → Milestone → Tasks)
CREATE TABLE IF NOT EXISTS public.milestones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  goal_id UUID REFERENCES public.goals(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  milestone_order INTEGER,
  scheduled_date DATE,
  cognitive_load_score INTEGER CHECK (cognitive_load_score BETWEEN 1 AND 10),
  estimated_minutes INTEGER DEFAULT 90,
  status TEXT DEFAULT 'pending',
  progress_percent INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP
);

ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS milestone_id UUID REFERENCES public.milestones(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS daily_assigned_date DATE,
  ADD COLUMN IF NOT EXISTS scheduled_block_start TIME,
  ADD COLUMN IF NOT EXISTS scheduled_block_end TIME;

CREATE INDEX IF NOT EXISTS milestones_user_goal_idx
  ON public.milestones (user_id, goal_id);

CREATE INDEX IF NOT EXISTS milestones_user_scheduled_idx
  ON public.milestones (user_id, scheduled_date)
  WHERE scheduled_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS tasks_milestone_id_idx
  ON public.tasks (milestone_id)
  WHERE milestone_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS tasks_daily_assigned_idx
  ON public.tasks (user_id, daily_assigned_date)
  WHERE daily_assigned_date IS NOT NULL;

ALTER TABLE public.milestones ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own milestones" ON public.milestones
  FOR ALL USING (auth.uid() = user_id);
