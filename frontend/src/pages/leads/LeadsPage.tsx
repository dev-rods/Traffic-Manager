import { useState } from 'react'
import { useLeads } from '@/hooks/useLeads'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { formatPhone } from '@/utils/formatPhone'
import type { Lead } from '@/types'

type FilterStatus = 'all' | 'booked' | 'not_booked'

export function LeadsPage() {
  const [status, setStatus] = useState<FilterStatus>('all')
  const bookedParam = status === 'all' ? undefined : status === 'booked'

  const { data, isLoading, isError, error, refetch } = useLeads({
    booked: bookedParam,
    limit: 100,
  })

  const leads = data?.leads ?? []
  const totalLeads = data?.total ?? 0
  const bookedCount = leads.filter((l) => l.booked).length
  const notBookedCount = leads.filter((l) => !l.booked).length
  const conversionRate = totalLeads > 0 ? Math.round((bookedCount / totalLeads) * 100) : 0

  if (isLoading) return <div className="p-6"><SkeletonTable rows={8} /></div>
  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar leads.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Leads</h1>
        <p className="text-sm text-gray-400 mt-1">Contatos que iniciaram conversa com o bot</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard label="Total de leads" value={totalLeads} />
        <KpiCard label="Convertidos" value={bookedCount} />
        <KpiCard label="Não convertidos" value={notBookedCount} />
        <KpiCard label="Taxa de conversão" value={`${conversionRate}%`} />
      </div>

      {/* Filter */}
      <div className="flex gap-1">
        {([
          { key: 'all' as const, label: 'Todos' },
          { key: 'booked' as const, label: 'Convertidos' },
          { key: 'not_booked' as const, label: 'Não convertidos' },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setStatus(key)}
            className={[
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer',
              status === key ? 'bg-brand-500 text-white' : 'text-gray-500 hover:bg-gray-100',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      {leads.length === 0 ? (
        <EmptyState
          title="Nenhum lead encontrado"
          description={status !== 'all' ? 'Tente mudar o filtro.' : 'Leads aparecem quando pacientes entram em contato via WhatsApp.'}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                <th className="px-5 py-3">Contato</th>
                <th className="px-3 py-3">Telefone</th>
                <th className="px-3 py-3">Fonte</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Valor 1o agend.</th>
                <th className="px-3 py-3">Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {leads.map((lead: Lead) => (
                <tr key={lead.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-800">{lead.name || 'Sem nome'}</p>
                  </td>
                  <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                    {formatPhone(lead.phone)}
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant="neutral">{lead.source}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={lead.booked ? 'success' : 'warning'}>
                      {lead.booked ? 'Convertido' : 'Pendente'}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-gray-700 whitespace-nowrap">
                    {lead.first_appointment_value
                      ? `R$ ${lead.first_appointment_value.toFixed(2).replace('.', ',')}`
                      : '—'}
                  </td>
                  <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                    {new Date(lead.created_at).toLocaleDateString('pt-BR')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs text-gray-400 font-medium">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
    </Card>
  )
}
