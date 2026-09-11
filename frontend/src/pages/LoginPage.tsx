import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { supabase, isSupabaseConfigured } from '@/lib/supabase'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const { error: authError } = await supabase.auth.signInWithPassword({ email, password })
    setLoading(false)
    if (authError) {
      setError(t('auth.serviceUnavailableDetail'))
      return
    }
    navigate('/dashboard')
  }

  return (
    <div className="flex h-screen items-center justify-center px-4" style={{ background: 'var(--surface-page)' }}>
      <div className="w-full max-w-[380px]">
        <div className="mb-8 flex flex-col items-center gap-2 text-center">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style={{ color: 'var(--accent)' }}>
            <path
              d="M12 2C12 2 6 10 6 15a6 6 0 0 0 12 0c0-5-6-13-6-13Z"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinejoin="round"
            />
          </svg>
          <div className="text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('app.name')}</div>
        </div>

        <div className="surface-card p-7">
          <h1 className="text-[19px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('auth.loginTitle')}</h1>
          <p className="mt-1 text-[13px]" style={{ color: 'var(--text-secondary)' }}>{t('auth.loginSubtitle')}</p>

          {!isSupabaseConfigured && (
            <p className="mt-4 rounded-md p-3 text-[13px]" style={{ background: 'var(--risk-watch-soft)', color: 'var(--risk-watch)' }}>
              {t('auth.serviceUnavailable')}
            </p>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-3">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('auth.email')}
              className="input"
            />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('auth.password')}
              className="input"
            />
            {error && <p className="text-[13px]" style={{ color: 'var(--risk-danger)' }}>{error}</p>}
            <button type="submit" disabled={loading || !isSupabaseConfigured} className="btn btn-primary w-full">
              {loading ? t('common.loading') : t('auth.login')}
            </button>
          </form>

          <div className="mt-5 flex flex-col gap-1.5 border-t pt-4 text-[13px]" style={{ borderColor: 'var(--border-subtle)' }}>
            <Link to="/signup/individual" className="font-medium" style={{ color: 'var(--accent)' }}>
              {t('auth.individualSignup')}
            </Link>
            <Link to="/signup/corporate" className="font-medium" style={{ color: 'var(--accent)' }}>
              {t('auth.corporateSignup')}
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
