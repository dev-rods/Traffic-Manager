interface PrimeiraVisitaFieldProps {
  checked: boolean
  onChange: (valor: boolean) => void
}

/**
 * A marca de estreia, que pinta o agendamento de fúcsia na agenda.
 *
 * Pelo painel ela nasce SEMPRE desmarcada e só a recepção marca (decisão do
 * André em 09/09/2026). A contagem automática enxerga apenas os agendamentos
 * deste banco, e a clínica atende desde antes dele existir: ela anunciaria
 * "primeira vez" para cliente antiga, na frente dela. O bot continua decidindo
 * sozinho, porque atende quem chega da landing page sem ninguém por perto.
 */
export function PrimeiraVisitaField({ checked, onChange }: PrimeiraVisitaFieldProps) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-fuchsia-500 w-4 h-4"
      />
      <span className="text-sm text-gray-700">Primeira vez na clínica</span>
    </label>
  )
}
