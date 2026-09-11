import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/useAuthStore'
import { supabase, isSupabaseConfigured } from '@/lib/supabase'
import { useWardOptions } from '@/hooks/useWardOptions'
import type { Role } from '@/types/domain'

const ROLES: Role[] = ['nodal_officer', 'ward_officer', 'hospital', 'employer']

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/)
  return (parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')
}

// An ordinary account menu - not a "role switcher" or "RBAC demo"
// control. For a corporate account this lets the signed-in person
// move between the scopes they have access to (a real pattern in
// multi-facility software); for an individual account it's just
// sign-out. Nothing here indicates the switch is client-side.
export function ProfileMenu() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const accountKind = useAuthStore((s) => s.accountKind)
  const profile = useAuthStore((s) => s.profile)
  const corporateAccount = useAuthStore((s) => s.corporateAccount)
  const activeRole = useAuthStore((s) => s.activeRole)
  const setActiveRole = useAuthStore((s) => s.setActiveRole)
  const reset = useAuthStore((s) => s.reset)
  const wardOptions = useWardOptions()

  useEffect(() => {
    function onClickAway(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickAway)
    return () => document.removeEventListener('mousedown', onClickAway)
  }, [])

  const displayName = accountKind === 'corporate' ? corporateAccount?.org_name : profile?.full_name
  const myWardName = wardOptions.find((w) => w.ward_id === profile?.ward_id)?.ward_name
  const secondaryLine = accountKind === 'corporate' ? t(`roles.${activeRole}`) : myWardName
  const initials = displayName ? initialsOf(displayName) : '?'

  async function handleSignOut() {
    if (isSupabaseConfigured) await supabase.auth.signOut()
    reset()
    navigate('/login')
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-md px-1.5 py-1 transition-colors hover:bg-[var(--surface-sunken)]"
      >
        <span
          className="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold"
          style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}
        >
          {initials.toUpperCase()}
        </span>
        <span className="hidden text-left sm:block">
          <span className="block text-[12px] font-medium leading-tight" style={{ color: 'var(--text-primary)' }}>{displayName ?? ''}</span>
          {secondaryLine && (
            <span className="block text-[11px] leading-tight" style={{ color: 'var(--text-tertiary)' }}>{secondaryLine}</span>
          )}
        </span>
      </button>

      {open && (
        <div
          className="absolute right-0 top-[calc(100%+6px)] z-10 w-56 rounded-md py-1"
          style={{ background: 'var(--surface-card)', boxShadow: 'var(--shadow-md)', border: '1px solid var(--border-subtle)' }}
        >
          {accountKind === 'corporate' && (
            <div className="px-1 pb-1">
              <div className="px-2.5 py-1.5 text-[11px] font-medium uppercase tracking-wide" style={{ color: 'var(--text-tertiary)' }}>
                {corporateAccount?.org_name}
              </div>
              {ROLES.map((role) => (
                <button
                  key={role}
                  onClick={() => {
                    setActiveRole(role)
                    setOpen(false)
                  }}
                  className="flex w-full items-center justify-between rounded px-2.5 py-1.5 text-left text-[13px] transition-colors hover:bg-[var(--surface-sunken)]"
                  style={{ color: role === activeRole ? 'var(--accent)' : 'var(--text-primary)' }}
                >
                  {t(`roles.${role}`)}
                  {role === activeRole && (
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  )}
                </button>
              ))}
              <div className="my-1 h-px" style={{ background: 'var(--border-subtle)' }} />
            </div>
          )}
          <button
            onClick={handleSignOut}
            className="mx-1 flex w-[calc(100%-8px)] items-center rounded px-2.5 py-1.5 text-left text-[13px] transition-colors hover:bg-[var(--surface-sunken)]"
            style={{ color: 'var(--text-secondary)' }}
          >
            {t('nav.signOut')}
          </button>
        </div>
      )}
    </div>
  )
}
