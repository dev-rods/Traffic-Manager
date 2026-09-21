import json
import logging
from datetime import datetime, date

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import dentro_da_janela, fora_da_janela, para_o_staff
from src.utils.http import parse_body, http_response, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.duracao_manual import DuracaoInvalida
from src.services.duracao_manual import valida as valida_duracao
from src.services.availability_engine import AvailabilityEngine

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    GET /clinics/{clinicId}/available-slots?date=YYYY-MM-DD&serviceId=UUID[&totalDuration=INT]

    Returns available time slots for a given clinic, date, and service.
    `totalDuration` e a duracao EFETIVA da sessao, em minutos - ja com piso,
    teto e passo aplicados pelo painel, ou a duracao que a recepcao fixou na
    mao. Quando vem, e usada COMO ESTA.
    """
    try:
        identidade, error_response = require_acesso(event, "agenda.ler")
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId is required"})

        date_param = extract_query_param(event, "date")
        service_id = extract_query_param(event, "serviceId")
        total_duration_param = extract_query_param(event, "totalDuration")

        if date_param and not dentro_da_janela(identidade, date_param):
            return fora_da_janela()

        if not date_param or not service_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "date and serviceId query parameters are required"
            })

        logger.info(f"[clinicId: {clinic_id}] Getting available slots for date={date_param}, serviceId={service_id}, totalDuration={total_duration_param}")

        db = PostgresService()
        engine = AvailabilityEngine(db)

        if total_duration_param:
            # A duracao chega PRONTA e e usada como esta.
            #
            # Ate 19/09/2026 esta linha reaplicava `duracao_da_sessao` por cima
            # do valor recebido, e uma sessao de 75 minutos fixada na mao virava
            # 50 no teto da clinica: a tela oferecia horarios de 50 minutos para
            # uma sessao de 75, e a paciente seguinte era marcada por cima.
            #
            # E o MESMO defeito que o reschedule tinha, no mesmo dia, pelo mesmo
            # motivo - a regra sendo reaplicada sobre um numero que ja passou
            # por ela. Ver duracao_manual e appointment_service.reschedule.
            duracao = valida_duracao(total_duration_param)
            slots = engine.get_available_slots_multi(clinic_id, date_param, duracao)
        else:
            slots = engine.get_available_slots(clinic_id, date_param, service_id)

        return http_response(200, para_o_staff(identidade, {
            "status": "SUCCESS",
            "clinicId": clinic_id,
            "date": date_param,
            "serviceId": service_id,
            "slots": slots,
            "totalSlots": len(slots),
        }))

    except DuracaoInvalida as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})

    except Exception as e:
        logger.error(f"Error getting available slots: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
