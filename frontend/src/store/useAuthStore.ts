import { create } from 'zustand'
import type { Session } from '@supabase/supabase-js'
import type { ProfileRow, CorporateAccountRow } from '@/types/supabase'
import type { AccountKind, Role } from '@/types/domain'

interface AuthState {
  session: Session | null
  accountKind: AccountKind | null
  profile: ProfileRow | null
  corporateAccount: CorporateAccountRow | null
  // Demo-scope role switcher for the corporate/admin console (see
  // components/layout/ProfileMenu.tsx docstring for the real-RBAC
  // caveat - this filters the view client-side, it does not yet change
  // what the backend/Supabase RLS actually authorizes).
  activeRole: Role
  // True only while the initial supabase.auth.getSession() check on
  // first app load is in flight.
  authLoading: boolean
  // True while a profile/corporate_account row is being fetched for a
  // session that already exists (initial load AND right after a fresh
  // login). Distinct from authLoading: without this, DashboardPage saw
  // session=set but accountKind=null immediately after login (the
  // profile fetch hadn't resolved yet) and bounced back to /login
  // before hydration ever finished.
  profileLoading: boolean

  setSession: (session: Session | null) => void
  setProfile: (profile: ProfileRow | null) => void
  setCorporateAccount: (account: CorporateAccountRow | null) => void
  setAccountKind: (kind: AccountKind | null) => void
  setActiveRole: (role: Role) => void
  setAuthLoading: (loading: boolean) => void
  setProfileLoading: (loading: boolean) => void
  reset: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  accountKind: null,
  profile: null,
  corporateAccount: null,
  activeRole: 'nodal_officer',
  authLoading: true,
  profileLoading: true,

  setSession: (session) => set({ session }),
  setProfile: (profile) => set({ profile }),
  setCorporateAccount: (corporateAccount) => set({ corporateAccount }),
  setAccountKind: (accountKind) => set({ accountKind }),
  setActiveRole: (activeRole) => set({ activeRole }),
  setAuthLoading: (authLoading) => set({ authLoading }),
  setProfileLoading: (profileLoading) => set({ profileLoading }),
  reset: () =>
    set({
      session: null,
      accountKind: null,
      profile: null,
      corporateAccount: null,
      activeRole: 'nodal_officer',
      profileLoading: false,
    }),
}))
