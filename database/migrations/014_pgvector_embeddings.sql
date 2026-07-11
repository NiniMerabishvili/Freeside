-- RAG infrastructure only: pgvector columns and Co-Pilot turn embeddings.
-- Freeside embeds text with Gemini's text-only embedding model
-- (gemini-embedding-001 / text-embedding-001 generation) using
-- output_dimensionality = 768. Google documents the model as 3072-dimensional
-- by default, with 768 as a supported storage-efficient MRL dimension.
-- Retrieval indexes are intentionally deferred: no ivfflat/hnsw until row
-- counts and query patterns justify index build cost and tuning.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS embedding vector(768);

ALTER TABLE public.goals
  ADD COLUMN IF NOT EXISTS embedding vector(768);

CREATE TABLE IF NOT EXISTS public.copilot_message_embeddings (
  message_id UUID PRIMARY KEY REFERENCES public.copilot_logs(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  embedding vector(768) NOT NULL,
  source TEXT NOT NULL DEFAULT 'copilot_turn',
  created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE public.copilot_message_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own data" ON public.copilot_message_embeddings
  FOR ALL USING (auth.uid() = user_id);
