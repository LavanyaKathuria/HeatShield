import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/store/useAuthStore'
import { CorporateDashboard } from '@/pages/CorporateDashboard'
import { IndividualDashboard } from '@/pages/IndividualDashboard'
import { LoadingState } from '@/components/common/LoadingState'

// Same underlying forecast data, two different account kinds get two
// different shaped experiences - the full disaster-console (corporate:
// admin/hospital/school/PHC) vs. a personal ward+dependents view
// (individual).
export function DashboardPage() {
  const { t } = useTranslation()
  const accountKind = useAuthStore((s) => s.accountKind)
  const profileLoading = useAuthStore((s) => s.profileLoading)

  // A session existing doesn't mean the profile/corporate_account row
  // has been fetched yet - that fetch is async and, right after a
  // fresh login, hasn't resolved by the time this renders. Show a
  // loading state instead of treating "not hydrated yet" the same as
  // "not logged in" (which was bouncing straight back to /login).
  if (profileLoading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'var(--surface-page)' }}>
        <LoadingState label={t('common.loadingAccount')} />
      </div>
    )
  }

  if (accountKind === 'corporate') return <CorporateDashboard />
  if (accountKind === 'individual') return <IndividualDashboard />

  return <Navigate to="/login" replace />
}
