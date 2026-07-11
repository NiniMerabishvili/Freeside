-- Encrypt stored OAuth/API tokens with pgcrypto.
--
-- RLS remains row-based on profiles and user_integrations. These new bytea columns
-- are covered by the existing "Users see own data" policies; no column-level RLS
-- policies exist in this schema.
--
-- Hosted Supabase does not allow project users to set arbitrary database-level
-- GUCs such as app.settings.encryption_key. Instead, backend service-role code
-- passes ENCRYPTION_KEY into these RPCs at runtime; the key is never hardcoded in
-- SQL or exposed to anon/authenticated clients.

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS google_refresh_token_enc bytea;

ALTER TABLE public.user_integrations
  ADD COLUMN IF NOT EXISTS api_token_enc bytea;

COMMENT ON COLUMN public.profiles.google_refresh_token IS
  'Deprecated plaintext legacy column. Use google_refresh_token_enc via service-role vault RPCs.';
COMMENT ON COLUMN public.user_integrations.api_token IS
  'Deprecated plaintext legacy column. Use api_token_enc via service-role vault RPCs.';
COMMENT ON COLUMN public.profiles.google_refresh_token_enc IS
  'pgcrypto-encrypted Google refresh token; decrypt only through service-role vault RPCs.';
COMMENT ON COLUMN public.user_integrations.api_token_enc IS
  'pgcrypto-encrypted integration API/OAuth token; decrypt only through service-role vault RPCs.';

CREATE OR REPLACE FUNCTION public._assert_vault_key(p_key text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF p_key IS NULL OR length(p_key) < 16 THEN
    RAISE EXCEPTION 'ENCRYPTION_KEY is not configured or is too short'
      USING ERRCODE = '22023';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public._assert_service_role()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF auth.role() <> 'service_role'
     AND current_user NOT IN ('postgres', 'supabase_admin', 'service_role') THEN
    RAISE EXCEPTION 'token vault access requires service_role'
      USING ERRCODE = '42501';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.backfill_encrypted_oauth_tokens(p_key text)
RETURNS TABLE(profile_tokens_encrypted integer, integration_tokens_encrypted integer)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  profile_count integer := 0;
  integration_count integer := 0;
BEGIN
  PERFORM public._assert_service_role();
  PERFORM public._assert_vault_key(p_key);

  UPDATE public.profiles
  SET google_refresh_token_enc = extensions.pgp_sym_encrypt(google_refresh_token, p_key)
  WHERE google_refresh_token IS NOT NULL
    AND google_refresh_token_enc IS NULL;
  GET DIAGNOSTICS profile_count = ROW_COUNT;

  UPDATE public.user_integrations
  SET api_token_enc = extensions.pgp_sym_encrypt(api_token, p_key)
  WHERE api_token IS NOT NULL
    AND api_token_enc IS NULL;
  GET DIAGNOSTICS integration_count = ROW_COUNT;

  RETURN QUERY SELECT profile_count, integration_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_google_refresh_token(
  p_user_id uuid,
  p_key text
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  token text;
BEGIN
  PERFORM public._assert_service_role();
  PERFORM public._assert_vault_key(p_key);

  SELECT CASE
    WHEN google_refresh_token_enc IS NOT NULL
      THEN extensions.pgp_sym_decrypt(google_refresh_token_enc, p_key)
    ELSE google_refresh_token
  END
  INTO token
  FROM public.profiles
  WHERE id = p_user_id;

  RETURN token;
END;
$$;

CREATE OR REPLACE FUNCTION public.set_google_refresh_token(
  p_user_id uuid,
  p_token text,
  p_key text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM public._assert_service_role();
  PERFORM public._assert_vault_key(p_key);

  UPDATE public.profiles
  SET
    google_refresh_token_enc = CASE
      WHEN p_token IS NULL THEN NULL
      ELSE extensions.pgp_sym_encrypt(p_token, p_key)
    END,
    google_refresh_token = NULL
  WHERE id = p_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_api_token(
  p_user_id uuid,
  p_key text,
  p_integration_type text DEFAULT 'clickup'
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  token text;
BEGIN
  PERFORM public._assert_service_role();
  PERFORM public._assert_vault_key(p_key);

  SELECT CASE
    WHEN api_token_enc IS NOT NULL
      THEN extensions.pgp_sym_decrypt(api_token_enc, p_key)
    ELSE api_token
  END
  INTO token
  FROM public.user_integrations
  WHERE user_id = p_user_id
    AND integration_type = p_integration_type
  LIMIT 1;

  RETURN token;
END;
$$;

CREATE OR REPLACE FUNCTION public.set_api_token(
  p_user_id uuid,
  p_token text,
  p_key text,
  p_integration_type text DEFAULT 'clickup'
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM public._assert_service_role();
  PERFORM public._assert_vault_key(p_key);

  INSERT INTO public.user_integrations (
    user_id,
    integration_type,
    is_connected,
    api_token_enc,
    api_token,
    updated_at
  )
  VALUES (
    p_user_id,
    p_integration_type,
    p_token IS NOT NULL,
    CASE
      WHEN p_token IS NULL THEN NULL
      ELSE extensions.pgp_sym_encrypt(p_token, p_key)
    END,
    NULL,
    NOW()
  )
  ON CONFLICT (user_id, integration_type)
  DO UPDATE SET
    api_token_enc = CASE
      WHEN p_token IS NULL THEN NULL
      ELSE extensions.pgp_sym_encrypt(p_token, p_key)
    END,
    api_token = NULL,
    is_connected = p_token IS NOT NULL,
    updated_at = NOW();
END;
$$;

REVOKE ALL ON FUNCTION public._assert_vault_key(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._assert_service_role() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.backfill_encrypted_oauth_tokens(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.get_google_refresh_token(uuid, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.set_google_refresh_token(uuid, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.get_api_token(uuid, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.set_api_token(uuid, text, text, text) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.backfill_encrypted_oauth_tokens(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.get_google_refresh_token(uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.set_google_refresh_token(uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.get_api_token(uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.set_api_token(uuid, text, text, text) TO service_role;
