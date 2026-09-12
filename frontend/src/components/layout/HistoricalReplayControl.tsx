import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useMapStore } from '@/store/useMapStore'
import { useAuthStore } from '@/store/useAuthStore'

export function HistoricalReplayControl() {
  const { t } = useTranslation()
  const source = useMapStore((s) => s.source)
  const setSource = useMapStore((s) => s.setSource)
  const session = useAuthStore((s) => s.session)
  const client = useQueryClient()
  const send = useMutation({
    mutationFn: async () => {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? '/api'}/alerts/replay`, {
        method: 'POST', headers: { Authorization: `Bearer ${session?.access_token}` },
      })
      if (!response.ok) throw new Error('Replay alert dispatch failed')
      return response.json() as Promise<{ status: string; results: { status: string }[] }>
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ['alert-system'] }),
  })
  const active = source === 'may_2024'
  return <div className="relative shrink-0">
    <button className="btn btn-secondary !text-[12px]" aria-pressed={active} disabled={send.isPending}
      onClick={() => {
        setSource(active ? 'live' : 'may_2024')
        send.reset()
        if (!active && session) send.mutate()
      }}>{t(active ? 'replay.exit' : 'replay.enter')}</button>
    {active && <div role="status" className="absolute left-0 top-full z-50 mt-1 max-w-[300px] rounded bg-[var(--surface-card)] px-2 py-1 text-[11px] shadow">
      {send.isPending ? t('replay.sending') : send.isError ? t('replay.sendError') : send.data?.status === 'opted_out' ? t('replay.optedOut') : send.data?.results.length === 0 ? t('replay.empty') : send.data ?
        [...new Set(send.data.results.map((r) => r.status))].map((status) => status === 'suppressed' ? t('replay.recent') : t(`whatsapp.status.${status}`, { defaultValue: status })).join(' · ') : t('replay.previewOnly')}
    </div>}
  </div>
}
