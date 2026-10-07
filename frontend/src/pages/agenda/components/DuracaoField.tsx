/**
 * Faixa de sanidade da duração manual.
 *
 * Espelha MINIMO/MAXIMO em scheduler/src/services/duracao_manual.py. Quem
 * decide é o backend; isto aqui é para a atendente descobrir o erro digitando,
 * não depois de salvar.
 */
export const DURACAO_MANUAL = { minimo: 5, maximo: 480 } as const

interface DuracaoFieldProps {
  /** O que a regra da clínica calcula para as áreas escolhidas. */
  calculada?: number
  /** O que uma pessoa fixou. `null` = seguindo o cálculo. */
  manual: number | null
  onChange: (minutos: number | null) => void
  /** Aviso de que o override foi descartado porque as áreas mudaram. */
  avisoDeDescarte?: boolean
  disabled?: boolean
}

/**
 * A duração da sessão, com a opção de fixar um valor diferente do calculado.
 *
 * O cálculo (soma das áreas, com piso/teto/passo da clínica) acerta quase
 * sempre e é o padrão. O que ele não sabe é o que só a recepção sabe: a
 * paciente que sempre demora mais, a sessão que vai acumular duas coisas, o dia
 * em que a sala precisa de folga.
 *
 * O valor fixado vale SÓ para este agendamento - a regra da clínica não é
 * tocada. O texto diz isso em voz alta de propósito: quem mexe aqui está
 * resolvendo um caso, e achar que mudou a regra de todo mundo seria o erro caro.
 * Para mudar a regra existe a tela de Duração.
 */
export function DuracaoField({
  calculada,
  manual,
  onChange,
  avisoDeDescarte = false,
  disabled = false,
}: DuracaoFieldProps) {
  const fixada = manual !== null
  const foraDaFaixa =
    fixada && (manual < DURACAO_MANUAL.minimo || manual > DURACAO_MANUAL.maximo)

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label htmlFor="duracao" className="text-xs font-medium text-gray-500">
          Duração
        </label>
        {fixada ? (
          <button
            type="button"
            onClick={() => onChange(null)}
            disabled={disabled}
            className="text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
          >
            Voltar ao cálculo
          </button>
        ) : (
          calculada !== undefined && (
            <button
              type="button"
              onClick={() => onChange(calculada)}
              disabled={disabled}
              className="text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
            >
              Ajustar
            </button>
          )
        )}
      </div>

      {fixada ? (
        <>
          <div className="flex items-center gap-2">
            <input
              id="duracao"
              type="number"
              inputMode="numeric"
              value={manual}
              min={DURACAO_MANUAL.minimo}
              max={DURACAO_MANUAL.maximo}
              disabled={disabled}
              onChange={(e) => {
                const v = e.target.value
                onChange(v === '' ? null : Number(v))
              }}
              className="w-24 rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
            <span className="text-sm text-gray-500">minutos</span>
          </div>
          {foraDaFaixa ? (
            <p className="mt-1.5 text-xs text-red-500">
              A duração precisa estar entre {DURACAO_MANUAL.minimo} e{' '}
              {DURACAO_MANUAL.maximo} minutos.
            </p>
          ) : (
            <p className="mt-1.5 text-xs text-gray-400">
              {calculada !== undefined && <>A regra calcula {calculada} min. </>}
              Vale só para este agendamento.
            </p>
          )}
        </>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
          <span className="text-sm text-gray-800">
            {calculada !== undefined ? `${calculada} minutos` : '—'}
          </span>
          <span className="ml-2 text-xs text-gray-400">calculada pelas áreas</span>
        </div>
      )}

      {/* Sem isto o valor fixado some e a atendente não entende por quê. */}
      {avisoDeDescarte && (
        <p className="mt-1.5 text-xs text-amber-600">
          A duração fixada foi descartada porque as áreas mudaram.
        </p>
      )}
    </div>
  )
}
