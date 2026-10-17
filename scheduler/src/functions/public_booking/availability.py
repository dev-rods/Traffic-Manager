import logging
from datetime import datetime

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.availability_engine import AvailabilityEngine
from src.services import carrinho, mes_vigente

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_DATES_PER_CALL = 31

FECHADO = {"status": "CLOSED", "slots": []}


def handler(event, context):
    """
    GET /public/clinics/{clinicId}/availability
        ?dates=2026-10-20,2026-10-21
        &serviceIds=uuid,uuid
        &serviceAreaPairs=serviceId:areaId,serviceId:areaId

    Status por dia (CLOSED | FULL | AVAILABLE) + horários livres, para uma lista de
    datas. Reaproveita a mesma AvailabilityEngine do bot de WhatsApp.

    A duração da sessão é calculada AQUI, a partir do carrinho, pela mesma função
    que a criação usa para gravar (`carrinho.duracao`): a grade oferecida é a
    grade gravável. Antes o site mandava `totalDuration` somado no navegador,
    sem piso, teto, passo nem combos, e a criação recusava horário que a tela
    tinha oferecido.

    Só vale a janela do site (`mes_vigente`): data passada ou fora do mês
    corrente da clínica volta CLOSED, sem consultar a agenda; hoje, os horários
    que já passaram não entram. `window` na resposta diz ao site até quando vai
    a janela e quando o próximo mês abre - a regra não é repetida no front.

    Compatibilidade: sem `serviceIds` e com `totalDuration`, usa a duração
    informada (front antigo em cache durante o deploy). Logado como legado; sai
    quando o log zerar.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        dates_param = extract_query_param(event, "dates")
        service_ids_param = extract_query_param(event, "serviceIds")
        total_duration_param = extract_query_param(event, "totalDuration")

        if not dates_param or not (service_ids_param or total_duration_param):
            return http_response(400, {
                "status": "ERROR",
                "message": "dates e serviceIds são obrigatórios",
            })

        dates = list(dict.fromkeys(d.strip() for d in dates_param.split(",") if d.strip()))
        if not dates:
            return http_response(400, {"status": "ERROR", "message": "dates vazio"})
        if len(dates) > MAX_DATES_PER_CALL:
            return http_response(400, {
                "status": "ERROR",
                "message": f"no máximo {MAX_DATES_PER_CALL} datas por chamada",
            })
        try:
            datas = {d: datetime.strptime(d, "%Y-%m-%d").date() for d in dates}
        except ValueError:
            return http_response(400, {"status": "ERROR", "message": "dates deve ser YYYY-MM-DD"})

        db = PostgresService()

        clinics = db.execute_query(
            "SELECT timezone FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        if service_ids_param:
            pares = carrinho.pares_da_query(extract_query_param(event, "serviceAreaPairs"))
            service_ids = carrinho.valida_carrinho(
                db, clinic_id, [s for s in service_ids_param.split(",") if s.strip()], pares)
            duracao = carrinho.duracao(db, clinic_id, service_ids, pares)
        else:
            try:
                duracao = int(total_duration_param)
            except ValueError:
                return http_response(400, {"status": "ERROR", "message": "totalDuration inválido"})
            logger.warning(f"[PublicBooking][availability] {clinic_id}: totalDuration legado ({duracao})")

        agora = mes_vigente.agora_na_clinica(clinics[0].get("timezone"))
        hoje = agora.date()
        inicio, fim = mes_vigente.janela(agora)

        dentro = [d for d in dates if mes_vigente.dentro(datas[d], agora)]
        engine = AvailabilityEngine(db)
        days = engine.get_days_status(
            clinic_id, dentro, duracao,
            a_partir_de={hoje.isoformat(): mes_vigente.minutos_de_agora(agora)},
        ) if dentro else {}

        return http_response(200, {
            "status": "SUCCESS",
            "days": {d: days.get(d, FECHADO) for d in dates},
            "window": {
                "start": inicio.isoformat(),
                "end": fim.isoformat(),
                "nextOpensOn": mes_vigente.proximo_mes_abre_em(agora).isoformat(),
            },
        })

    except carrinho.CarrinhoInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao buscar status dos dias: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
