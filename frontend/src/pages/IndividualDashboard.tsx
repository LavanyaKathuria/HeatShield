import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { DashboardShell } from '@/components/layout/DashboardShell'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { TIER_COLOR, TIER_SOFT_COLOR } from '@/lib/riskTiers'
import { useWardPriority, useWardForecastTimeline } from '@/hooks/useForecastData'
import { useAuthStore } from '@/store/useAuthStore'
import { supabase, isSupabaseConfigured } from '@/lib/supabase'
import type { RelationshipType } from '@/types/supabase'
import type { WardHeatRisk } from '@/types/api'

const RELATIONSHIPS: RelationshipType[] = ['parent', 'grandparent', 'child', 'spouse', 'sibling', 'other']

function findWard(wards: WardHeatRisk[] | undefined, wardId: string | null): WardHeatRisk | undefined {
  return wardId ? wards?.find((w) => w.ward_id === wardId) : undefined
}

export function IndividualDashboard() {
  const { t } = useTranslation()
  const profile = useAuthStore((s) => s.profile)

  const priorityQuery = useWardPriority()
  const timelineQuery = useWardForecastTimeline()
  const queryClient = useQueryClient()

  // age is kept as a string while the field is being edited - Number()
  // on every keystroke turns a temporarily-empty field (while retyping)
  // into 0, which then gets stuck showing "0". Only converted to a
  // number right before the insert.
  const [newDependent, setNewDependent] = useState({
    full_name: '', relationship: 'grandparent' as RelationshipType, age: '65', is_outdoor_worker: false,
  })

  const dependentsQuery = useQuery({
    queryKey: ['dependents', profile?.id],
    queryFn: async () => {
      const { data, error } = await supabase.from('dependents').select('*').eq('profile_id', profile!.id)
      if (error) throw error
      return data
    },
    enabled: isSupabaseConfigured && Boolean(profile),
  })

  const addDependentMutation = useMutation({
    mutationFn: async () => {
      if (!profile) throw new Error('Not signed in')
      const { error } = await supabase.from('dependents').insert({
        profile_id: profile.id,
        full_name: newDependent.full_name,
        relationship: newDependent.relationship,
        age: Number(newDependent.age),
        is_outdoor_worker: newDependent.is_outdoor_worker,
      })
      if (error) throw error
    },
    onSuccess: () => {
      setNewDependent({ full_name: '', relationship: 'grandparent', age: '65', is_outdoor_worker: false })
      queryClient.invalidateQueries({ queryKey: ['dependents'] })
    },
  })

  const deleteDependentMutation = useMutation({
    mutationFn: async (dependentId: string) => {
      const { error } = await supabase.from('dependents').delete().eq('id', dependentId)
      if (error) throw error
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dependents'] }),
  })

  const myWard = findWard(priorityQuery.data?.wards, profile?.ward_id ?? null)
  const tier = myWard?.alert_level ?? 'none'


  const todayWardDay = useMemo(() => {
    if (!timelineQuery.data || !profile?.ward_id) return null
    const firstDate = timelineQuery.data.dates[0]
    return timelineQuery.data.days.find((d) => d.ward_id === profile.ward_id && d.date === firstDate) ?? null
  }, [timelineQuery.data, profile])

  return (
    <DashboardShell>
      <div className="border-b px-6 py-6" style={{ borderColor: 'var(--border-subtle)', background: 'var(--surface-card)' }}>
        <div className="mx-auto max-w-[720px]">
          <div className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--text-tertiary)' }}>
            {t('individual.heroTitle')}
          </div>

          {priorityQuery.isLoading && <div className="mt-3"><LoadingState /></div>}
          {priorityQuery.isError && <div className="mt-3"><ErrorState onRetry={() => priorityQuery.refetch()} /></div>}

          {!priorityQuery.isLoading && !priorityQuery.isError && (
            myWard ? (
              <>
                <div className="mt-1.5 flex flex-wrap items-center gap-2.5">
                  <span className="badge" style={{ color: TIER_COLOR[tier], background: TIER_SOFT_COLOR[tier], fontSize: '13px', padding: '4px 12px' }}>
                    {t(`tiers.${tier}`)}
                  </span>
                  <h1 className="text-[19px] font-semibold" style={{ color: 'var(--text-primary)' }}>{myWard.ward_name}</h1>
                </div>
                <p className="mt-1.5 max-w-lg text-[13px]" style={{ color: 'var(--text-secondary)' }}>{t(`tierDescriptions.${tier}`)}</p>

                <div className="mt-3 flex flex-wrap items-baseline gap-3">
                  <span className="font-tabular text-[32px] font-semibold leading-none" style={{ color: 'var(--text-primary)' }}>
                    {(todayWardDay?.tmax ?? myWard.peak_utci_c).toFixed(0)}Â°
                  </span>
                  <span className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>
                    {t('thermometer.feelsLike')} {myWard.peak_utci_c.toFixed(0)}Â°
                  </span>
                  {todayWardDay && (
                    <span className="text-[12px]" style={{ color: 'var(--text-tertiary)' }}>
                      {t('weather.humidity')} {todayWardDay.afternoon_humidity_pct.toFixed(0)}% Â· {t('weather.wind')} {todayWardDay.afternoon_wind_ms.toFixed(0)} m/s
                    </span>
                  )}
                </div>

                {myWard.recommended_action_key && (
                  <p className="surface-sunken mt-3 max-w-lg p-3 text-[13px]" style={{ color: 'var(--text-primary)' }}>
                    {t(`citizenActions.${myWard.recommended_action_key}`)}
                  </p>
                )}
              </>
            ) : (
              <p className="mt-2 text-[13px]" style={{ color: 'var(--text-tertiary)' }}>{t('individual.wardPrompt')}</p>
            )
          )}
        </div>
      </div>

      <div className="mx-auto max-w-[720px] space-y-4 px-6 py-6">
        <div className="surface-card p-5">
          <h2 className="text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('alerts.title')}</h2>
          <p className="mt-2 text-[13px]" style={{ color: 'var(--text-tertiary)' }}>{t('alerts.citizenEmpty')}</p>
          <p className="mt-1 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>{t('alerts.citizenEmptyExplainer')}</p>
        </div>

        <div className="surface-card p-5">
          <div className="flex items-center gap-2">
            <h2 className="text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('family.title')}</h2>
            <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'var(--surface-sunken)', color: 'var(--text-tertiary)' }}>
              {t('family.optionalNote')}
            </span>
          </div>
          <p className="mt-1 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>{t('family.description')}</p>

          {!isSupabaseConfigured && (
            <p className="mt-3 rounded-md p-3 text-[13px]" style={{ background: 'var(--risk-watch-soft)', color: 'var(--risk-watch)' }}>
              {t('auth.serviceUnavailable')}
            </p>
          )}

          {isSupabaseConfigured && (
            <>
              <div className="mt-4 space-y-2">
                {dependentsQuery.data?.map((dep) => (
                  <div key={dep.id} className="surface-sunken flex items-center justify-between gap-3 p-3">
                    <div>
                      <div className="text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>{dep.full_name}</div>
                      <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                        {t(`relationships.${dep.relationship}`)} Â· {t('auth.age')} {dep.age}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {myWard && (
                        <span className="badge" style={{ color: TIER_COLOR[tier], background: TIER_SOFT_COLOR[tier] }}>
                          {t(`tiers.${tier}`)}
                        </span>
                      )}
                      <button
                        onClick={() => deleteDependentMutation.mutate(dep.id)}
                        disabled={deleteDependentMutation.isPending}
                        className="rounded p-1 transition-colors hover:bg-[var(--risk-danger-soft)]"
                        aria-label={t('family.remove')}
                        title={t('family.remove')}
                      >
                        <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                          <path d="M3 4h10M6.5 4V2.5h3V4M4.5 4l.5 9.5a1 1 0 0 0 1 .95h4a1 1 0 0 0 1-.95L11.5 4" stroke="var(--text-tertiary)" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
                {dependentsQuery.data?.length === 0 && (
                  <p className="text-[13px]" style={{ color: 'var(--text-tertiary)' }}>{t('family.empty')}</p>
                )}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <input
                  value={newDependent.full_name}
                  onChange={(e) => setNewDependent({ ...newDependent, full_name: e.target.value })}
                  placeholder={t('auth.fullName')}
                  className="input col-span-2"
                />
                <select
                  value={newDependent.relationship}
                  onChange={(e) => setNewDependent({ ...newDependent, relationship: e.target.value as RelationshipType })}
                  className="input"
                >
                  {RELATIONSHIPS.map((r) => (
                    <option key={r} value={r}>{t(`relationships.${r}`)}</option>
                  ))}
                </select>
                <input
                  type="number"
                  value={newDependent.age}
                  onChange={(e) => setNewDependent({ ...newDependent, age: e.target.value })}
                  placeholder={t('auth.age')}
                  className="input"
                />
                <label className="col-span-2 flex items-center gap-2 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                  <input
                    type="checkbox"
                    checked={newDependent.is_outdoor_worker}
                    onChange={(e) => setNewDependent({ ...newDependent, is_outdoor_worker: e.target.checked })}
                  />
                  {t('auth.isOutdoorWorker')}
                </label>
              </div>
              <button
                onClick={() => addDependentMutation.mutate()}
                disabled={!newDependent.full_name || !newDependent.age || Number(newDependent.age) <= 0 || addDependentMutation.isPending}
                className="btn btn-primary mt-3 w-full"
              >
                {t('family.add')}
              </button>
            </>
          )}
        </div>
      </div>
    </DashboardShell>
  )
}


