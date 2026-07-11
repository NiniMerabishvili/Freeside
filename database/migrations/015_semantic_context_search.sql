-- Semantic retrieval helper for Co-Pilot context.
-- Uses explicit p_user_id filters because backend calls use a service-role key;
-- RLS is still enabled, but service-role queries must not rely on RLS alone.

CREATE OR REPLACE FUNCTION public.match_copilot_context(
  p_user_id uuid,
  p_embedding vector(768),
  p_match_count integer DEFAULT 5
)
RETURNS TABLE (
  source_type text,
  source_id uuid,
  title text,
  content text,
  similarity double precision,
  created_at timestamp
)
LANGUAGE sql
STABLE
AS $$
  SELECT *
  FROM (
    SELECT
      'copilot_message'::text AS source_type,
      cme.message_id AS source_id,
      cl.message_type AS title,
      concat_ws(E'\n', cl.user_message, cl.assistant_reply) AS content,
      1 - (cme.embedding <=> p_embedding) AS similarity,
      cme.created_at
    FROM public.copilot_message_embeddings cme
    JOIN public.copilot_logs cl ON cl.id = cme.message_id
    WHERE cme.user_id = p_user_id
      AND cl.user_id = p_user_id

    UNION ALL

    SELECT
      'task'::text AS source_type,
      t.id AS source_id,
      t.title,
      concat_ws(E'\n', t.title, t.description, t.status, t.source) AS content,
      1 - (t.embedding <=> p_embedding) AS similarity,
      t.created_at
    FROM public.tasks t
    WHERE t.user_id = p_user_id
      AND t.embedding IS NOT NULL

    UNION ALL

    SELECT
      'goal'::text AS source_type,
      g.id AS source_id,
      g.title,
      concat_ws(E'\n', g.title, g.category, g.timeframe) AS content,
      1 - (g.embedding <=> p_embedding) AS similarity,
      g.created_at
    FROM public.goals g
    WHERE g.user_id = p_user_id
      AND g.embedding IS NOT NULL
  ) matches
  ORDER BY similarity DESC, created_at DESC
  LIMIT GREATEST(1, LEAST(COALESCE(p_match_count, 5), 20));
$$;

CREATE OR REPLACE FUNCTION public.match_user_goals(
  p_user_id uuid,
  p_embedding vector(768),
  p_match_count integer DEFAULT 3
)
RETURNS TABLE (
  goal_id uuid,
  title text,
  similarity double precision
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    g.id AS goal_id,
    g.title,
    1 - (g.embedding <=> p_embedding) AS similarity
  FROM public.goals g
  WHERE g.user_id = p_user_id
    AND g.is_active = true
    AND g.embedding IS NOT NULL
  ORDER BY similarity DESC, g.created_at DESC
  LIMIT GREATEST(1, LEAST(COALESCE(p_match_count, 3), 10));
$$;
