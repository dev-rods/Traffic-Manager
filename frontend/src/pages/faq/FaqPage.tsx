import { useState } from 'react'
import { useFaq, useCreateFaq, useUpdateFaq } from '@/hooks/useFaq'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import type { FaqItem } from '@/types'

export function FaqPage() {
  const { data: faqs, isLoading, isError, error, refetch } = useFaq()
  const createFaq = useCreateFaq()
  const updateFaq = useUpdateFaq()

  const [showCreate, setShowCreate] = useState(false)
  const [editingFaq, setEditingFaq] = useState<FaqItem | null>(null)

  // Create form
  const [newKey, setNewKey] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [newAnswer, setNewAnswer] = useState('')

  // Edit form
  const [editLabel, setEditLabel] = useState('')
  const [editAnswer, setEditAnswer] = useState('')
  const [editOrder, setEditOrder] = useState(0)

  const handleCreate = async () => {
    if (!newKey.trim() || !newLabel.trim() || !newAnswer.trim()) return
    await createFaq.mutateAsync({
      question_key: newKey.trim().toLowerCase().replace(/\s+/g, '_'),
      question_label: newLabel.trim(),
      answer: newAnswer.trim(),
    })
    setNewKey('')
    setNewLabel('')
    setNewAnswer('')
    setShowCreate(false)
  }

  const handleUpdate = async () => {
    if (!editingFaq) return
    await updateFaq.mutateAsync({
      faqId: editingFaq.id,
      payload: {
        question_label: editLabel.trim(),
        answer: editAnswer.trim(),
        display_order: editOrder,
      },
    })
    setEditingFaq(null)
  }

  const handleToggleActive = async (faq: FaqItem) => {
    await updateFaq.mutateAsync({
      faqId: faq.id,
      payload: { active: !faq.active },
    })
  }

  const openEdit = (faq: FaqItem) => {
    setEditingFaq(faq)
    setEditLabel(faq.question_label)
    setEditAnswer(faq.answer)
    setEditOrder(faq.display_order)
  }

  if (isLoading) return <div className="p-6"><SkeletonTable rows={5} /></div>
  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar FAQ.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">FAQ</h1>
          <p className="text-sm text-gray-400 mt-1">Perguntas frequentes respondidas pelo bot do WhatsApp</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>+ Nova pergunta</Button>
      </div>

      {!faqs || faqs.length === 0 ? (
        <EmptyState
          title="Nenhuma pergunta cadastrada"
          description="Crie perguntas frequentes para o bot responder automaticamente."
          action={
            <Button size="sm" onClick={() => setShowCreate(true)}>Criar primeira pergunta</Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {faqs.map((faq) => (
            <div
              key={faq.id}
              className="rounded-lg border border-gray-200 bg-white px-4 py-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-gray-400 bg-gray-100">
                      {faq.question_key}
                    </span>
                    <span className="text-[11px] text-gray-300">#{faq.display_order}</span>
                  </div>
                  <p className="text-sm font-semibold text-gray-800 mb-1">{faq.question_label}</p>
                  <p className="text-sm text-gray-500 whitespace-pre-line">{faq.answer}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => openEdit(faq)}
                    className="text-xs text-gray-400 hover:text-brand-600 transition-colors font-medium"
                  >
                    Editar
                  </button>
                  <button
                    onClick={() => void handleToggleActive(faq)}
                    className={[
                      'text-xs font-medium transition-colors',
                      faq.active ? 'text-gray-400 hover:text-red-500' : 'text-green-600 hover:text-green-700',
                    ].join(' ')}
                  >
                    {faq.active ? 'Desativar' : 'Ativar'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nova pergunta" width="lg">
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Chave (identificador único)</label>
            <input
              type="text"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="Ex: horario_funcionamento"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 font-mono"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Pergunta (como o cliente pergunta)</label>
            <input
              type="text"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="Ex: Qual o horário de funcionamento?"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Resposta</label>
            <textarea
              value={newAnswer}
              onChange={(e) => setNewAnswer(e.target.value)}
              rows={4}
              placeholder="Resposta que o bot envia..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancelar</Button>
            <Button
              onClick={() => void handleCreate()}
              loading={createFaq.isPending}
              disabled={!newKey.trim() || !newLabel.trim() || !newAnswer.trim()}
            >
              Criar pergunta
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal open={!!editingFaq} onClose={() => setEditingFaq(null)} title="Editar pergunta" width="lg">
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Pergunta</label>
            <input
              type="text"
              value={editLabel}
              onChange={(e) => setEditLabel(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Resposta</label>
            <textarea
              value={editAnswer}
              onChange={(e) => setEditAnswer(e.target.value)}
              rows={4}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
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
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setEditingFaq(null)}>Cancelar</Button>
            <Button onClick={() => void handleUpdate()} loading={updateFaq.isPending} disabled={!editLabel.trim() || !editAnswer.trim()}>
              Salvar
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
