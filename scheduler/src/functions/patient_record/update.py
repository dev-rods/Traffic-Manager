import logging

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import para_o_staff
from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.historico_de_sessao import (
    RegistroInvalido,
    grava_trilha,
    valida_aplicacoes,
)
from src.functions.patient_record._comum import grava_aplicacoes, registro_com_aplicacoes
from src.functions.patient_record.create import _do_corpo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """PUT /clinics/{clinicId}/session-records/{recordId}

    Edita o registro. O estado anterior NAO se perde: a trilha guarda o estado
    completo a cada escrita, e e dela que sai o painel de "editado". Decisao do
    Andre em 17/09/2026.
    """
    try:
        identidade, erro = require_acesso(event, "prontuario.escrever")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        record_id = extract_path_param(event, "recordId")
        if not clinic_id or not record_id:
            return http_response(400, {"status": "ERROR",
                                       "message": "clinicId e recordId sao obrigatorios"})

        body = parse_body(event) or {}
        db = PostgresService()

        atual = db.execute_query(
            """SELECT * FROM scheduler.patient_session_records
               WHERE id = %s::uuid AND clinic_id = %s AND deleted_at IS NULL""",
            (record_id, clinic_id),
        )
        if not atual:
            return http_response(404, {"status": "ERROR",
                                       "message": "Registro nao encontrado"})
        versao = atual[0].get("version", 1)

        campos, params = [], []
        for chave_http, coluna, cast in (
            ("sessionDate", "session_date", "::date"),
            ("professionalId", "professional_id", "::uuid"),
            ("tannedSkin", "tanned_skin", ""),
            ("notes", "notes", ""),
        ):
            if chave_http in body:
                valor = body[chave_http]
                if chave_http == "notes":
                    valor = (valor or "").strip() or None
                if chave_http == "professionalId":
                    valor = valor or None
                campos.append(f"{coluna} = %s{cast}")
                params.append(valor)

        if campos:
            params += [record_id, versao]
            alteradas = db.execute_write(
                f"""UPDATE scheduler.patient_session_records
                    SET {", ".join(campos)}, version = version + 1, updated_at = NOW()
                    WHERE id = %s::uuid AND version = %s""",
                tuple(params),
            )
            if alteradas == 0:
                return http_response(409, {
                    "status": "ERROR",
                    "message": "Registro foi modificado por outra pessoa. Reabra e tente de novo.",
                })

        if "applications" in body:
            grava_aplicacoes(db, record_id,
                             valida_aplicacoes(_do_corpo(body["applications"])))

        registro = registro_com_aplicacoes(db, record_id)
        grava_trilha(db, record_id, clinic_id, "UPDATE", registro,
                     body.get("changedBy"))

        logger.info(f"[Prontuario] registro editado: {record_id}")
        return http_response(200, para_o_staff(identidade, {"status": "SUCCESS", "record": registro}))

    except RegistroInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"[Prontuario] Erro ao editar registro: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
