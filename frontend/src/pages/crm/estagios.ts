import type { LeadStage, StageSource } from '@/types'

/**
 * Rotulos, ordem e regras de edicao da fila do CRM (PRD 057).
 *
 * Espelha `estagio_do_lead.py`: ORDEM_DA_FILA, ESTAGIOS_DA_AGENDA e
 * ESTAGIOS_EDITAVEIS. O backend e quem decide (o PATCH recusa fato da agenda);
 * aqui a lista so evita oferecer uma opcao que voltaria 400.
 */
export interface EstagioInfo {
  label: string
  descricao: string
  variant: 'success' | 'warning' | 'danger' | 'neutral' | 'info'
}

export const ESTAGIOS: Record<LeadStage, EstagioInfo> = {
  AGUARDANDO_NOS: { label: 'Aguardando nós', descricao: 'A última mensagem é do lead.', variant: 'danger' },
  SUMIU: { label: 'Sumiu', descricao: 'A conversa parou há mais de N dias.', variant: 'warning' },
  INICIADA_SEM_RESPOSTA: { label: 'Sem resposta', descricao: 'Só nós falamos, há poucos dias.', variant: 'warning' },
  SEM_CONVERSA: { label: 'Sem conversa', descricao: 'Ninguém falou ainda.', variant: 'neutral' },
  EM_ANDAMENTO: { label: 'Em andamento', descricao: 'Conversa viva, sem decisão.', variant: 'info' },
  NAO_AGENDOU: { label: 'Não agendou', descricao: 'Decidiu não agendar.', variant: 'neutral' },
  CANCELOU: { label: 'Cancelou', descricao: 'O último agendamento foi cancelado e não voltou a escrever.', variant: 'warning' },
  FALTOU: { label: 'Faltou', descricao: 'Não compareceu e não voltou a escrever.', variant: 'danger' },
  AGENDOU: { label: 'Agendou', descricao: 'Tem agendamento confirmado ou sessão feita.', variant: 'success' },
  NAO_E_LEAD: { label: 'Não é lead', descricao: 'Fornecedor, pessoal, spam.', variant: 'neutral' },
}

/** Ordem de trabalho da fila: quem precisa de ação primeiro. */
export const ORDEM_DA_FILA: LeadStage[] = [
  'AGUARDANDO_NOS', 'SUMIU', 'INICIADA_SEM_RESPOSTA', 'SEM_CONVERSA', 'EM_ANDAMENTO',
  'NAO_AGENDOU', 'CANCELOU', 'FALTOU', 'AGENDOU',
]

/** Fato da agenda: vem da agenda, não se edita. */
export const ESTAGIOS_DA_AGENDA: LeadStage[] = ['AGENDOU', 'CANCELOU', 'FALTOU']

/** O que a atendente pode escolher. */
export const ESTAGIOS_EDITAVEIS: LeadStage[] = [
  'AGUARDANDO_NOS', 'SUMIU', 'INICIADA_SEM_RESPOSTA', 'SEM_CONVERSA', 'EM_ANDAMENTO', 'NAO_AGENDOU', 'NAO_E_LEAD',
]

export const FONTE_LABEL: Record<StageSource, string> = {
  REGRA: 'Pelas mensagens',
  MODELO: 'Sugerido pelo modelo',
  MANUAL: 'Corrigido pela equipe',
  HISTORICO: 'Conversa antiga, sem transcrição',
}

export const ORIGENS = [
  { value: 'landing-page', label: 'Site' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'harmonizacao', label: 'Harmonização' },
  { value: 'painel', label: 'Painel' },
] as const

export function rotuloDaOrigem(source: string): string {
  return ORIGENS.find((o) => o.value === source)?.label ?? source
}
