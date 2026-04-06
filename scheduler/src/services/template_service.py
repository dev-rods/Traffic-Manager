import re
import logging
from typing import Any, Dict, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = {
    "WELCOME_NEW": "Olá! Seja {{bem_vindx}} à *{{clinic_name}}*!\n\nComo posso te ajudar hoje?",
    "WELCOME_RETURNING": "Olá, {{patient_name}}! {{Bem_vindx}} de volta à *{{clinic_name}}*!\n\nComo posso te ajudar?",
    "MAIN_MENU": "Escolha uma opção:",
    "SCHEDULE_MENU": "O que você gostaria de fazer?",
    "PRICE_TABLE": "{{price_table}}",
    "AVAILABLE_DAYS": "Selecione o dia para agendamento:",
    "SELECT_TIME": "Selecione o horário para {{date}}:",
    "SELECT_SERVICES": "Selecione o(s) serviço(s) desejado(s):\n\nVocê selecionou: {{selected_services}}\n\n_Digite \"voltar\" para retornar ou \"menu\" para o início._",
    "CONFIRM_SERVICES": "Serviços selecionados:\n{{selected_services}}\n\nDeseja confirmar?",
    "SELECT_AREAS": "Selecione as áreas de tratamento (digite os números separados por vírgula):\n\n{{areas_list}}\n\n_Digite \"voltar\" para retornar ou \"menu\" para o início._",
    "CONFIRM_AREAS": "Áreas selecionadas:\n{{selected_areas}}\n\nDeseja confirmar?",
    "ASK_FULL_NAME": "Ótimo! Para finalizar, por favor me informe seu *nome completo*:\n\n_Digite \"voltar\" para retornar ou \"menu\" para o início._",
    "CONFIRM_BOOKING": "Confirme seu agendamento:\n*{{full_name}}*\n{{date}} às {{time}}\n{{service}}\nÁreas: {{areas}}\nDuração prevista: {{duration}}\n*Valor: {{price}}*\n{{clinic_name}} - {{address}}",
    "BOOKED": "Agendamento confirmado!\nTe esperamos no dia {{date}} às {{time}}.\nDuração prevista: {{duration}}\n*Valor: {{price}}*",
    "RESCHEDULE_FOUND": "Encontramos seu agendamento:\n{{date}} às {{time}}\n{{service}}\n\nPara qual dia deseja remarcar?",
    "RESCHEDULE_NOT_FOUND": "Não encontramos um agendamento ativo para este número.",
    "RESCHEDULED": "Agendamento remarcado com sucesso!\nNova data: {{date}} às {{time}}",
    "FAQ_MENU": "Qual sua dúvida?",
    "HUMAN_HANDOFF": "Entendi! Vamos encaminhar sua mensagem para nossa equipe. Em breve alguém entrará em contato.",
    "ATTENDANT_SESSION_ENDED": "O atendimento foi encerrado. Como posso te ajudar?",
    "UNRECOGNIZED": "Desculpe, não entendi sua mensagem. O que deseja fazer?",
    "RESCHEDULE_SELECT_APPOINTMENT": "Você possui mais de um agendamento. Qual deseja remarcar?",
    "CANCEL_NOT_FOUND": "Não encontramos um agendamento ativo para este número.",
    "CANCEL_SELECT_APPOINTMENT": "Você possui mais de um agendamento. Qual deseja cancelar?",
    "CONFIRM_CANCEL": "Deseja cancelar este agendamento?\n{{date}} às {{time}}\n{{service}}",
    "CANCELLED": "Agendamento cancelado com sucesso.",
    "FAREWELL": "Obrigado pelo contato e tenha uma ótima semana! Até a próxima!",
    "RECOMMENDATIONS": "📋 *Recomendações importantes para sua sessão:*\n\n{{recommendations}}\n\nPor favor, confirme que leu e entendeu as recomendações acima.",
    "REMINDER_24H": "Lembrete: Amanhã às {{time}} você tem sessão na {{clinic_name}}. Responda OK para confirmar.",
    "AI_SYSTEM_PROMPT": """Você é a assistente virtual da {{clinic_display_name}}.
Você NÃO é especialista em nada. Você é apenas uma recepcionista simpática que
agenda sessões e responde dúvidas SOMENTE com o que está no sistema (tools).

Clínica: {{clinic_display_name}}
Endereço: {{clinic_address}}
Telefone: {{clinic_phone}}

DADOS JÁ COLETADOS:
{{collected_data_summary}}

{{single_service_hint}}

═══ REGRA FUNDAMENTAL ═══
Você NÃO SABE NADA sobre depilação, saúde, estética ou qualquer outro assunto.
Toda informação que você der ao cliente DEVE vir de uma tool.
Se nenhuma tool retornar a informação, chame request_human_handoff.
NUNCA invente, suponha ou use conhecimento geral.

═══ COMO CLASSIFICAR CADA MENSAGEM ═══
Leia a mensagem e escolha UMA ação:

(A) SAUDAÇÃO ("oi", "olá", "bom dia")
    → Responda: "Olá! Seja bem-vinda à {{clinic_display_name}} 😊 Como posso te ajudar?"

(B) QUER AGENDAR ("quero agendar", "marcar", "reservar", "sessão", "horário")
    → Siga o FLUXO DE AGENDAMENTO abaixo, uma etapa por vez.

(C) QUER REMARCAR ("remarcar", "trocar data", "mudar horário")
    → Chame lookup_appointments, depois siga o fluxo de remarcação.

(D) QUER CANCELAR ("cancelar", "desmarcar")
    → Chame lookup_appointments, depois siga o fluxo de cancelamento.

(E) DÚVIDA/PERGUNTA ("posso", "pode", "como funciona", "quanto custa", "dói",
    "é possível", "tem como", "qual", "o que", qualquer pergunta)
    → Primeiro, tente responder usando a BASE DE CONHECIMENTO (FAQ) que está no seu contexto.
    → Se a pergunta não está coberta exatamente, mas o FAQ tem informações relacionadas,
      use-as para formular uma resposta útil e natural.
    → Se precisar buscar algo mais específico, chame get_faq_answer com a pergunta.
    → Após responder, pergunte: "Posso te ajudar com mais alguma coisa?"
    → Só transfira para humano se REALMENTE não conseguir ajudar após tentar.

(F) NÃO ENTENDI (mensagem confusa, fora de contexto, ambígua)
    → Se é a PRIMEIRA vez: pergunte educadamente o que o cliente deseja.
    → Se é a SEGUNDA vez que não entende: responda EXATAMENTE:
      "Desculpe, não consegui entender sua solicitação. Vou te transferir
      para um dos nossos profissionais que poderá te atender. Aguarde um momento!"
      E chame request_human_handoff com reason="incompreensao".
    → NUNCA fique em ciclo — no máximo 1 tentativa de esclarecimento.

(G) QUER FALAR COM HUMANO ("atendente", "humano", "pessoa", "ajuda")
    → Chame request_human_handoff imediatamente.

═══ FLUXO DE AGENDAMENTO (uma etapa por vez) ═══
NUNCA pule etapas. NUNCA mostre áreas + datas + horários juntos.
Cada mensagem sua deve terminar com UMA pergunta.

  1. SERVIÇO → Se clínica tem 1 serviço, pule para etapa 2.
     Se tem vários, chame list_services → present_options.
     Pergunte: "Qual serviço você gostaria?"

  2. ÁREAS → Chame list_areas → present_options.
     Pergunte: "Quais áreas você gostaria de tratar?"
     Aguarde a resposta. Depois confirme:
     "Você selecionou [áreas]. Deseja prosseguir para escolher a data?"

  3. DATAS → Chame check_availability → present_options com datas formatadas.
     Se o paciente pediu uma data específica (ex: "hoje", "amanhã") e NÃO há disponibilidade,
     informe gentilmente e apresente as datas disponíveis mais próximas.
     Pergunte: "Qual data prefere?"

  4. HORÁRIOS → Chame get_time_slots → present_options com horários.
     Pergunte: "Qual horário prefere?"

  5. NOME → Se ainda não tem, pergunte: "Para finalizar, qual seu nome completo?"

  6. RESUMO → Mostre: áreas, data, horário, valor, nome.
     Pergunte: "Está tudo certo? Posso confirmar o agendamento?"

  7. CONFIRMAR → Chame book_appointment. Informe que está confirmado.

═══ REGRAS DE FORMATAÇÃO ═══
- NUNCA exponha IDs, UUIDs, JSON, nomes de tools ou dados internos.
- Datas: "segunda-feira, 3 de março" (nunca YYYY-MM-DD).
- Preços: "R$ 150,00" (vírgula decimal).
- Horários: "14:00" ou "14h".
- Negrito: *texto* (pontuação DENTRO dos asteriscos). Correto: *texto!* Errado: *texto*!
- NÃO use negrito com asteriscos duplos (**texto**) — WhatsApp usa asterisco simples.
- Use SEMPRE gênero neutro. Exemplos: "Seja bem-vindo(a)", "Você está interessado(a)", "Ficamos felizes em atendê-lo(a)". Nunca assuma o gênero do paciente.
- Termine TODA mensagem com uma pergunta (exceto confirmação final e handoff).
- Seja concisa — mensagens curtas.
- Use emojis com moderação (máx 1 por mensagem).
- Responda SEMPRE em português brasileiro.""",
}


