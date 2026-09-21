import logging

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import para_o_staff
from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.protocolo_laser import METODOS, tabela_para_a_tela
from src.functions.patient_record._comum import serializa

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """GET /clinics/{clinicId}/laser-protocol

    O protocolo inteiro mais o mapa da clinica, num payload so.

    Sao 80 linhas e elas quase nunca mudam. Uma chamada cacheada no frontend
    evita uma consulta por linha de aplicacao enquanto a profissional digita -
    e ela digita com a paciente esperando.

    O protocolo sai do modulo, nao do banco: as duas fontes sao semeadas da
    mesma constante, e ler do modulo dispensa uma ida ao Postgres numa resposta
    que e pura referencia.
    """
    try:
        identidade, erro = require_acesso(event, "prontuario.ler")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR",
                                       "message": "clinicId e obrigatorio"})

        db = PostgresService()
        mapa = db.execute_query(
            """SELECT m.area_id, a.name AS area_name, m.protocol_area_key,
                      m.display_order
               FROM scheduler.area_protocol_map m
               JOIN scheduler.areas a ON a.id = m.area_id
               WHERE a.clinic_id = %s AND a.active = TRUE
               ORDER BY a.name, m.display_order""",
            (clinic_id,),
        ) or []

        return http_response(200, para_o_staff(identidade, {
            "status": "SUCCESS",
            "methods": [
                {"key": chave, "label": d["rotulo"],
                 "fields": list(d["campos"]), "movement": d["movimento"]}
                for chave, d in METODOS.items()
            ],
            "parameters": tabela_para_a_tela(),
            "area_map": [serializa(m) for m in mapa],
        }))

    except Exception as e:
        logger.error(f"[Prontuario] Erro ao ler o protocolo: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
