/**
 * O mesmo default do backend (template_service.DEFAULT_TEMPLATES). Sem link e
 * sem "cancelar" ou "remarcar" de proposito: citar a saida planta a ideia
 * (PRD 027). Se mudar la, mudar aqui - o teste da pagina confere as palavras
 * proibidas.
 */
export const LEMBRETE_PADRAO =
  'Oi {{nome}}! Sua sessão de {{areas}} na {{clinic_name}} está confirmada para {{dia}} às {{hora}}. ' +
  'Já estamos preparando tudo para você. Lembre de raspar a área no dia e evitar sol até lá. Até breve! 😊'

export const EXEMPLO_DO_LEMBRETE: Record<string, string> = {
  nome: 'Maria',
  areas: 'Axilas e Virilha Completa',
  clinic_name: 'sua clínica',
  dia: 'sexta, 06/11',
  hora: '09:00',
  endereco: 'Rua Exemplo, 100 - Jardins',
}
