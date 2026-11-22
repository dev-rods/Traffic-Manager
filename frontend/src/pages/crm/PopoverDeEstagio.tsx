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

/** Correcao inline do estagio: sem modal, fecha com Escape, salva com MANUAL. */
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
      role="dialog"
      aria-label="Corrigir estágio"
      className="absolute left-0 top-full z-20 mt-2 w-72 rounded-xl border border-gray-200 bg-white p-4 shadow-lg flex flex-col gap-3"
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-gray-600">Estágio</span>
        <select value={stage} onChange={(e) => setStage(e.target.value as LeadStage)} className={CAMPO}>
          {ESTAGIOS_EDITAVEIS.map((s) => (
            <option key={s} value={s}>
              {ESTAGIOS[s].label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-gray-600">Motivo (opcional)</span>
        <input
          value={reason}
          maxLength={120}
          onChange={(e) => setReason(e.target.value)}
          placeholder="ex.: achou caro"
          className={CAMPO}
        />
      </label>
      {corrige.isError && <p className="text-sm text-red-600">Não foi possível salvar. Tente de novo.</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onFechar}>
          Cancelar
        </Button>
        <Button size="sm" loading={corrige.isPending} onClick={salvar}>
          Salvar
        </Button>
      </div>
    </div>
  )
}
