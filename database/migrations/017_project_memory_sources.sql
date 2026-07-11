-- Project Memory: user-owned chunks of messy project context for grounded planning.
-- Stores pasted briefs, client notes, meeting summaries, and brain-dump context
-- as retrievable pgvector rows. Backend service-role calls pass p_user_id
-- explicitly, so matching never relies on RLS alone.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.project_memory_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'project_note',
  content TEXT NOT NULL,
  chunk_index INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(768),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS project_memory_sources_user_created_idx
  ON public.project_memory_sources (user_id, created_at DESC);

ALTER TABLE public.project_memory_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own project memory" ON public.project_memory_sources
  FOR ALL USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.match_project_memory(
  p_user_id uuid,
  p_embedding vector(768),
  p_match_count integer DEFAULT 6
)
RETURNS TABLE (
  memory_id uuid,
  title text,
  source_type text,
  content text,
  chunk_index integer,
  similarity double precision,
  created_at timestamp
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    pms.id AS memory_id,
    pms.title,
    pms.source_type,
    pms.content,
    pms.chunk_index,
    1 - (pms.embedding <=> p_embedding) AS similarity,
    pms.created_at
  FROM public.project_memory_sources pms
  WHERE pms.user_id = p_user_id
    AND pms.embedding IS NOT NULL
  ORDER BY similarity DESC, pms.created_at DESC
  LIMIT GREATEST(1, LEAST(COALESCE(p_match_count, 6), 20));
$$;
