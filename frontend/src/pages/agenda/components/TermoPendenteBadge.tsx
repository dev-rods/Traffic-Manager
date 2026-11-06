import type { Appointment } from '@/types'
import { situacaoDoTermo } from '@/utils/termo'

/**
 * "DOCS" ao lado do nome quando falta o documento do check-in, termo e ficha
 * de anamnese num só (PRD 036 e 038):
 * a recepção vê de longe quem ainda vai assinar no iPad. Mesmo molde do
 * `ConfirmacaoBadge`. Some quando assinado, em papel, dispensado, ou quando a
 * clínica não tem versão do termo configurada.
 */
export function TermoPendenteBadge({ appointment: a, compacto = false }: { appointment: Appointment; compacto?: boolean }) {
  const situacao = situacaoDoTermo(a)
  if (!situacao.pendente) return null
  return (
    <span
      title={situacao.label === 'Pendente' ? 'Termo e anamnese pendentes' : situacao.label}
      className={[
        'inline-block rounded px-1 font-bold align-middle bg-amber-100 text-amber-700',
        compacto ? 'text-[10px] mr-0.5' : 'px-1.5 py-0.5 text-[10px]',
      ].join(' ')}
    >
      DOCS
    </span>
  )
}
