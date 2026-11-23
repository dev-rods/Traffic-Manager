/**
 * O site de autoatendimento da clínica, visto do painel (PRD 060).
 *
 * Espelha `scheduler/src/services/autoatendimento.py`: a raiz do domínio
 * próprio é o link para MARCAR; `?meus=1` abre "Meus agendamentos" direto,
 * para remarcar ou cancelar. É este segundo que a recepção manda quando a
 * paciente pede para mexer numa sessão: em 23/11/2026 o link raiz levou uma
 * paciente a criar uma sessão nova em vez de remarcar, e outra a não achar
 * onde cancelar.
 */
export const PARAMETRO_MEUS_AGENDAMENTOS = 'meus=1'

export function linkDoSite(customDomain: string | null | undefined): string | null {
  const dominio = (customDomain ?? '').trim().replace(/^https?:\/\//, '').replace(/\/+$/, '')
  return dominio ? `https://${dominio}/` : null
}

export function linkDeMeusAgendamentos(customDomain: string | null | undefined): string | null {
  const base = linkDoSite(customDomain)
  return base ? `${base}?${PARAMETRO_MEUS_AGENDAMENTOS}` : null
}
