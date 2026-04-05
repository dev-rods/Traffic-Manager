import { useState } from 'react'
import { useServices, useCreateService, useUpdateService } from '@/hooks/useServices'
import { useServiceAreas, useClinicAreas, useCreateServiceArea, useDeleteServiceArea } from '@/hooks/useAreas'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import type { ClinicService } from '@/services/services.service'

export function ServicosPage() {
  const { data: services, isLoading, isError, error, refetch } = useServices()
  const createService = useCreateService()

  const [showCreate, setShowCreate] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Create form
  const [newName, setNewName] = useState('')
  const [newDuration, setNewDuration] = useState(30)
  const [newPrice, setNewPrice] = useState('')

  const handleCreate = async () => {
    if (!newName.trim() || newDuration <= 0) return
    await createService.mutateAsync({
      name: newName.trim(),
      duration_minutes: newDuration,
      price_cents: newPrice ? Math.round(parseFloat(newPrice) * 100) : undefined,
    })
    setNewName('')
    setNewDuration(30)
    setNewPrice('')
    setShowCreate(false)
  }

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
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Serviços</h1>
          <p className="text-sm text-gray-400 mt-1">Gerencie os serviços oferecidos pela clínica</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>+ Novo serviço</Button>
      </div>

      {!services || services.length === 0 ? (
        <EmptyState
          title="Nenhum serviço cadastrado"
          description="Crie serviços para começar a agendar."
          action={
            <Button size="sm" onClick={() => setShowCreate(true)}>Criar primeiro serviço</Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {services.map((svc) => (
            <ServiceCard
              key={svc.id}
              service={svc}
              expanded={expandedId === svc.id}
              onToggle={() => setExpandedId(expandedId === svc.id ? null : svc.id)}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Novo serviço">
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Nome</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Ex: Depilação a Laser"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              autoFocus
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1.5">Duração (min)</label>
              <input
                type="number"
                value={newDuration}
                onChange={(e) => setNewDuration(parseInt(e.target.value, 10) || 0)}
                min={5}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1.5">Preço base (R$)</label>
              <input
                type="text"
                value={newPrice}
                onChange={(e) => setNewPrice(e.target.value)}
                placeholder="0,00"
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancelar</Button>
            <Button
              onClick={() => void handleCreate()}
              loading={createService.isPending}
              disabled={!newName.trim()}
            >
              Criar serviço
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

// ── Service card with expandable areas ───────────────────────
function ServiceCard({ service, expanded, onToggle }: { service: ClinicService; expanded: boolean; onToggle: () => void }) {
  const updateService = useUpdateService()
  const { data: serviceAreas, isLoading: areasLoading } = useServiceAreas(expanded ? service.id : undefined)
  const { data: clinicAreas } = useClinicAreas()
  const createServiceArea = useCreateServiceArea()
  const deleteServiceArea = useDeleteServiceArea()

  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState(service.name)
  const [editDuration, setEditDuration] = useState(service.duration_minutes)
  const [editPrice, setEditPrice] = useState(service.price_cents ? (service.price_cents / 100).toFixed(2) : '')

  const handleSave = async () => {
    await updateService.mutateAsync({
      serviceId: service.id,
      payload: {
        name: editName.trim(),
        duration_minutes: editDuration,
        price_cents: editPrice ? Math.round(parseFloat(editPrice) * 100) : undefined,
      },
    })
    setEditing(false)
  }

  const handleLinkArea = async (areaId: string) => {
    await createServiceArea.mutateAsync({
      serviceId: service.id,
      payload: { area_id: areaId },
    })
  }

  const handleUnlinkArea = async (areaId: string) => {
    await deleteServiceArea.mutateAsync({ serviceId: service.id, areaId })
  }

  const linkedAreaIds = new Set(serviceAreas?.map((sa) => sa.area_id) ?? [])
  const unlinkedAreas = clinicAreas?.filter((a) => !linkedAreaIds.has(a.id)) ?? []

  const formatPrice = (cents: number | null) =>
    cents != null ? (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : '—'

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <button onClick={onToggle} className="flex items-center gap-3 flex-1 text-left">
          <span className={['text-xs transition-transform', expanded ? 'rotate-90' : ''].join(' ')}>
            ▶
          </span>
          <div>
            <p className="text-sm font-semibold text-gray-800">{service.name}</p>
            <p className="text-xs text-gray-400">
              {service.duration_minutes} min · {formatPrice(service.price_cents)}
            </p>
          </div>
        </button>
        <button
          onClick={() => { setEditing(true); setEditName(service.name); setEditDuration(service.duration_minutes); setEditPrice(service.price_cents ? (service.price_cents / 100).toFixed(2) : '') }}
          className="text-xs text-gray-400 hover:text-brand-600 transition-colors font-medium"
        >
          Editar
        </button>
      </div>

      {/* Edit inline */}
      {editing && (
        <div className="px-4 pb-3 border-t border-gray-100 pt-3 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[11px] text-gray-400 block mb-1">Nome</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-400 block mb-1">Duração (min)</label>
              <input
                type="number"
                value={editDuration}
                onChange={(e) => setEditDuration(parseInt(e.target.value, 10) || 0)}
                min={5}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-400 block mb-1">Preço (R$)</label>
              <input
                type="text"
                value={editPrice}
                onChange={(e) => setEditPrice(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setEditing(false)} className="text-xs text-gray-400 hover:text-gray-600 px-3 py-1.5">
              Cancelar
            </button>
            <button
              onClick={() => void handleSave()}
              disabled={updateService.isPending}
              className="text-xs font-semibold text-white bg-brand-500 hover:bg-brand-600 px-3 py-1.5 rounded-lg transition-colors"
            >
              {updateService.isPending ? 'Salvando...' : 'Salvar'}
            </button>
          </div>
        </div>
      )}

      {/* Expanded areas */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/30">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Áreas vinculadas</p>

          {areasLoading ? (
            <div className="text-xs text-gray-400 py-2">Carregando...</div>
          ) : serviceAreas && serviceAreas.length > 0 ? (
            <div className="space-y-1 mb-3">
              {serviceAreas.map((sa) => (
                <div key={sa.area_id} className="flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-gray-100/50">
                  <div>
                    <span className="text-sm text-gray-700">{sa.name}</span>
                    <span className="text-xs text-gray-400 ml-2">
                      {sa.effective_duration_minutes}min · {formatPrice(sa.effective_price_cents)}
                    </span>
                  </div>
                  <button
                    onClick={() => void handleUnlinkArea(sa.area_id)}
                    disabled={deleteServiceArea.isPending}
                    className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                  >
                    Desvincular
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400 mb-3">Nenhuma área vinculada</p>
          )}

          {/* Link new area */}
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
