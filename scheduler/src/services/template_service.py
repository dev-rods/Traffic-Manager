import re
import logging
from typing import Any, Dict, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = {
    "WELCOME_NEW": "Ola! Seja bem-vinda a {{clinic_name}}! Como posso te ajudar hoje?",
    "WELCOME_RETURNING": "Ola, {{patient_name}}! Bem-vinda de volta a {{clinic_name}}! Como posso te ajudar?",
    "MAIN_MENU": "Escolha uma opcao:",
    "SCHEDULE_MENU": "O que voce gostaria de fazer?",
    "PRICE_TABLE": "{{price_table}}",
    "AVAILABLE_DAYS": "Dias disponiveis para agendamento:\n{{days_list}}",
    "SELECT_TIME": "Horarios disponiveis para {{date}}:\n{{times_list}}",
    "INPUT_AREAS": "Por favor, digite a(s) area(s) que deseja tratar.\nExemplo: Pernas e axilas",
    "CONFIRM_BOOKING": "Confirme seu agendamento:\n{{date}} as {{time}}\n{{service}}\n{{areas}}\n{{clinic_name}} - {{address}}",
    "BOOKED": "Agendamento confirmado!\nTe esperamos no dia {{date}} as {{time}}.\n\n{{pre_session_instructions}}",
    "RESCHEDULE_FOUND": "Encontramos seu agendamento:\n{{date}} as {{time}}\n{{service}}\n\nPara qual dia deseja remarcar?",
    "RESCHEDULE_NOT_FOUND": "Nao encontramos um agendamento ativo para este numero.",
    "RESCHEDULED": "Agendamento remarcado com sucesso!\nNova data: {{date}} as {{time}}",
    "FAQ_MENU": "Qual sua duvida?",
    "HUMAN_HANDOFF": "Entendi! Vamos encaminhar sua mensagem para nossa equipe. Entraremos em contato o mais rapido possivel dentro do horario comercial.",
    "UNRECOGNIZED": "Desculpe, nao entendi sua mensagem. O que deseja fazer?",
    "REMINDER_24H": "Lembrete: Amanha as {{time}} voce tem sessao na {{clinic_name}}. Responda OK para confirmar.",
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
            return str(variables.get(key, match.group(0)))

        return re.sub(r"\{\{(\w+)\}\}", replace_var, content)

    def get_and_render(self, clinic_id: str, template_key: str, variables: Optional[Dict[str, str]] = None) -> str:
        template = self.get_template(clinic_id, template_key)
        return self.render_template(template, variables)
