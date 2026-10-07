import logging

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import para_o_staff
from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.historico_de_sessao import (
    RegistroInvalido,
    aplicacoes_do_agendamento,
    grava_trilha,
    valida_aplicacoes,
)
from src.functions.patient_record._comum import (
    grava_aplicacoes,
    registro_com_aplicacoes,
    tipo_de_pele,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """POST /clinics/{clinicId}/patients/{patientId}/session-records

    Body:
    {
        "appointmentId": "uuid",        // opcional: traz data e areas prontas
        "sessionDate": "2026-09-17",    // obrigatorio se nao houver agendamento
        "professionalId": "uuid",       // opcional
        "tannedSkin": false,
        "notes": "...",
        "applications": [               // se omitido e houver agendamento,
            {                           // nasce do agendamento
                "areaId": "uuid", "areaName": "Axilas",
                "protocolAreaKey": "axilas", "method": "SHR",
                "fluenceJ": 7, "energyKj": 8, "stacks": null, "passes": null
            }
        ]
    }
    """
    try:
        identidade, erro = require_acesso(event, "prontuario.escrever")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        patient_id = extract_path_param(event, "patientId")
        if not clinic_id or not patient_id:
            return http_response(400, {"status": "ERROR",
                                       "message": "clinicId e patientId sao obrigatorios"})

        body = parse_body(event) or {}
        appointment_id = body.get("appointmentId")
        session_date = body.get("sessionDate")

        db = PostgresService()

        # A data vem do agendamento quando ha um: e a data do ATENDIMENTO, nao
        # a de digitacao, e digitar de novo o que o sistema ja sabe e onde o
        # erro entra.
        if appointment_id and not session_date:
            linhas = db.execute_query(
                """SELECT appointment_date FROM scheduler.appointments
                   WHERE id = %s::uuid AND clinic_id = %s""",
                (appointment_id, clinic_id),
            )
            if not linhas:
                return http_response(404, {"status": "ERROR",
                                           "message": "Agendamento nao encontrado"})
            session_date = str(linhas[0]["appointment_date"])

        if not session_date:
            return http_response(400, {"status": "ERROR",
                                       "message": "Informe a data da sessao ou um agendamento"})

        pele = tipo_de_pele(db, patient_id)

        if "applications" in body:
            aplicacoes = valida_aplicacoes(_do_corpo(body["applications"]))
        elif appointment_id:
            aplicacoes = valida_aplicacoes(
                aplicacoes_do_agendamento(db, appointment_id, pele))
        else:
            aplicacoes = []

        criado = db.execute_write_returning(
            """INSERT INTO scheduler.patient_session_records
               (clinic_id, patient_id, appointment_id, professional_id,
                session_date, tanned_skin, skin_type_snapshot, notes)
               VALUES (%s, %s::uuid, %s::uuid, %s::uuid, %s::date, %s, %s, %s)
               RETURNING *""",
            (clinic_id, patient_id, appointment_id or None,
             body.get("professionalId") or None, session_date,
             bool(body.get("tannedSkin")), pele,
             (body.get("notes") or "").strip() or None),
        )
        record_id = str(criado["id"])
        grava_aplicacoes(db, record_id, aplicacoes)

        registro = registro_com_aplicacoes(db, record_id)
        grava_trilha(db, record_id, clinic_id, "CREATE", registro,
                     body.get("changedBy"))

        logger.info(
            f"[Prontuario] registro criado: {record_id} paciente={patient_id} "
            f"sessao={session_date} aplicacoes={len(aplicacoes)}"
        )
        return http_response(201, para_o_staff(identidade, {"status": "SUCCESS", "record": registro}))

    except RegistroInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"[Prontuario] Erro ao criar registro: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})


def _do_corpo(aplicacoes):
    """camelCase do HTTP para snake_case do banco.

    A conversao fica num lugar so pelo mesmo motivo de duration_rules: um
    chamador novo que erre a grafia perde o campo EM SILENCIO - o par e
    descartado e ninguem levanta.
    """
    return [{
        "area_id": a.get("areaId"),
        "area_name": a.get("areaName"),
        "protocol_area_key": a.get("protocolAreaKey"),
        "method": a.get("method"),
        "fluence_j": a.get("fluenceJ"),
        "energy_kj": a.get("energyKj"),
        "stacks": a.get("stacks"),
        "passes": a.get("passes"),
        "display_order": a.get("displayOrder"),
    } for a in (aplicacoes or [])]