class TemplateService:

    def __init__(self, db: PostgresService):
        self.db = db

    def get_template(self, clinic_id: str, template_key: str) -> Dict[str, Any]:
        try:
            results = self.db.execute_query(
                """
                SELECT template_key, content, buttons
                FROM scheduler.message_templates
                WHERE clinic_id = %s AND template_key = %s AND active = TRUE
                """,
                (clinic_id, template_key),
            )
            logger.info(f"[TemplateService] get_template results: {results}")
            if results:
                return results[0]
        except Exception as e:
            logger.warning(f"[TemplateService] Erro ao buscar template {template_key}: {e}")

        default_content = DEFAULT_TEMPLATES.get(template_key, "")
        return {"template_key": template_key, "content": default_content, "buttons": None}

    def render_template(self, template: Dict[str, Any], variables: Optional[Dict[str, str]] = None) -> str:
        content = template.get("content", "")

        if not variables:
            return content

        def replace_var(match):
            key = match.group(1).strip()
            value = variables.get(key, match.group(0))
            if value is None:
                return ""
            return str(value)

        return re.sub(r"\{\{(\w+)\}\}", replace_var, content)

    def get_and_render(self, clinic_id: str, template_key: str, variables: Optional[Dict[str, str]] = None) -> str:
        template = self.get_template(clinic_id, template_key)
        return self.render_template(template, variables)
