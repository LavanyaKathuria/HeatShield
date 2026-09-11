import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)

if (!isSupabaseConfigured) {
  // Loud, not silent: auth-dependent screens should show a real
  // "not configured" state rather than pretending to work. See
  // README for the two-minute Supabase setup steps.
  // eslint-disable-next-line no-console
  console.warn(
    '[supabase] VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set. ' +
      'Auth, dependents, corporate accounts, alerts, and interventions will not work until they are.'
  )
}

// A placeholder client still gets created (pointing nowhere) so imports
// don't crash the whole app before configuration exists - callers must
// check isSupabaseConfigured before relying on it.
export const supabase = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key'
)
