-- CLCS routing audit trail (reroute events when energy changes)
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS public.routing_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  task_id UUID REFERENCES public.tasks(id) ON DELETE SET NULL,
  task_title TEXT,
  cognitive_load_score INTEGER,
  energy_score INTEGER,
  energy_level TEXT,
  effective_capacity INTEGER,
  delta INTEGER,
  was_rerouted BOOLEAN NOT NULL DEFAULT FALSE,
  unlock_score INTEGER,
  routed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS routing_logs_user_routed_at_idx
  ON public.routing_logs (user_id, routed_at DESC);

ALTER TABLE public.routing_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own routing logs" ON public.routing_logs;
CREATE POLICY "Users see own routing logs"
  ON public.routing_logs FOR ALL
  USING (auth.uid() = user_id);

NOTIFY pgrst, 'reload schema';
