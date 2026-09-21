import type { PapelDoUsuario } from '@/types'

/**
 * O que cada papel enxerga no painel.
 *
 * Isto é conveniência, e não segurança. Quem autoriza de verdade é o servidor:
 * o funcionário tem um token válido na mão e pode chamar qualquer rota direto,
 * então esconder item de menu no React não fecha porta nenhuma. O backend nega
 * por padrão (`require_api_key`) e abre uma rota de cada vez
 * (`require_acesso`) - é lá que a decisão mora.
 *
 * O que esta lista resolve é o outro problema: oferecer ao funcionário uma tela
 * que vai responder 403. Um menu que leva a erro é pior do que um menu menor.
 */

/** Prefixos de rota liberados ao STAFF. A comparação é por começo do caminho. */
export const ROTAS_DO_STAFF = [
  '/agenda',
  // Cobre também /pacientes/:id/documentos, que é o prontuário.
  '/pacientes',
] as const

/** Para onde o STAFF vai quando entra, ou quando tenta uma rota fechada. */
export const ROTA_INICIAL_DO_STAFF = '/agenda'

export function podeVer(papel: PapelDoUsuario, caminho: string): boolean {
  if (papel === 'ADMIN') return true
  return ROTAS_DO_STAFF.some(
    (rota) => caminho === rota || caminho.startsWith(`${rota}/`),
  )
}

export function rotaInicial(papel: PapelDoUsuario): string {
  return papel === 'ADMIN' ? '/dashboard' : ROTA_INICIAL_DO_STAFF
}
