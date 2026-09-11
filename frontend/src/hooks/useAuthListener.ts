import { useEffect, useRef } from 'react'
import { supabase, isSupabaseConfigured } from '@/lib/supabase'
import { useAuthStore } from '@/store/useAuthStore'

// Subscribes to Supabase auth state once at the app root and hydrates
// the profile/corporate-account row for whichever account kind signed
// in. If Supabase isn't configured yet, this just marks auth as
// "not loading" with no session - screens should show a real
// not-configured state, not a fake logged-out one that looks the same
// as "no account exists."
export function useAuthListener() {
  const setSession = useAuthStore((s) => s.setSession)
  const setProfile = useAuthStore((s) => s.setProfile)
  const setCorporateAccount = useAuthStore((s) => s.setCorporateAccount)
  const setAccountKind = useAuthStore((s) => s.setAccountKind)
  const setAuthLoading = useAuthStore((s) => s.setAuthLoading)
  const setProfileLoading = useAuthStore((s) => s.setProfileLoading)

  // Tracks which user id has already been hydrated so a token refresh
  // (Supabase's client silently refreshes the session - and does so
  // proactively whenever the browser tab regains focus/visibility)
  // doesn't re-trigger the full loading screen on every alt-tab back
  // into the app. Only a genuine sign-in for a *different* user (or
  // the very first load) should re-fetch and re-show it.
  const hydratedUserId = useRef<string | null>(null)

  useEffect(() => {
    if (!isSupabaseConfigured) {
      setAuthLoading(false)
      setProfileLoading(false)
      return
    }

    async function hydrate(userId: string) {
      if (hydratedUserId.current === userId) return
      hydratedUserId.current = userId
      setProfileLoading(true)
      try {
        const [{ data: profile }, { data: corporate }] = await Promise.all([
          supabase.from('profiles').select('*').eq('id', userId).maybeSingle(),
          supabase.from('corporate_accounts').select('*').eq('id', userId).maybeSingle(),
        ])

        if (profile) {
          setProfile(profile)
          setAccountKind('individual')
        } else if (corporate) {
          setCorporateAccount(corporate)
          setAccountKind('corporate')
        }
      } finally {
        setProfileLoading(false)
      }
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) hydrate(session.user.id).finally(() => setAuthLoading(false))
      else {
        setAuthLoading(false)
        setProfileLoading(false)
      }
    })

    // Fires on login, logout, and token refresh (including the
    // tab-focus refresh above) - not just on first load. hydrate()
    // itself no-ops for a user it's already loaded, so this stays
    // cheap and silent for anything but a real sign-in/sign-out.
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session) hydrate(session.user.id)
      else {
        hydratedUserId.current = null
        setProfileLoading(false)
      }
    })

    return () => subscription.subscription.unsubscribe()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
