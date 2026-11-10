import { Badge } from '@/components/ui/Badge'
import { semTermo } from '@/utils/termo'
import type { ConsentStatus } from '@/types'

interface SeloSemTermoProps {
  /** A clínica tem versão do termo configurada; sem ela nada é pendente. */
  consentEnabled: boolean
  status: ConsentStatus | null | undefined
}

/**
 * "Sem termo" ao lado do nome (PRD 047, §7.3 A).
 *
 * Só o negativo: quem está em dia não ganha selo, senão a lista vira um mural
 * de rótulos e o aviso some justo onde importa. Mesmo molde do
 * `SeloSilenciado`.
 */
export function SeloSemTermo({ consentEnabled, status }: SeloSemTermoProps) {
  if (!semTermo(consentEnabled, status)) return null

  return (
    <span title="Termo e anamnese sem assinatura vigente">
      <Badge variant="warning">Sem termo</Badge>
    </span>
  )
}
