/**
 * O mesmo default do backend (template_service.DEFAULT_TEMPLATES, PRD 048).
 * Avisa dos DOIS códigos (entrar e assinar) para o link não parecer golpe.
 * Se mudar lá, mudar aqui.
 */
export const LINK_DOCUMENTOS_PADRAO =
  'Olá, {{nome}}! Sua sessão na {{clinic_name}} é {{dia}} às {{hora}}. ' +
  'Para agilizar o atendimento, confira seus dados, responda a ficha de saúde ' +
  'e assine o termo de consentimento pelo link: {{link}}\n' +
  'Leva uns 5 minutos. Você entra com este número de WhatsApp e um código que ' +
  'chega aqui; na hora de assinar, chega outro código.'

export const EXEMPLO_DO_LINK: Record<string, string> = {
  nome: 'Maria',
  clinic_name: 'sua clínica',
  dia: 'quarta, 03/12',
  hora: '10:00',
  link: 'https://documentos.suaclinica.com.br/sua-clinica/documentos',
}
