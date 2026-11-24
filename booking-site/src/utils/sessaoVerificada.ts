// O celular verificado pelo código nesta aba (PRD 061). O fluxo de agendamento
// e o "Meus agendamentos" compartilham a verificação: quem confirmou o código
// num lugar não digita outro no outro. `sessionStorage` morre com a aba, e o
// prazo aqui tem um minuto de folga sobre os 30 min do token no backend.
// Nunca `localStorage`: o token autoriza cancelar e remarcar.

const CHAVE = 'booking:verificada'
const VALIDADE_MS = 29 * 60 * 1000

export interface SessaoVerificada {
  phone: string // como a API recebe
  token: string
  expiraEm: number // epoch ms
}

export function guardaSessaoVerificada(phone: string, token: string, agora = Date.now()): SessaoVerificada {
  const sessao = { phone, token, expiraEm: agora + VALIDADE_MS }
  try {
    sessionStorage.setItem(CHAVE, JSON.stringify(sessao))
  } catch {
    // navegação privada ou storage bloqueado: a verificação vale só em memória
  }
  return sessao
}

export function leSessaoVerificada(agora = Date.now()): SessaoVerificada | null {
  try {
    const bruto = sessionStorage.getItem(CHAVE)
    if (!bruto) return null
    const sessao = JSON.parse(bruto) as Partial<SessaoVerificada>
    if (
      typeof sessao.phone !== 'string' ||
      typeof sessao.token !== 'string' ||
      typeof sessao.expiraEm !== 'number' ||
      sessao.expiraEm <= agora
    ) {
      limpaSessaoVerificada()
      return null
    }
    return { phone: sessao.phone, token: sessao.token, expiraEm: sessao.expiraEm }
  } catch {
    return null
  }
}

export function limpaSessaoVerificada() {
  try {
    sessionStorage.removeItem(CHAVE)
  } catch {
    // nada a limpar
  }
}

/** A sessão guardada vale para este celular? */
export function sessaoValeParaOCelular(
  sessao: SessaoVerificada | null,
  phone: string,
  agora = Date.now()
): sessao is SessaoVerificada {
  return sessao !== null && sessao.phone === phone && sessao.expiraEm > agora
}
