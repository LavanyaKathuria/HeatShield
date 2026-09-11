import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthListener } from '@/hooks/useAuthListener'
import { useAuthStore } from '@/store/useAuthStore'
import { LoadingState } from '@/components/common/LoadingState'
import { LoginPage } from '@/pages/LoginPage'
import { SignupIndividualPage } from '@/pages/SignupIndividualPage'
import { SignupCorporatePage } from '@/pages/SignupCorporatePage'
import { DashboardPage } from '@/pages/DashboardPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const session = useAuthStore((s) => s.session)
  const authLoading = useAuthStore((s) => s.authLoading)

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'var(--surface-page)' }}>
        <LoadingState />
      </div>
    )
  }

  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  useAuthListener()

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup/individual" element={<SignupIndividualPage />} />
        <Route path="/signup/corporate" element={<SignupCorporatePage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
