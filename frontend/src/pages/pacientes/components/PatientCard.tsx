import { Link } from 'react-router-dom'
import { WhatsAppIcon, PauseIcon, PlayIcon, TrashIcon, DocumentIcon } from '@/components/ui/Icons'
import { formatDate } from '@/utils/formatDate'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

interface PatientCardProps {
  patient: PatientWithStats
  selected: boolean
  paused: boolean
  pauseLoading?: boolean
  onSelect: (patient: PatientWithStats) => void
  onToggleSelect: (patient: PatientWithStats) => void
  onWhatsApp: (patient: PatientWithStats) => void
  onPauseBot: (phone: string) => void
  onDelete: (patient: PatientWithStats) => void
}

/**
 * Um paciente em celular.
 *
 * A tabela tem nove colunas. Em 375px ela só existe dentro de um
 * `overflow-x-auto`, e rolar na horizontal para ler uma linha é o tipo de
 * gesto que ninguém faz duas vezes - a informação existe e não é lida.
 *
 * O card empilha o que a linha espalhava: identidade em cima, números da
 * relação embaixo, ações numa régua própria com alvo de 44px.
 *
 * **Valor gasto não aparece aqui.** A recepção pode estar com o interruptor de
 * preço desligado, e nesse caso o campo nem chega do servidor; mostrar um
 * espaço vazio seria pior que não mostrar. Quem precisa do total abre no
 * desktop.
 */
export function PatientCard({
  patient: p,
  selected,
  paused,
  pauseLoading,
  onSelect,
  onToggleSelect,
  onWhatsApp,
  onPauseBot,
  onDelete,
}: PatientCardProps) {
  return (
    <li className="flex gap-3 px-3 py-3">
      <label className="flex h-11 w-6 flex-shrink-0 items-center justify-center cursor-pointer">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(p)}
          aria-label={`Selecionar ${p.name ?? 'paciente'}`}
          className="accent-brand-500"
        />
      </label>

      <div className="min-w-0 flex-1">
        <button
          type="button"
          onClick={() => onSelect(p)}
          className="block w-full text-left"
        >
          <span className="flex items-center gap-2">
            <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
              {(p.name ?? '?')[0].toUpperCase()}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-medium text-gray-800">
                {p.name ?? 'Sem nome'}
              </span>
              <span className="block text-xs text-gray-500">{formatPhone(p.phone)}</span>
            </span>
          </span>

          <span className="mt-1.5 block text-xs leading-relaxed text-gray-500">
            {p.total_visits} {p.total_visits === 1 ? 'visita' : 'visitas'}
            {p.last_visit && <> · última {formatDate(p.last_visit)}</>}
          </span>
          {p.next_visit && (
            <span className="mt-1 inline-block rounded bg-brand-50 px-1.5 py-0.5 text-[11px] font-medium text-brand-700">
              próxima {formatDate(p.next_visit)}
            </span>
          )}
        </button>

        {/* WhatsApp, prontuário e pausar bot ficam a um toque: são o uso do
            dia a dia. Excluir vai para a ponta, separado por `ml-auto` - um
            destrutivo colado nos demais é toque errado esperando acontecer. */}
        <div className="mt-2 flex items-center gap-1">
          <AcaoDoCard
            onClick={() => onWhatsApp(p)}
            label="Enviar mensagem no WhatsApp"
            className="text-emerald-600 hover:bg-emerald-50"
          >
            <WhatsAppIcon className="h-[18px] w-[18px]" />
          </AcaoDoCard>

          <AcaoDoCard
            onClick={() => onPauseBot(p.phone)}
            disabled={pauseLoading}
            pressed={paused}
            label={paused ? 'Retomar bot' : 'Pausar bot'}
            className={paused ? 'bg-amber-50 text-amber-600' : 'text-gray-500 hover:bg-gray-100'}
          >
            {paused ? <PlayIcon className="h-[18px] w-[18px]" /> : <PauseIcon className="h-[18px] w-[18px]" />}
          </AcaoDoCard>

          <Link
            to={`/pacientes/${p.id}/documentos`}
            aria-label="Documentos do paciente"
            className="flex h-11 w-11 items-center justify-center rounded-lg text-gray-500 transition-colors hover:bg-brand-50 hover:text-brand-600"
          >
            <DocumentIcon className="h-[18px] w-[18px]" />
          </Link>

          <AcaoDoCard
            onClick={() => onDelete(p)}
            label="Excluir paciente"
            className="ml-auto text-gray-400 hover:bg-red-50 hover:text-red-600"
          >
            <TrashIcon className="h-[18px] w-[18px]" />
          </AcaoDoCard>
        </div>
      </div>
    </li>
  )
}

function AcaoDoCard({
  onClick,
  label,
  className,
  disabled,
  pressed,
  children,
}: {
  onClick: () => void
  label: string
  className: string
  disabled?: boolean
  pressed?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={pressed}
      className={[
        // 44px: a régua de toque do CLAUDE.md. Os 36px da tabela foram feitos
        // para o mouse.
        'flex h-11 w-11 items-center justify-center rounded-lg transition-colors',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
        className,
      ].join(' ')}
    >
      {children}
    </button>
  )
}
