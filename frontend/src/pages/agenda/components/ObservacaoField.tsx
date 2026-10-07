/** Limite do campo. O backend corta em 500; avisar antes evita perda silenciosa. */
export const MAX_OBSERVACAO = 500

interface ObservacaoFieldProps {
  value: string
  onChange: (texto: string) => void
}

/**
 * Observação curta do agendamento, visível no popover da agenda.
 *
 * A edição já tinha este campo; a criação não - a atendente marcava e só
 * conseguia anotar reabrindo depois. Extraído para componente em vez de
 * duplicado: dois textareas iguais divergem no primeiro ajuste de estilo, e
 * aqui eles precisam parecer o mesmo campo porque são.
 *
 * Três linhas de propósito. É para "veio pela indicação da Ana" ou "quer trocar
 * de sala", não para prontuário - isso mora no cadastro da paciente.
 */
export function ObservacaoField({ value, onChange }: ObservacaoFieldProps) {
  const restantes = MAX_OBSERVACAO - value.length

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label htmlFor="observacao" className="text-xs font-medium text-gray-500">
          Observações
        </label>
        {/* Só aparece perto do limite: contador permanente vira ruído num campo
            que quase sempre leva uma frase. */}
        {restantes <= 80 && (
          <span className={restantes < 0 ? 'text-xs text-red-500' : 'text-xs text-gray-400'}>
            {restantes} restantes
          </span>
        )}
      </div>
      <textarea
        id="observacao"
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, MAX_OBSERVACAO))}
        rows={3}
        maxLength={MAX_OBSERVACAO}
        placeholder="Ex: veio por indicação, prefere sala 2, alergia a..."
        className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
      />
    </div>
  )
}
