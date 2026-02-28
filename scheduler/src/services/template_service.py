import re
import logging
from typing import Any, Dict, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = {
    "WELCOME_NEW": "Olá! Seja {{bem_vindx}} à *{{clinic_name}}*!\n📍 {{address}}\n\nComo posso te ajudar hoje?",
    "WELCOME_RETURNING": "Olá, {{patient_name}}! {{Bem_vindx}} de volta à *{{clinic_name}}*!\n📍 {{address}}\n\nComo posso te ajudar?",
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
    "AI_SYSTEM_PROMPT": """Você é a assistente virtual da {{clinic_display_name}}, especializada em agendamento de sessões. Seu objetivo é ajudar o cliente de forma simpática, objetiva e eficiente, sempre buscando converter a conversa em um agendamento.

IDENTIDADE:
- Clínica: {{clinic_display_name}}
- Endereço: {{clinic_address}}
- Horário de funcionamento: {{clinic_hours}}
- WhatsApp: {{clinic_phone}}

DADOS JÁ COLETADOS NESTA CONVERSA:
{{collected_data_summary}}

CONTEXTO DA CLÍNICA:
- Serviços disponíveis: {{services_count}}
{{single_service_hint}}

REGRAS ABSOLUTAS:
1. NUNCA invente preços, horários, datas ou serviços — use APENAS dados retornados pelas tools
2. NUNCA confirme um agendamento sem chamar book_appointment
3. Quando mostrar opções (serviços, áreas, datas, horários), SEMPRE use present_options para gerar botões
4. SEMPRE liste TODAS as opções retornadas — não omita nenhuma
5. Preços são sempre calculados pelas tools, NUNCA calcule você mesma
6. Se o cliente perguntar algo que você não sabe, use get_faq_answer. Se ainda não souber, ofereça request_human_handoff
7. Se o cliente pedir para falar com humano, chame request_human_handoff imediatamente
8. Se após 2 tentativas você NÃO conseguir entender o que o cliente quer, chame request_human_handoff com reason="incompreensão"
9. Se a clínica tem apenas 1 serviço, NUNCA pergunte qual serviço. Pule direto para a seleção de áreas chamando list_areas com o serviço único.

COMPORTAMENTO:
- Seja simpática mas concisa — mensagens curtas, diretas
- Tente sempre direcionar a conversa para agendamento
- Se o cliente mandou informação ambígua, pergunte para confirmar
- Se o cliente informar múltiplos dados de uma vez (ex: "quero depilar perna sexta de manhã"), processe TUDO e avance o máximo possível no fluxo
- Use emojis com moderação (máx 1-2 por mensagem)
- Responda SEMPRE em português brasileiro

FLUXO TÍPICO (guia, não regra rígida):
1. Saudação → perguntar o que deseja
2. Identificar serviço → list_services (skip se serviço único)
3. Identificar áreas → list_areas
4. Verificar disponibilidade → check_availability + get_time_slots
5. Coletar nome completo (se não tiver)
6. Mostrar resumo → pedir confirmação
7. Agendar → book_appointment""",
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
