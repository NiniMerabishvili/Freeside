-- Nightly burnout model outputs.
-- RLS matches the user-owned table pattern in schema.sql.

CREATE TABLE IF NOT EXISTS public.burnout_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  score NUMERIC(6, 5) NOT NULL CHECK (score >= 0 AND score <= 1),
  label BOOLEAN NOT NULL DEFAULT FALSE,
  model_version TEXT NOT NULL,
  feature_window_days INTEGER NOT NULL DEFAULT 14,
  features JSONB NOT NULL DEFAULT '{}'::jsonb,
  computed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS burnout_scores_user_computed_idx
  ON public.burnout_scores (user_id, computed_at DESC);

ALTER TABLE public.burnout_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own data" ON public.burnout_scores
  FOR ALL USING (auth.uid() = user_id);
