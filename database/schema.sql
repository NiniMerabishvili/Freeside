-- ============================================================
-- FREESIDE DATABASE SCHEMA
-- Run this in Supabase Dashboard → SQL Editor
-- ============================================================

-- USERS PROFILE (extends Supabase's built-in auth.users)
CREATE TABLE public.profiles (
  id UUID REFERENCES auth.users(id) PRIMARY KEY,
  name TEXT,
  role TEXT,                          -- 'student', 'professional', 'entrepreneur'
  productive_day_description TEXT,    -- "What does a productive day look like?"
  peak_focus_time TEXT,               -- 'morning', 'afternoon', 'evening'
  daily_work_hours INTEGER,
  work_style TEXT,                    -- 'long_blocks', 'short_sprints'
  google_calendar_connected BOOLEAN DEFAULT FALSE,
  google_refresh_token TEXT,          -- stored encrypted
  xp_total INTEGER DEFAULT 0,
  onboarding_completed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- GOALS (user's 1-3 big objectives)
CREATE TABLE public.goals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id),
  title TEXT NOT NULL,                -- "Launch my side project"
  category TEXT,                      -- 'work', 'personal', 'health', 'learning'
  timeframe TEXT,                     -- '1 month', '3 months', '6 months'
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- TASKS
CREATE TABLE public.tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id),
  goal_id UUID REFERENCES public.goals(id),   -- optional link to a goal
  title TEXT NOT NULL,
  description TEXT,
  cognitive_load_score INTEGER CHECK (cognitive_load_score BETWEEN 1 AND 10),
  status TEXT DEFAULT 'pending',      -- 'pending', 'active', 'completed', 'rerouted'
  source TEXT DEFAULT 'manual',       -- 'manual', 'ai_generated' (micro-steps)
  parent_task_id UUID REFERENCES public.tasks(id),  -- for micro-steps
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP
);

-- ENERGY LOGS
CREATE TABLE public.energy_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id),
  ai_suggested_score INTEGER,         -- what the AI guessed (1-10)
  ai_suggested_level TEXT,            -- 'high', 'balanced', 'low'
  ai_reasoning TEXT,                  -- why the AI suggested this
  confirmed_score INTEGER,            -- what user confirmed (1-10)
  confirmed_level TEXT,               -- final level used by routing
  calendar_event_count INTEGER,       -- how many events were on calendar
  calendar_context TEXT,              -- summary of calendar fed to AI
  logged_at TIMESTAMP DEFAULT NOW()
);

-- SESSION LOGS (thesis data — every task interaction)
CREATE TABLE public.session_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id),
  task_id UUID REFERENCES public.tasks(id),
  energy_level TEXT,
  energy_score INTEGER,
  was_rerouted BOOLEAN DEFAULT FALSE,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  ai_copilot_used BOOLEAN DEFAULT FALSE
);

-- COPILOT LOGS (for analytics)
CREATE TABLE public.copilot_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id),
  message_type TEXT,                  -- 'micro_step', 'proactive', 'user_initiated'
  task_id UUID REFERENCES public.tasks(id),
  energy_level_at_time TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- USER INTEGRATIONS (ClickUp, Asana, Obsidian, Notes, AI Agents)
CREATE TABLE public.user_integrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  integration_type TEXT NOT NULL,  -- 'clickup', 'asana', 'obsidian', 'notes', 'ai_agents'
  is_connected BOOLEAN DEFAULT FALSE,
  api_token TEXT,                  -- for ClickUp, Asana (store encrypted in production)
  context_notes TEXT,              -- for Obsidian, Notes, AI Agents (free-text context injected into AI)
  workspace_name TEXT,             -- optional workspace/space label
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, integration_type)
);

-- ============================================================
-- ROW LEVEL SECURITY: users can only see their own data
-- ============================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.energy_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.session_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.copilot_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own data" ON public.profiles
  FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users see own data" ON public.goals
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own data" ON public.tasks
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own data" ON public.energy_logs
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own data" ON public.session_logs
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own data" ON public.copilot_logs
  FOR ALL USING (auth.uid() = user_id);

ALTER TABLE public.user_integrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own data" ON public.user_integrations
  FOR ALL USING (auth.uid() = user_id);

-- ============================================================
-- AUTO-CREATE PROFILE ON SIGNUP
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id)
  VALUES (NEW.id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
