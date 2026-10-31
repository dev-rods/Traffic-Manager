import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.availability_engine import AvailabilityEngine
from src.services import carrinho, janela_do_site, relogio

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    GET /public/clinics/{clinicId}/availability
        ?serviceIds=uuid,uuid
        &serviceAreaPairs=serviceId:areaId,serviceId:areaId

    As próximas datas com horário livre para o carrinho, em ordem, cada uma com
    os horários: `days` = {data: {status: AVAILABLE, slots: [...]}}. Quantas é
    `max_future_dates` da clínica ("Datas futuras" em Configurações), o mesmo
    limite do bot - a regra mora em `janela_do_site`, e o front só exibe.
    Reaproveita a mesma AvailabilityEngine do bot de WhatsApp.

    A duração da sessão é calculada AQUI, a partir do carrinho, pela mesma função
    que a criação usa para gravar (`carrinho.duracao`): a grade oferecida é a
    grade gravável. Antes o site mandava `totalDuration` somado no navegador,
    sem piso, teto, passo nem combos, e a criação recusava horário que a tela
    tinha oferecido.

    Compatibilidade: `dates` (front antigo, que pedia o mês) é ignorado; sem
    `serviceIds` e com `totalDuration`, usa a duração informada. Logado como
    legado; sai quando o log zerar.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        service_ids_param = extract_query_param(event, "serviceIds")
        total_duration_param = extract_query_param(event, "totalDuration")

        if not (service_ids_param or total_duration_param):
            return http_response(400, {"status": "ERROR", "message": "serviceIds é obrigatório"})

        db = PostgresService()

        clinics = db.execute_query(
            "SELECT timezone, max_future_dates FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
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

        agora = relogio.agora_na_clinica(clinics[0].get("timezone"))
        days = janela_do_site.dias_oferecidos(
            AvailabilityEngine(db), clinic_id, duracao, agora, janela_do_site.quantas(clinics[0]))

        return http_response(200, {"status": "SUCCESS", "days": days})

    except carrinho.CarrinhoInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao buscar status dos dias: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
