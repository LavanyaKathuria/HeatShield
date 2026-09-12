import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { supabase, isSupabaseConfigured } from '@/lib/supabase'
import { useWardOptions } from '@/hooks/useWardOptions'

export function SignupIndividualPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const wards = useWardOptions()

  const [form, setForm] = useState({
    email: '', password: '', full_name: '', phone: '', age: '', ward_id: '',
    preferred_language: 'en', is_outdoor_worker: false,
  })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [pendingConfirmation, setPendingConfirmation] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    let phone = form.phone.trim().replace(/[\s()-]/g, '')
    if (/^[6-9]\d{9}$/.test(phone)) phone = `+91${phone}`
    if (phone && !/^\+[1-9]\d{7,14}$/.test(phone)) {
      setError(t('whatsapp.invalidPhone'))
      return
    }
    setLoading(true)

    // All profile fields travel as signUp metadata, not a follow-up
    // insert - see supabase/schema.sql's handle_new_user() trigger for
    // why: a client-side insert right after signUp() fails RLS when
    // email confirmation is required, because there's no session yet.
    const { data, error: authError } = await supabase.auth.signUp({
      email: form.email,
      password: form.password,
      options: {
        data: {
          account_kind: 'individual',
          full_name: form.full_name,
          phone: phone || null,
          preferred_language: form.preferred_language,
          ward_id: form.ward_id || null,
          age: form.age || null,
          is_outdoor_worker: form.is_outdoor_worker,
        },
      },
    })

    setLoading(false)

    if (authError || !data.user) {
      setError(t('auth.serviceUnavailableDetail'))
      return
    }

    if (!data.session) {
      setPendingConfirmation(true)
      return
    }

    navigate('/dashboard')
  }

  const cardHeader = (
    <div className="mb-8 flex flex-col items-center gap-2 text-center">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style={{ color: 'var(--accent)' }}>
        <path d="M12 2C12 2 6 10 6 15a6 6 0 0 0 12 0c0-5-6-13-6-13Z" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" />
      </svg>
      <div className="text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('app.name')}</div>
    </div>
  )

  if (pendingConfirmation) {
    return (
      <div className="flex h-screen items-center justify-center px-4" style={{ background: 'var(--surface-page)' }}>
        <div className="w-full max-w-[380px]">
          {cardHeader}
          <div className="surface-card p-7 text-center">
            <p className="text-[14px]" style={{ color: 'var(--text-primary)' }}>{t('auth.checkEmailConfirm')}</p>
            <Link to="/login" className="mt-4 inline-block text-[13px] font-medium" style={{ color: 'var(--accent)' }}>
              {t('auth.login')}
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: 'var(--surface-page)' }}>
      <div className="w-full max-w-[380px]">
        {cardHeader}
        <div className="surface-card p-7">
          <h1 className="text-[19px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('auth.individualSignupTitle')}</h1>
          <p className="mt-1 text-[13px]" style={{ color: 'var(--text-secondary)' }}>{t('auth.individualSignupSubtitle')}</p>

          {!isSupabaseConfigured && (
            <p className="mt-4 rounded-md p-3 text-[13px]" style={{ background: 'var(--risk-watch-soft)', color: 'var(--risk-watch)' }}>
              {t('auth.serviceUnavailable')}
            </p>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-3">
            <input
              required
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              placeholder={t('auth.fullName')}
              className="input"
            />
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder={t('auth.email')}
              className="input"
            />
            <input
              type="password"
              required
              minLength={6}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder={t('auth.password')}
              className="input"
            />
            <input
              value={form.phone}
              type="tel"
              autoComplete="tel"
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder={t('auth.phone')}
              className="input"
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                type="number"
                value={form.age}
                onChange={(e) => setForm({ ...form, age: e.target.value })}
                placeholder={t('auth.age')}
                className="input"
              />
              <select
                value={form.preferred_language}
                onChange={(e) => setForm({ ...form, preferred_language: e.target.value })}
                className="input"
              >
                <option value="en">English</option>
                <option value="hi">हिन्दी</option>
                <option value="gu">ગુજરાતી</option>
              </select>
            </div>
            <select
              value={form.ward_id}
              onChange={(e) => setForm({ ...form, ward_id: e.target.value })}
              className="input"
            >
              <option value="">{t('auth.ward')}</option>
              {wards.map((w) => (
                <option key={w.ward_id} value={w.ward_id}>{w.ward_name}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-[13px]" style={{ color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={form.is_outdoor_worker}
                onChange={(e) => setForm({ ...form, is_outdoor_worker: e.target.checked })}
              />
              {t('auth.isOutdoorWorker')}
            </label>

            {error && <p className="text-[13px]" style={{ color: 'var(--risk-danger)' }}>{error}</p>}

            <button type="submit" disabled={loading || !isSupabaseConfigured} className="btn btn-primary w-full">
              {loading ? t('common.loading') : t('auth.signup')}
            </button>
          </form>

          <p className="mt-4 text-center text-[13px]" style={{ color: 'var(--text-tertiary)' }}>
            {t('auth.haveAccount')} <Link to="/login" className="font-medium" style={{ color: 'var(--accent)' }}>{t('auth.login')}</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
