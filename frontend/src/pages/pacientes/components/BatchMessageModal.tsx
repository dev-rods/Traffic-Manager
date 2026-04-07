import { useState, useMemo } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useSendBatchMessages } from '@/hooks/useMessages'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'
import type { SendMessagePayload } from '@/services/messages.service'

interface BatchMessageModalProps {
  open: boolean
  patients: PatientWithStats[]
  availableDates: string[]
  clinicTemplate?: string | null
  onClose: () => void
  onDone: () => void
}

export function buildDefaultMessage(availableDates: string[]): string {
  const datesText = availableDates.length > 0
    ? availableDates.map((d) => {
        const [, m, day] = d.split('-')
        return `${day}/${m}`
      }).join(', ')
    : 'em breve'

  return `Oi {nome}! Tudo bem?\n\nEstamos com novas datas disponíveis para agendamento: *${datesText}*.\n\nGostaria de agendar sua sessão? Responda aqui que te ajudamos!`
}

export function BatchMessageModal({ open, patients, availableDates, clinicTemplate, onClose, onDone }: BatchMessageModalProps) {
  const [messageTemplate, setMessageTemplate] = useState(() =>
    clinicTemplate?.trim() ? clinicTemplate : buildDefaultMessage(availableDates),
  )
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set())
  const { send, results, isSending, progress, reset } = useSendBatchMessages()

  const activePatients = useMemo(
    () => patients.filter((p) => !removedIds.has(p.id)),
    [patients, removedIds],
  )

  const isDone = results.length > 0 && !isSending

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

  const sentCount = results.filter((r) => r.status === 'sent' || r.status === 'queued').length
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
              return (
                <div key={p.id} className="flex items-center justify-between px-3 py-2">
                  <div className="flex items-center gap-2">
                    <p className="text-sm text-gray-800">{p.name ?? 'Sem nome'}</p>
                    <span className="text-xs text-gray-400">{formatPhone(p.phone)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {result && (
                      <span className={[
                        'text-xs font-medium',
                        result.status === 'sent' || result.status === 'queued'
                          ? 'text-emerald-600'
                          : result.status === 'failed'
                            ? 'text-red-500'
                            : 'text-gray-400',
                      ].join(' ')}>
                        {result.status === 'sent' || result.status === 'queued' ? 'Enviado' : result.status === 'failed' ? 'Falhou' : '...'}
                      </span>
                    )}
                    {!isSending && !isDone && (
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
        {!isDone && (
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">
              Mensagem <span className="text-gray-300">({'{nome}'} = primeiro nome do paciente)</span>
            </label>
            <textarea
              value={messageTemplate}
              onChange={(e) => setMessageTemplate(e.target.value)}
              rows={5}
              disabled={isSending}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
            />
          </div>
        )}

        {/* Preview */}
        {!isDone && (
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

        {/* Summary */}
        {isDone && (
          <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3 space-y-1">
            <p className="text-sm font-semibold text-gray-800">Envio concluído</p>
            <p className="text-sm text-emerald-600">{sentCount} mensagen{sentCount !== 1 ? 's' : ''} enviada{sentCount !== 1 ? 's' : ''}</p>
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
          {!isDone && (
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
