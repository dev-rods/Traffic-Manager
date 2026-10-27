import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useLembrarAgendaDoDia } from '@/hooks/useAppointments'
import type { LembretesDoDiaResponse } from '@/types'

interface LembrarAgendaDoDiaProps {
  dia: string
  disabled?: boolean
}

function horaLocal(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function plural(n: number, um: string, varios: string) {
  return n === 1 ? um : varios
}

/**
 * Botao com previa: primeiro conta, depois envia (PRD 027).
 *
 * A previa evita o clique duplo e diz a atendente o que o bot vai fazer se
 * alguem pedir para cancelar - com site, manda o link; sem site, resolve pela
 * conversa. Inline, sem modal: a decisao e pequena e reversivel so ate aqui.
 */
export function LembrarAgendaDoDia({ dia, disabled }: LembrarAgendaDoDiaProps) {
  const [previa, setPrevia] = useState<LembretesDoDiaResponse | null>(null)
  const [resultado, setResultado] = useState<LembretesDoDiaResponse | null>(null)
  const lembrar = useLembrarAgendaDoDia()

  const abrirPrevia = () =>
    lembrar.mutate({ dia, simular: true }, { onSuccess: (r) => { setPrevia(r); setResultado(null) } })
  const confirmar = () =>
    lembrar.mutate({ dia, simular: false }, { onSuccess: (r) => { setResultado(r); setPrevia(null) } })
  const fechar = () => { setPrevia(null); setResultado(null) }

  return (
    <div className="relative">
      <Button
        variant="secondary"
        onClick={abrirPrevia}
        disabled={disabled || lembrar.isPending}
        loading={lembrar.isPending && !previa}
      >
        Lembrar agenda do dia
      </Button>

      {lembrar.isError && (
        <p role="alert" className="absolute right-0 mt-2 w-72 text-sm text-red-600">
          Não foi possível preparar o lembrete. Tente de novo.
        </p>
      )}

      {previa && (
        <div
          role="dialog"
          aria-label="Confirmar lembrete"
          className="absolute right-0 z-20 mt-2 flex w-80 flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 text-sm shadow-lg"
        >
          <p className="text-gray-800">
            <strong>{previa.enfileirados}</strong> para lembrar
            {previa.ja_lembrados > 0 && <>, {previa.ja_lembrados} já {plural(previa.ja_lembrados, 'lembrado', 'lembrados')}</>}
            {previa.enfileirados_antes > 0 && <>, {previa.enfileirados_antes} a caminho</>}
            {previa.sem_telefone > 0 && <>, {previa.sem_telefone} sem telefone</>}.
          </p>
          <p className="text-gray-500">
            {previa.tem_link_de_autoatendimento
              ? 'Se alguém pedir para cancelar ou remarcar, o bot envia o link do site.'
              : 'Esta clínica não tem site: o bot cancela e remarca pela conversa.'}
          </p>
          {previa.adiados_para && (
            <p className="text-amber-700">Fora do horário: saem às {horaLocal(previa.adiados_para)}.</p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={fechar}>Cancelar</Button>
            <Button size="sm" onClick={confirmar} disabled={previa.enfileirados === 0} loading={lembrar.isPending}>
              Enviar para {previa.enfileirados}
            </Button>
          </div>
        </div>
      )}

      {resultado && (
        <p role="status" className="absolute right-0 mt-2 whitespace-nowrap text-sm text-emerald-700">
          {resultado.enfileirados} {plural(resultado.enfileirados, 'lembrete', 'lembretes')}
          {resultado.adiados_para ? ` saem às ${horaLocal(resultado.adiados_para)}` : ' a caminho'}.
          <button type="button" onClick={fechar} className="ml-2 cursor-pointer underline">ok</button>
        </p>
      )}
    </div>
  )
}
