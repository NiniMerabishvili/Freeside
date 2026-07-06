-- Subtask ordering for energy-aware splits
ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS step_order INTEGER;

CREATE INDEX IF NOT EXISTS tasks_parent_task_id_idx
  ON public.tasks (parent_task_id)
  WHERE parent_task_id IS NOT NULL;
