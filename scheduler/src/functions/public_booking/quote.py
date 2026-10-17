import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.phone import is_valid_br_phone
from src.services.db.postgres import PostgresService
from src.services.carrinho import CarrinhoInvalido, cota, pares_do_corpo, valida_carrinho

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _final_do_telefone(phone):
    return f"***{str(phone)[-4:]}" if phone else "-"


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/quote

    Body:
    {
        "serviceIds": ["uuid", ...],
        "serviceAreaPairs": [{"serviceId": "uuid", "areaId": "uuid"}],  // opcional
        "phone": "5511999999999"                                         // opcional
    }

    O valor que o site mostra antes de confirmar - total pela tabela, desconto
    e valor final -, calculado pelas MESMAS funções que a criação usa para
    gravar (`carrinho.cota`). Sem telefone, só o desconto por quantidade de
    áreas; com telefone, também primeira sessão e desconto personalizado.

    POST e não GET: o carrinho pode ter dezenas de pares, e o telefone não deve
    ir para a URL (nem para log de acesso).

    Não devolve duração (o site não a exibe) nem o histórico da pessoa: o motivo
    do desconto é só a categoria ("personalizado"), nunca o porquê.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        phone = body.get("phone") or None
        if phone and not is_valid_br_phone(str(phone)):
            return http_response(400, {"status": "ERROR", "message": "Telefone inválido"})

        db = PostgresService()

        clinics = db.execute_query(
            "SELECT clinic_id FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        pares = pares_do_corpo(body.get("serviceAreaPairs"))
        service_ids = valida_carrinho(db, clinic_id, body.get("serviceIds"), pares)

        cotacao = cota(db, clinic_id, service_ids, pares, phone)

        logger.info(
            f"[PublicBooking][quote] {clinic_id} tel={_final_do_telefone(phone)}: "
            f"pares={len(pares)}->{cotacao.qtd_areas} combos={len(cotacao.combos)} "
            f"original={cotacao.original_cents} final={cotacao.final_cents} "
            f"razao={cotacao.desconto.razao} pct={cotacao.desconto.pct}"
        )

        return http_response(200, {
            "status": "SUCCESS",
            "quote": {
                "originalPriceCents": cotacao.original_cents,
                "discountPct": float(cotacao.desconto.pct or 0),
                "discountReason": cotacao.desconto.razao,
                "finalPriceCents": cotacao.final_cents,
                "areaCount": cotacao.qtd_areas,
                "combos": [
                    {"from": t["de"], "to": t["para"], "savingsCents": t["economia_cents"]}
                    for t in cotacao.combos
                ],
            },
        })

    except CarrinhoInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao cotar carrinho público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
