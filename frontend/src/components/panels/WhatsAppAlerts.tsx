import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useMapStore } from '@/store/useMapStore'
import { useAuthStore } from '@/store/useAuthStore'

interface AlertData {
  alerts: { ward_id: string; group: string; date: string; body: string; advisory_body?: string; channels: string[] }[]
  history: { id: string; body: string; status: string; created_at: string }[]
}
interface SystemStatus {
  automation: { enabled: boolean; running: boolean; next_run: number; last_run: { status?: string; outcome?: string; finished_at?: number } }
  budget: { enabled: boolean; daily_limit: number; total_limit: number; remaining: number | null; total_attempts: number }
  history: AlertData['history']
  opted_in: boolean
}

export function WhatsAppAlerts() {
  const { t } = useTranslation()
  const session = useAuthStore((s) => s.session)
  const individualProfile = useAuthStore((s) => s.accountKind === 'individual' ? s.profile : null)
  const corporateAccount = useAuthStore((s) => s.accountKind === 'corporate' ? s.corporateAccount : null)
  const profile = individualProfile ?? corporateAccount
  const source = useMapStore((s) => s.source)
  const client = useQueryClient()

  async function request<T>(path: string, payload?: unknown): Promise<T> {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? '/api'}/alerts/${path}`, {
      method: payload ? 'POST' : 'GET',
      headers: { Authorization: `Bearer ${session?.access_token}`, 'Content-Type': 'application/json' },
      body: payload ? JSON.stringify(payload) : undefined,
    })
    if (!response.ok) throw new Error(t('whatsapp.error'))
    return response.json() as Promise<T>
  }

  const query = useQuery({
    queryKey: ['personal-alerts', profile?.id, source],
    queryFn: () => request<AlertData>(`me?source=${source}`),
    enabled: Boolean(session && profile),
    refetchInterval: 180_000,
  })

  const system = useQuery({
    queryKey: ['alert-system', profile?.id],
    queryFn: () => request<SystemStatus>('status'),
    enabled: Boolean(session && profile), refetchInterval: 30_000,
  })
  const refresh = useMutation({
    mutationFn: () => request('refresh-delivery', {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ['alert-system'] }),
  })

  return <section className="surface-card space-y-3 p-5">
    <h2 className="text-[15px] font-semibold">{t('whatsapp.title')}</h2>
    <div className="surface-sunken space-y-2 p-3 text-[13px]">
      <h3 className="font-semibold">{t('whatsapp.automatic')}</h3>
      {system.data && <>
        <p>{t(system.data.automation.enabled ? 'whatsapp.autoOn' : 'whatsapp.autoOff')}</p>
        {system.data.budget.enabled && <><p>{t('whatsapp.budget', { remaining: system.data.budget.remaining, daily: system.data.budget.daily_limit, total: system.data.budget.total_limit })}</p><p>{t('whatsapp.localBudget')}</p></>}
        {system.data.automation.last_run.finished_at && <p>{t('whatsapp.lastCheck')} {new Date(system.data.automation.last_run.finished_at * 1000).toLocaleString()} · {t(`whatsapp.outcome.${system.data.automation.last_run.outcome ?? system.data.automation.last_run.status}`)}</p>}
        {!system.data.opted_in && <p>{t('whatsapp.enableFirst')}</p>}
      </>}
      {(system.isError || refresh.isError) && <p role="alert">{t('whatsapp.error')}</p>}
    </div>
    <h3 className="text-[14px] font-semibold">{t('whatsapp.forecast')}</h3>
    {query.isError && <p role="alert" className="text-[13px]">{t('whatsapp.error')} <button className="underline" onClick={() => query.refetch()}>{t('common.retry')}</button></p>}
    {query.isLoading && <p role="status">{t('whatsapp.loading')}</p>}
    {query.data?.alerts.length === 0 && <p className="text-[13px]">{t('whatsapp.empty')}</p>}
    {query.data?.alerts.map((alert) => <article key={`${alert.ward_id}-${alert.group}-${alert.date}`} className="surface-sunken p-3">
      <p className="whitespace-pre-wrap text-[13px]">{alert.advisory_body ?? alert.body}</p>
      {!alert.channels.includes('whatsapp') && <p className="mt-2 text-[12px]">{t('whatsapp.dashboardOnly')}</p>}
    </article>)}
    {Boolean(system.data?.history.length) && <>
      <h3 className="text-[14px] font-semibold">{t('whatsapp.history')}</h3>
      <button className="btn btn-secondary" disabled={refresh.isPending} onClick={() => refresh.mutate()}>{t('whatsapp.refreshDelivery')}</button>
      {system.data?.history.map((item) => <details key={item.id} className="surface-sunken p-3 text-[13px]">
        <summary>{t(`whatsapp.status.${item.status}`, { defaultValue: t('whatsapp.status.unknown') })} · {item.created_at}</summary>
        <p className="mt-2 whitespace-pre-wrap">{item.body}</p>
      </details>)}
    </>}
  </section>
}
