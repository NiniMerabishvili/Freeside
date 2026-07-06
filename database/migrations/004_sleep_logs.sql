-- Sleep pulse logs for SQDS (PSQI proxy) — run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS public.sleep_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  hours_slept NUMERIC(4, 1) NOT NULL CHECK (hours_slept >= 0 AND hours_slept <= 24),
  rested_score INTEGER NOT NULL CHECK (rested_score BETWEEN 1 AND 5),
  logged_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sleep_logs_user_logged_at_idx
  ON public.sleep_logs (user_id, logged_at DESC);

ALTER TABLE public.sleep_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own sleep logs" ON public.sleep_logs;
CREATE POLICY "Users see own sleep logs"
  ON public.sleep_logs FOR ALL
  USING (auth.uid() = user_id);

NOTIFY pgrst, 'reload schema';
