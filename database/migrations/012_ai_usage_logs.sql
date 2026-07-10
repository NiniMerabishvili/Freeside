-- Phase 1: per-call AI cost/latency logging (data source for the cost dashboard)
CREATE TABLE IF NOT EXISTS public.ai_usage_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  task_type TEXT NOT NULL,          -- energy_inference | goal_decompose | copilot_chat | ...
  provider TEXT NOT NULL,           -- gemini | anthropic
  model TEXT NOT NULL,
  tokens_in INTEGER,
  tokens_out INTEGER,
  latency_ms INTEGER,
  cache_hit BOOLEAN DEFAULT FALSE,
  ok BOOLEAN DEFAULT TRUE,
  error TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_user ON public.ai_usage_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_task ON public.ai_usage_logs (task_type, created_at DESC);
