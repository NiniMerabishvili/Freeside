import { createBrowserClient } from '@supabase/ssr'
import { createFetchWithTimeout } from './fetch-with-timeout'

export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  { global: { fetch: createFetchWithTimeout(8000) } }
)
