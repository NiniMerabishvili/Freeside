-- Create user_integrations if missing (required for ClickUp / onboarding integrations)
CREATE TABLE IF NOT EXISTS public.user_integrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  integration_type TEXT NOT NULL,
  is_connected BOOLEAN DEFAULT FALSE,
  api_token TEXT,
  context_notes TEXT,
  workspace_name TEXT,
  external_team_id TEXT,
  account_label TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, integration_type)
);

ALTER TABLE public.user_integrations
  ADD COLUMN IF NOT EXISTS external_team_id TEXT,
  ADD COLUMN IF NOT EXISTS account_label TEXT;

ALTER TABLE public.user_integrations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own data" ON public.user_integrations;
CREATE POLICY "Users see own data" ON public.user_integrations
  FOR ALL USING (auth.uid() = user_id);
