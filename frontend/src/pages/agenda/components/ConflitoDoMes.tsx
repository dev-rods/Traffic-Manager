import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { formatCalendarDate } from '@/utils/formatDate'
import type { SessaoExistente } from '@/types'

interface ConflitoDoMesProps {
  existing: SessaoExistente
  /** A data e o horário do formulário. */
  novaData: string
  novaHora: string
  /** `criar`: a existente é cancelada e esta nasce. `mover`: a existente é cancelada e esta sessão é remarcada. */
  modo: 'criar' | 'mover'
  /** Só ADMIN vê "Manter as duas" (PRD 056, decisão 5). */
  ehAdmin: boolean
  loading?: boolean
  onConfirmar: () => void
  onManterAsDuas: (motivo: string) => void
  onVoltar: () => void
}

/**
 * Uma sessão por mês (PRD 056): o aviso inline do painel, no lugar dos botões
 * do formulário. "Confirmar" faz a troca (o `remarca` da 054: a sessão
 * existente sai com o desfecho da antecedência e esta nasce vinculada).
 * "Manter as duas" é a única exceção, de ADMIN, e exige motivo gravado.
 */
export function ConflitoDoMes({
  existing,
  novaData,
  novaHora,
  modo,
  ehAdmin,
  loading = false,
  onConfirmar,
  onManterAsDuas,
  onVoltar,
}: ConflitoDoMesProps) {
  const [mantendo, setMantendo] = useState(false)
  const [motivo, setMotivo] = useState('')
  const botao = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    botao.current?.focus()
  }, [])

  const nome = existing.patientName || 'A paciente'
  const quando = `${formatCalendarDate(existing.date)} às ${existing.time}`
  const para = `${formatCalendarDate(novaData)} às ${novaHora}`
  const pergunta = `${nome} já tem sessão em ${quando}.`
  const consequencia =
    modo === 'criar'
      ? `Ao confirmar, essa sessão será cancelada e remarcada para ${para}.`
      : `Ao confirmar, essa sessão será cancelada e esta será remarcada para ${para}.`

  return (
    <div
      role="group"
      aria-label={pergunta}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onVoltar()
        }
      }}
      className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm"
    >
      <p className="font-medium text-gray-900">{pergunta}</p>
      <p className="text-gray-700">{consequencia}</p>
      {existing.areas && <p className="text-xs text-gray-500">Áreas: {existing.areas}</p>}

      {mantendo ? (
        <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-3">
          <Input
            label="Motivo para manter as duas sessões"
            placeholder="Ex.: áreas tratadas em dias separados"
            value={motivo}
            maxLength={200}
            onChange={(e) => setMotivo(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button type="button" size="sm" variant="secondary" onClick={() => setMantendo(false)} disabled={loading}>
              Cancelar
            </Button>
            <Button
              type="button"
              size="sm"
              variant="danger"
              onClick={() => onManterAsDuas(motivo.trim())}
              disabled={!motivo.trim()}
              loading={loading}
            >
              Manter as duas
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-end gap-2">
          {ehAdmin && (
            <button
              type="button"
              onClick={() => setMantendo(true)}
              disabled={loading}
              className="mr-auto text-xs font-medium text-gray-500 underline-offset-2 hover:underline disabled:opacity-50"
            >
              Manter as duas
            </button>
          )}
          <Button type="button" size="sm" variant="secondary" onClick={onVoltar} disabled={loading}>
            Voltar
          </Button>
          <Button ref={botao} type="button" size="sm" onClick={onConfirmar} loading={loading}>
            Confirmar
          </Button>
        </div>
      )}
    </div>
  )
}
