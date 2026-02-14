import re
import logging
from typing import Any, Dict, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = {
    "WELCOME_NEW": "Olá! Seja {{bem_vindx}} à {{clinic_name}}! Como posso te ajudar hoje?",
    "WELCOME_RETURNING": "Olá, {{patient_name}}! {{Bem_vindx}} de volta à {{clinic_name}}! Como posso te ajudar?",
    "MAIN_MENU": "Escolha uma opção:",
    "SCHEDULE_MENU": "O que você gostaria de fazer?",
    "PRICE_TABLE": "{{price_table}}",
    "AVAILABLE_DAYS": "Dias disponíveis para agendamento:\n{{days_list}}",
    "SELECT_TIME": "Horários disponíveis para {{date}}:\n{{times_list}}",
    "SELECT_SERVICES": "Selecione o(s) serviço(s) desejado(s):\n\nVocê selecionou: {{selected_services}}",
    "CONFIRM_SERVICES": "Serviços selecionados:\n{{selected_services}}\n\nDeseja confirmar?",
    "SELECT_AREAS": "Selecione as áreas de tratamento (digite os números separados por vírgula):\n\n{{areas_list}}",
    "CONFIRM_AREAS": "Áreas selecionadas:\n{{selected_areas}}\n\nDeseja confirmar?",
    "CONFIRM_BOOKING": "Confirme seu agendamento:\n{{date}} às {{time}}\n{{service}}\nÁreas: {{areas}}\nDuração prevista: {{duration}}\n{{clinic_name}} - {{address}}",
    "BOOKED": "Agendamento confirmado!\nTe esperamos no dia {{date}} às {{time}}.\nDuração prevista: {{duration}}\n\n{{pre_session_instructions}}",
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
    "REMINDER_24H": "Lembrete: Amanhã às {{time}} você tem sessão na {{clinic_name}}. Responda OK para confirmar.",
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
