import { useState, useMemo } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useSendBatchMessages, type BatchMessageResult } from '@/hooks/useMessages'
import { formatPhone } from '@/utils/formatPhone'
import { buildDefaultMessage } from '@/utils/buildDefaultMessage'
import type { PatientWithStats } from '@/types'
import type { SendMessagePayload } from '@/services/messages.service'

function getStatusLabel(result: BatchMessageResult | undefined): { text: string; className: string } | null {
  if (!result) return null
  if (result.status === 'failed') return { text: 'Falhou', className: 'text-red-500' }
  if (result.status === 'pending') return { text: '...', className: 'text-gray-400' }
  // status === 'sent' | 'queued'
  if (result.delivery === 'delivered') return { text: 'Entregue', className: 'text-emerald-600' }
  if (result.delivery === 'sent_only') return { text: 'Sem confirmação', className: 'text-amber-600' }
  if (result.delivery === 'checking') return { text: 'Verificando...', className: 'text-gray-500' }
  return { text: 'Enviado', className: 'text-emerald-600' }
}

interface BatchMessageModalProps {
  open: boolean
  patients: PatientWithStats[]
  availableDates: string[]
  clinicTemplate?: string | null
  onClose: () => void
  onDone: () => void
}

export function BatchMessageModal({ open, patients, availableDates, clinicTemplate, onClose, onDone }: BatchMessageModalProps) {
  const [messageTemplate, setMessageTemplate] = useState(() =>
    clinicTemplate?.trim() ? clinicTemplate : buildDefaultMessage(availableDates),
  )
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set())
  const { send, results, isSending, isCheckingDelivery, progress, reset } = useSendBatchMessages()

  const activePatients = useMemo(
    () => patients.filter((p) => !removedIds.has(p.id)),
    [patients, removedIds],
  )

  const isDone = results.length > 0 && !isSending && !isCheckingDelivery

  const handleRemovePatient = (id: string) => {
    setRemovedIds((prev) => new Set([...prev, id]))
  }

  const handleSend = async () => {
    const payloads: SendMessagePayload[] = activePatients.map((p) => {
      const firstName = p.name?.split(' ')[0] || 'Ola'
      const body = messageTemplate.replace(/\{nome\}/g, firstName)
      return {
        patient_id: p.id,
        phone: p.phone,
        template: 'livre' as const,
        body,
      }
    })
    await send(payloads)
  }

  const handleClose = () => {
    reset()
    setRemovedIds(new Set())
    onClose()
    if (isDone) onDone()
  }

  const previewMessage = useMemo(() => {
    const firstName = activePatients[0]?.name?.split(' ')[0] || 'Maria'
    return messageTemplate.replace(/\{nome\}/g, firstName)
  }, [messageTemplate, activePatients])

  const deliveredCount = results.filter((r) => r.delivery === 'delivered').length
  const unconfirmedCount = results.filter((r) => (r.status === 'sent' || r.status === 'queued') && r.delivery === 'sent_only').length
  const failedCount = results.filter((r) => r.status === 'failed').length

  return (
    <Modal open={open} onClose={handleClose} title="Enviar WhatsApp em lote" width="lg">
      <div className="space-y-5">
        {/* Patient list */}
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">
            Pacientes ({activePatients.length})
          </label>
          <div className="rounded-lg border border-gray-200 max-h-40 overflow-y-auto divide-y divide-gray-50">
            {activePatients.map((p) => {
              const result = results.find((r) => r.patientId === p.id)
              const label = getStatusLabel(result)
              return (
                <div key={p.id} className="flex items-center justify-between px-3 py-2">
                  <div className="flex items-center gap-2">
                    <p className="text-sm text-gray-800">{p.name ?? 'Sem nome'}</p>
                    <span className="text-xs text-gray-400">{formatPhone(p.phone)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {label && (
                      <span className={['text-xs font-medium', label.className].join(' ')}>
                        {label.text}
                      </span>
                    )}
                    {!isSending && !isCheckingDelivery && !isDone && (
                      <button
                        onClick={() => handleRemovePatient(p.id)}
                        className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                      >
                        &times;
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Message template */}
        {results.length === 0 && (
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">
              Mensagem <span className="text-gray-300">({'{nome}'} = primeiro nome do paciente)</span>
            </label>
            <textarea
              value={messageTemplate}
              onChange={(e) => setMessageTemplate(e.target.value)}
              rows={5}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
            />
          </div>
        )}

        {/* Preview */}
        {results.length === 0 && (
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Preview</label>
            <div className="rounded-lg bg-emerald-50 border border-emerald-100 px-4 py-3 text-sm text-gray-700 whitespace-pre-line">
              {previewMessage}
            </div>
          </div>
        )}

        {/* Progress */}
        {isSending && (
          <div className="rounded-lg bg-brand-50 border border-brand-100 px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm font-medium text-brand-700">
                Enviando {progress.sent}/{progress.total}...
              </span>
            </div>
            <div className="w-full bg-brand-100 rounded-full h-1.5">
              <div
                className="bg-brand-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${(progress.sent / progress.total) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Delivery verification */}
        {!isSending && isCheckingDelivery && (
          <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-700">
                Verificando confirmações de entrega...
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Aguardando WhatsApp confirmar quais mensagens realmente chegaram.
            </p>
          </div>
        )}

        {/* Summary */}
        {isDone && (
          <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3 space-y-1">
            <p className="text-sm font-semibold text-gray-800">Envio concluído</p>
            <p className="text-sm text-emerald-600">
              {deliveredCount} entregue{deliveredCount !== 1 ? 's' : ''}
            </p>
            {unconfirmedCount > 0 && (
              <p className="text-sm text-amber-600">
                {unconfirmedCount} sem confirmação — o WhatsApp aceitou mas não confirmou entrega. Verifique com esses pacientes por outro canal.
              </p>
            )}
            {failedCount > 0 && (
              <p className="text-sm text-red-500">{failedCount} falha{failedCount !== 1 ? 's' : ''}</p>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={handleClose}>
            {isDone ? 'Fechar' : 'Cancelar'}
          </Button>
          {results.length === 0 && (
            <Button
              onClick={() => void handleSend()}
              loading={isSending}
              disabled={activePatients.length === 0 || !messageTemplate.trim()}
            >
              Enviar para {activePatients.length} paciente{activePatients.length !== 1 ? 's' : ''}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
