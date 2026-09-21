import logging

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import para_o_staff
from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.functions.patient_record._comum import serializa

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """GET /clinics/{clinicId}/patients/{patientId}/session-records

    Devolve os registros em ordem decrescente, com as aplicacoes embutidas, e
    tambem os agendamentos do paciente que AINDA NAO tem registro - e o que a
    tela oferece em "de qual sessao?", e o que evita a sessao duplicada.
    """
    try:
        identidade, erro = require_acesso(event, "prontuario.ler")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        patient_id = extract_path_param(event, "patientId")
        if not clinic_id or not patient_id:
            return http_response(400, {"status": "ERROR",
                                       "message": "clinicId e patientId sao obrigatorios"})

        db = PostgresService()

        # O paciente vem junto de proposito: a tela precisa do nome, do
        # telefone e do tipo de pele, e nao existe GET /patients/{id} no
        # backend. Uma chamada a menos com a paciente esperando.
        paciente = db.execute_query(
            """SELECT id, name, phone, skin_type FROM scheduler.patients
               WHERE id = %s::uuid AND clinic_id = %s AND deleted_at IS NULL""",
            (patient_id, clinic_id),
        )
        if not paciente:
            return http_response(404, {"status": "ERROR",
                                       "message": "Paciente nao encontrado"})

        registros = db.execute_query(
            """SELECT r.*, p.name AS professional_name,
                      (SELECT COUNT(*) FROM scheduler.patient_session_record_audit a
                        WHERE a.record_id = r.id AND a.action = 'UPDATE') AS edit_count
               FROM scheduler.patient_session_records r
               LEFT JOIN scheduler.professionals p ON p.id = r.professional_id
               WHERE r.clinic_id = %s AND r.patient_id = %s::uuid
                 AND r.deleted_at IS NULL
               ORDER BY r.session_date DESC, r.created_at DESC""",
            (clinic_id, patient_id),
        ) or []

        por_id = {}
        for linha in registros:
            item = serializa(linha)
            item["edit_count"] = int(item.get("edit_count") or 0)
            item["applications"] = []
            por_id[str(linha["id"])] = item

        if por_id:
            # Uma consulta para todas as aplicacoes, nao uma por registro: a
            # lista abre inteira e N+1 aqui e latencia que a profissional sente.
            aplicacoes = db.execute_query(
                """SELECT * FROM scheduler.patient_session_applications
                   WHERE record_id = ANY(%s::uuid[])
                   ORDER BY record_id, display_order""",
                (list(por_id),),
            ) or []
            for ap in aplicacoes:
                por_id[str(ap["record_id"])]["applications"].append(serializa(ap))

        # Agendamentos confirmados ainda sem registro.
        sem_registro = db.execute_query(
            """SELECT a.id, a.appointment_date, a.start_time,
                      COALESCE(string_agg(asa.area_name, ', '
                               ORDER BY asa.created_at), '') AS areas
               FROM scheduler.appointments a
               LEFT JOIN scheduler.appointment_service_areas asa
                      ON asa.appointment_id = a.id
               LEFT JOIN scheduler.patient_session_records r
                      ON r.appointment_id = a.id AND r.deleted_at IS NULL
               WHERE a.clinic_id = %s AND a.patient_id = %s::uuid
                 AND a.status = 'CONFIRMED' AND r.id IS NULL
               GROUP BY a.id, a.appointment_date, a.start_time
               ORDER BY a.appointment_date DESC
               LIMIT 20""",
            (clinic_id, patient_id),
        ) or []

        return http_response(200, para_o_staff(identidade, {
            "status": "SUCCESS",
            "patient": serializa(paciente[0]),
            "records": list(por_id.values()),
            "appointments_without_record": [serializa(a) for a in sem_registro],
        }))

    except Exception as e:
        logger.error(f"[Prontuario] Erro ao listar registros: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
