import { useState } from 'react'
import { useServices } from '@/hooks/useServices'
import { useServiceAreas, useClinicAreas, useCreateServiceArea, useDeleteServiceArea, useUpdateServiceArea } from '@/hooks/useAreas'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import type { ClinicService } from '@/services/services.service'

export function ServicosAreasPage() {
  const { data: services, isLoading, isError, error, refetch } = useServices()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (isLoading) return <div className="p-6"><SkeletonTable rows={6} /></div>
  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar serviços.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Serviços & Áreas</h1>
        <p className="text-sm text-gray-400 mt-1">Gerencie os vínculos entre serviços e áreas de tratamento</p>
      </div>

      {!services || services.length === 0 ? (
        <EmptyState
          title="Nenhum serviço cadastrado"
          description="Cadastre serviços na página de Serviços para vincular áreas."
        />
      ) : (
        <div className="space-y-3">
          {services.map((svc) => (
            <ServiceAreaCard
              key={svc.id}
              service={svc}
              expanded={expandedId === svc.id}
              onToggle={() => setExpandedId(expandedId === svc.id ? null : svc.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ServiceAreaCard({ service, expanded, onToggle }: { service: ClinicService; expanded: boolean; onToggle: () => void }) {
  const { data: serviceAreas, isLoading: areasLoading } = useServiceAreas(expanded ? service.id : undefined)
  const { data: clinicAreas } = useClinicAreas()
  const createServiceArea = useCreateServiceArea()
  const deleteServiceArea = useDeleteServiceArea()
  const updateServiceArea = useUpdateServiceArea()

  const [editingAreaId, setEditingAreaId] = useState<string | null>(null)
  const [editDuration, setEditDuration] = useState(0)
  const [editPrice, setEditPrice] = useState('')
  const [editInstructions, setEditInstructions] = useState('')

  const linkedAreaIds = new Set(serviceAreas?.map((sa) => sa.area_id) ?? [])
  const unlinkedAreas = clinicAreas?.filter((a) => !linkedAreaIds.has(a.id)) ?? []

  const formatPrice = (cents: number | null) =>
    cents != null ? (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : '—'

  const handleLinkArea = async (areaId: string) => {
    await createServiceArea.mutateAsync({
      serviceId: service.id,
      payload: { area_id: areaId },
    })
  }

  const handleUnlinkArea = async (areaId: string) => {
    await deleteServiceArea.mutateAsync({ serviceId: service.id, areaId })
  }

  const openEditArea = (areaId: string, duration: number, priceCents: number | null, instructions: string | null) => {
    setEditingAreaId(areaId)
    setEditDuration(duration)
    setEditPrice(priceCents != null ? (priceCents / 100).toFixed(2) : '')
    setEditInstructions(instructions ?? '')
  }

  const handleSaveArea = async () => {
    if (!editingAreaId) return
    await updateServiceArea.mutateAsync({
      serviceId: service.id,
      areaId: editingAreaId,
      payload: {
        duration_minutes: editDuration > 0 ? editDuration : null,
        price_cents: editPrice ? Math.round(parseFloat(editPrice) * 100) : null,
        pre_session_instructions: editInstructions.trim() || null,
      },
    })
    setEditingAreaId(null)
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center justify-between px-4 py-3">
        <button onClick={onToggle} className="flex items-center gap-3 flex-1 text-left">
          <span className={['text-xs transition-transform', expanded ? 'rotate-90' : ''].join(' ')}>
            ▶
          </span>
          <div>
            <p className="text-sm font-semibold text-gray-800">{service.name}</p>
            <p className="text-xs text-gray-400">
              {service.duration_minutes} min · {formatPrice(service.price_cents)}
              {serviceAreas ? ` · ${serviceAreas.length} área${serviceAreas.length !== 1 ? 's' : ''}` : ''}
            </p>
          </div>
        </button>
      </div>

      {expanded && (
        <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/30">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Áreas vinculadas</p>

          {areasLoading ? (
            <div className="text-xs text-gray-400 py-2">Carregando...</div>
          ) : serviceAreas && serviceAreas.length > 0 ? (
            <div className="space-y-1 mb-4">
              {serviceAreas.map((sa) => (
                <div key={sa.area_id}>
                  <div className="flex items-center justify-between py-2 px-2 rounded-md hover:bg-gray-100/50">
                    <div>
                      <span className="text-sm text-gray-700">{sa.name}</span>
                      <span className="text-xs text-gray-400 ml-2">
                        {sa.effective_duration_minutes}min · {formatPrice(sa.effective_price_cents)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openEditArea(sa.area_id, sa.duration_minutes ?? sa.effective_duration_minutes, sa.price_cents, sa.pre_session_instructions)}
                        className="text-xs text-gray-400 hover:text-brand-600 transition-colors font-medium"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => void handleUnlinkArea(sa.area_id)}
                        disabled={deleteServiceArea.isPending}
                        className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                      >
                        Desvincular
                      </button>
                    </div>
                  </div>

                  {editingAreaId === sa.area_id && (
                    <div className="px-2 pb-2 pt-1">
                      <div className="grid grid-cols-2 gap-3 mb-2">
                        <div>
                          <label className="text-[11px] text-gray-400 block mb-1">Duração (min)</label>
                          <input
                            type="number"
                            value={editDuration}
                            onChange={(e) => setEditDuration(parseInt(e.target.value, 10) || 0)}
                            min={0}
                            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-gray-400 block mb-1">Preço (R$)</label>
                          <input
                            type="text"
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            placeholder="Usar padrão do serviço"
                            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                          />
                        </div>
                      </div>
                      <div className="mb-2">
                        <label className="text-[11px] text-gray-400 block mb-1">Instruções pré-sessão</label>
                        <textarea
                          value={editInstructions}
                          onChange={(e) => setEditInstructions(e.target.value)}
                          rows={2}
                          placeholder="Instruções enviadas ao paciente antes da sessão nesta área..."
                          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <button onClick={() => setEditingAreaId(null)} className="text-xs text-gray-400 hover:text-gray-600 px-3 py-1.5">
                          Cancelar
                        </button>
                        <Button size="sm" onClick={() => void handleSaveArea()} loading={updateServiceArea.isPending}>
                          Salvar
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400 mb-4">Nenhuma área vinculada a este serviço</p>
          )}

          {unlinkedAreas.length > 0 && (
            <div>
              <p className="text-[11px] text-gray-400 mb-1.5">Vincular área:</p>
              <div className="flex flex-wrap gap-1.5">
                {unlinkedAreas.map((area) => (
                  <button
                    key={area.id}
                    onClick={() => void handleLinkArea(area.id)}
                    disabled={createServiceArea.isPending}
                    className="px-2.5 py-1 rounded-md text-xs font-medium border border-dashed border-gray-300 text-gray-500 hover:border-brand-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                  >
                    + {area.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
