-- ClickUp OAuth: store selected workspace team id and connected account label
ALTER TABLE public.user_integrations
  ADD COLUMN IF NOT EXISTS external_team_id TEXT,
  ADD COLUMN IF NOT EXISTS account_label TEXT;
