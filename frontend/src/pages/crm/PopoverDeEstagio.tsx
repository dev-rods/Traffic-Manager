import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useCorrigeEstagio } from '@/hooks/useLeads'
import type { Lead, LeadStage } from '@/types'
import { ESTAGIOS, ESTAGIOS_EDITAVEIS } from './estagios'

interface PopoverDeEstagioProps {
  lead: Lead
  onFechar: () => void
}

const CAMPO =
  'rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 bg-white min-h-11 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500'

/**
 * Correcao inline do estagio: sem modal, fecha com Escape, salva com MANUAL.
 *
 * Renderizado numa linha da tabela logo abaixo do lead, e nao como popover
 * absoluto: o contentor da tabela tem overflow-x e cortava o popover.
 */
export function PopoverDeEstagio({ lead, onFechar }: PopoverDeEstagioProps) {
  const [stage, setStage] = useState<LeadStage>(
    lead.stage && ESTAGIOS_EDITAVEIS.includes(lead.stage) ? lead.stage : 'EM_ANDAMENTO',
  )
  const [reason, setReason] = useState(lead.stage_reason ?? '')
  const corrige = useCorrigeEstagio()

  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [onFechar])

  const salvar = () => {
    corrige.mutate({ leadId: lead.id, stage, reason: reason.trim() || undefined }, { onSuccess: onFechar })
  }

  return (
    <div
      role="group"
      aria-label={`Corrigir estágio de ${lead.name ?? lead.phone}`}
      className="flex flex-wrap items-end gap-3 rounded-xl bg-brand-50/60 px-4 py-3"
    >
      <label className="flex flex-col gap-1 text-sm min-w-48">
        <span className="text-gray-600">Estágio</span>
        <select value={stage} onChange={(e) => setStage(e.target.value as LeadStage)} className={CAMPO}>
          {ESTAGIOS_EDITAVEIS.map((s) => (
            <option key={s} value={s}>
              {ESTAGIOS[s].label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm flex-1 min-w-64">
        <span className="text-gray-600">Motivo (opcional)</span>
        <input
          value={reason}
          maxLength={120}
          onChange={(e) => setReason(e.target.value)}
          placeholder="ex.: achou caro"
          className={CAMPO}
        />
      </label>
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={onFechar}>
          Cancelar
        </Button>
        <Button size="sm" loading={corrige.isPending} onClick={salvar}>
          Salvar
        </Button>
      </div>
      {corrige.isError && (
        <p className="basis-full text-sm text-red-600">Não foi possível salvar. Tente de novo.</p>
      )}
    </div>
  )
}
