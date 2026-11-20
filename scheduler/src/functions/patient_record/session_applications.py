import logging

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import para_o_staff
from src.utils.http import http_response, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.historico_de_sessao import aplicacoes_do_agendamento
from src.functions.patient_record._comum import serializa, tipo_de_pele

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """GET /clinics/{clinicId}/appointments/{appointmentId}/session-applications

    As aplicacoes com que o registro de sessao nasce, montadas a partir das
    areas do agendamento pelo mapa do protocolo (PRD 051).

    Existe para a montagem ter UM lugar. Ate 19/11/2026 a tela montava por
    conta propria, casando nomes por string, e trocava o nome comercial pelo
    do protocolo: "Perna Completa" virava "Meia perna" no registro. Aqui o
    nome comercial fica em `area_name` e o protocolo vai em
    `protocol_area_name`, como subtitulo.

    Nao confere status do agendamento: quem grava (POST) e que recusa
    cancelado e falta. Aqui e so leitura.
    """
    try:
        identidade, erro = require_acesso(event, "prontuario.ler")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        appointment_id = extract_path_param(event, "appointmentId")
        if not clinic_id or not appointment_id:
            return http_response(400, {"status": "ERROR",
                                       "message": "clinicId e appointmentId sao obrigatorios"})

        db = PostgresService()
        linhas = db.execute_query(
            "SELECT patient_id FROM scheduler.appointments WHERE id = %s::uuid AND clinic_id = %s",
            (appointment_id, clinic_id),
        )
        if not linhas:
            return http_response(404, {"status": "ERROR",
                                       "message": "Agendamento nao encontrado"})

        patient_id = linhas[0].get("patient_id")
        pele = tipo_de_pele(db, str(patient_id)) if patient_id else None
        aplicacoes = aplicacoes_do_agendamento(db, appointment_id, pele)

        return http_response(200, para_o_staff(identidade, {
            "status": "SUCCESS",
            "skin_type": pele,
            "applications": [serializa(a) for a in aplicacoes],
        }))

    except Exception as e:
        logger.error(f"[Prontuario] Erro ao montar aplicacoes do agendamento {appointment_id}: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
