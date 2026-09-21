import type { PapelDoUsuario, PermissoesDoUsuario } from '@/types'

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

export interface AcessoDoUsuario {
  papel: PapelDoUsuario
  permissoes: PermissoesDoUsuario
}

function casa(caminho: string, rota: string): boolean {
  return caminho === rota || caminho.startsWith(`${rota}/`)
}

export function podeVer(acesso: AcessoDoUsuario, caminho: string): boolean {
  if (acesso.papel === 'ADMIN') return true

  if (!ROTAS_DO_STAFF.some((rota) => casa(caminho, rota))) return false

  /**
   * A lista de pacientes é um interruptor à parte.
   *
   * Importa o `===`: só a LISTA é fechada. O prontuário
   * (`/pacientes/:id/documentos`) continua aberto, porque ela chega nele pelo
   * atalho da agenda e precisa dele para registrar a sessão. Usar `casa()`
   * aqui trancaria a funcionária fora do próprio trabalho.
   */
  if (caminho === '/pacientes' && !acesso.permissoes.see_patient_list) {
    return false
  }

  return true
}

export function rotaInicial(papel: PapelDoUsuario): string {
  return papel === 'ADMIN' ? '/dashboard' : ROTA_INICIAL_DO_STAFF
}
