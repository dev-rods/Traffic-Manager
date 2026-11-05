import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useToast } from '@/components/ui/toastContext'
import { useDispensarTermo, useRegistrarPapel } from '@/hooks/useConsents'
import { MOTIVO_DA_DISPENSA, situacaoDoTermo } from '@/utils/termo'
import type { Appointment, ConsentWaiveReason } from '@/types'

const TOM = {
  ok: 'text-emerald-600',
  atencao: 'text-amber-600',
  pendente: 'text-amber-600',
  nada: 'text-gray-500',
} as const

const MOTIVOS = Object.keys(MOTIVO_DA_DISPENSA) as ConsentWaiveReason[]

function hoje(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function mensagemDe(erro: unknown): string | undefined {
  return (erro as { response?: { data?: { message?: string } } })?.response?.data?.message
}

interface TermoDoAgendamentoProps {
  appointment: Appointment
}

/**
 * Termo de consentimento (PRD 036) no detalhe do agendamento.
 *
 * O iPad não deixa pular o termo; quem libera a sessão sem ele é a recepção,
 * aqui: "Dispensar nesta sessão" (a próxima pede de novo) ou "Assinado em
 * papel" (vale como vigente). Os dois exigem `agenda.escrever` no servidor.
 * Só aparece quando a clínica tem uma versão do termo configurada.
 */
export function TermoDoAgendamento({ appointment: a }: TermoDoAgendamentoProps) {
  const dispensar = useDispensarTermo()
  const papel = useRegistrarPapel()
  const { showToast } = useToast()
  const [modal, setModal] = useState<'dispensa' | 'papel' | null>(null)
  const [motivo, setMotivo] = useState<ConsentWaiveReason>('SEM_CELULAR')
  const [nota, setNota] = useState('')
  const [assinadoEm, setAssinadoEm] = useState(hoje)

  if (!a.consent_enabled) return null

  // O popover guarda o agendamento de quando foi aberto; depois da ação, o
  // estado novo vem da própria resposta, sem esperar a agenda recarregar.
  const situacao = papel.isSuccess
    ? { label: 'Em papel', tom: 'ok' as const, pendente: false }
    : dispensar.isSuccess
      ? { label: 'Dispensado nesta sessão', tom: 'atencao' as const, pendente: false }
      : situacaoDoTermo(a)

  function fechar() {
    setModal(null)
    setNota('')
  }

  function confirmarDispensa() {
    dispensar.mutate(
      { appointmentId: a.id, reason: motivo, note: motivo === 'OUTRO' ? nota.trim() : undefined },
      {
        onSuccess: () => {
          fechar()
          showToast({ message: 'Termo dispensado nesta sessão' })
        },
        onError: (erro) =>
          showToast({
            message: mensagemDe(erro) ?? 'Não foi possível dispensar o termo.',
            variant: 'error',
          }),
      }
    )
  }

  function confirmarPapel() {
    if (!a.patient_id) return
    papel.mutate(
      { patientId: a.patient_id, signedAt: assinadoEm },
      {
        onSuccess: () => {
          fechar()
          showToast({ message: 'Termo em papel registrado' })
        },
        onError: (erro) =>
          showToast({
            message: mensagemDe(erro) ?? 'Não foi possível registrar o termo.',
            variant: 'error',
          }),
      }
    )
  }

  return (
    <div className="px-4 pb-3 space-y-1.5 text-sm">
      <div className="flex justify-between gap-3">
        <span className="text-gray-400">Termo</span>
        <span className={`font-medium text-right ${TOM[situacao.tom]}`}>{situacao.label}</span>
      </div>

      {situacao.pendente && (
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={() => setModal('dispensa')}
            className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 cursor-pointer"
          >
            Dispensar nesta sessão
          </button>
          <button
            type="button"
            onClick={() => setModal('papel')}
            disabled={!a.patient_id}
            className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50 cursor-pointer"
          >
            Assinado em papel
          </button>
        </div>
      )}

      <Modal open={modal === 'dispensa'} onClose={fechar} title="Dispensar o termo nesta sessão" width="sm">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            A sessão segue sem o termo assinado. Na próxima, o iPad pede de novo.
          </p>
          <div>
            <label htmlFor="motivo-da-dispensa" className="text-xs font-medium text-gray-500 block mb-1.5">
              Motivo
            </label>
            <select
              id="motivo-da-dispensa"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value as ConsentWaiveReason)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            >
              {MOTIVOS.map((m) => (
                <option key={m} value={m}>
                  {MOTIVO_DA_DISPENSA[m]}
                </option>
              ))}
            </select>
          </div>
          {motivo === 'OUTRO' && (
            <div>
              <label htmlFor="nota-da-dispensa" className="text-xs font-medium text-gray-500 block mb-1.5">
                Descreva o motivo
              </label>
              <input
                id="nota-da-dispensa"
                type="text"
                value={nota}
                maxLength={200}
                onChange={(e) => setNota(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={fechar}>
              Cancelar
            </Button>
            <Button
              onClick={confirmarDispensa}
              loading={dispensar.isPending}
              disabled={motivo === 'OUTRO' && !nota.trim()}
            >
              Dispensar
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={modal === 'papel'} onClose={fechar} title="Termo assinado em papel" width="sm">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Guarde o papel na pasta da paciente. Aqui fica só o registro, sem PDF.
          </p>
          <div>
            <label htmlFor="data-do-papel" className="text-xs font-medium text-gray-500 block mb-1.5">
              Assinado em
            </label>
            <input
              id="data-do-papel"
              type="date"
              value={assinadoEm}
              max={hoje()}
              onChange={(e) => setAssinadoEm(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={fechar}>
              Cancelar
            </Button>
            <Button onClick={confirmarPapel} loading={papel.isPending} disabled={!assinadoEm}>
              Registrar
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
