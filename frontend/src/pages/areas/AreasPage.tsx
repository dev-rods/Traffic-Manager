import { useState } from 'react'
import { useClinicAreas, useCreateArea, useUpdateArea, useDeleteArea } from '@/hooks/useAreas'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import type { ClinicArea } from '@/types'

export function AreasPage() {
  const { data: areas, isLoading, isError, error, refetch } = useClinicAreas()
  const createArea = useCreateArea()
  const updateArea = useUpdateArea()
  const deleteArea = useDeleteArea()

  const [showCreate, setShowCreate] = useState(false)
  const [editingArea, setEditingArea] = useState<ClinicArea | null>(null)
  const [newName, setNewName] = useState('')
  const [editName, setEditName] = useState('')
  const [editOrder, setEditOrder] = useState(0)

  const handleCreate = async () => {
    if (!newName.trim()) return
    await createArea.mutateAsync({ name: newName.trim() })
    setNewName('')
    setShowCreate(false)
  }

  const handleUpdate = async () => {
    if (!editingArea || !editName.trim()) return
    await updateArea.mutateAsync({
      areaId: editingArea.id,
      payload: { name: editName.trim(), display_order: editOrder },
    })
    setEditingArea(null)
  }

  const handleDelete = async (areaId: string) => {
    await deleteArea.mutateAsync(areaId)
  }

  const openEdit = (area: ClinicArea) => {
    setEditingArea(area)
    setEditName(area.name)
    setEditOrder(area.display_order)
  }

  if (isLoading) return <div className="p-6"><SkeletonTable rows={6} /></div>
  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar áreas.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Áreas</h1>
          <p className="text-sm text-gray-400 mt-1">Catálogo de áreas de tratamento da clínica</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>+ Nova área</Button>
      </div>

      {!areas || areas.length === 0 ? (
        <EmptyState
          title="Nenhuma área cadastrada"
          description="Crie áreas de tratamento para vincular aos serviços."
          action={
            <Button size="sm" onClick={() => setShowCreate(true)}>Criar primeira área</Button>
          }
        />
      ) : (
        <div className="rounded-lg border border-gray-200 divide-y divide-gray-100">
          {areas.map((area) => (
            <div
              key={area.id}
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-500">
                  {area.display_order}
                </span>
                <span className="text-sm font-medium text-gray-800">{area.name}</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => openEdit(area)}
                  className="text-xs text-gray-400 hover:text-brand-600 transition-colors font-medium"
                >
                  Editar
                </button>
                <button
                  onClick={() => void handleDelete(area.id)}
                  disabled={deleteArea.isPending}
                  className="text-xs text-gray-400 hover:text-red-500 transition-colors font-medium"
                >
                  Remover
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nova área">
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Nome</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Ex: Abdômen, Axilas..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate() }}
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancelar</Button>
            <Button onClick={() => void handleCreate()} loading={createArea.isPending} disabled={!newName.trim()}>
              Criar área
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal open={!!editingArea} onClose={() => setEditingArea(null)} title="Editar área">
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Nome</label>
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Ordem de exibição</label>
            <input
              type="number"
              value={editOrder}
              onChange={(e) => setEditOrder(parseInt(e.target.value, 10) || 0)}
              min={0}
              className="w-24 border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setEditingArea(null)}>Cancelar</Button>
            <Button onClick={() => void handleUpdate()} loading={updateArea.isPending} disabled={!editName.trim()}>
              Salvar
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
