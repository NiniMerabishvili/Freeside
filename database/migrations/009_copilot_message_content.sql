-- Store Co-Pilot conversation text for day planning and goal-aligned task suggestions
ALTER TABLE public.copilot_logs
  ADD COLUMN IF NOT EXISTS user_message TEXT,
  ADD COLUMN IF NOT EXISTS assistant_reply TEXT;
