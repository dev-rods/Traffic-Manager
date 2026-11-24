import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.phone import is_valid_br_phone
from src.services.db.postgres import PostgresService
from src.services import carrinho
from src.services.carrinho import CarrinhoInvalido, cota, pares_do_corpo, valida_carrinho
from src.functions.public_booking.create_appointment import MENSAGEM_TOKEN
from src.utils.booking_verification import verify_token

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
        "phone": "5511999999999",                                        // opcional
        "token": "<token de sessao de /verify/confirm>"                  // obrigatorio com phone
    }

    O valor que o site mostra antes de confirmar - total pela tabela, desconto
    e valor final -, calculado pelas MESMAS funções que a criação usa para
    gravar (`carrinho.cota`).

    Sem celular (ou com celular sem token): só a faixa por quantidade de
    áreas, `cadastro` null. É a cotação cega, a única que a rota pública dá a
    quem ainda não provou ser dono do número.

    Com celular E token de sessão válido (PRD 061): também primeira sessão e
    desconto personalizado, com o motivo, e `quote.cadastro` diz o que falta
    no cadastro (`cpf`, `birth_date`, `email`). Antes do PRD 061 bastava o
    celular: qualquer pessoa descobria o desconto combinado de outra só
    digitando o número dela. Agora o preço da pessoa só sai depois do código.

    Celular com token inválido ou vencido: 401, para o site refazer o código
    em vez de mostrar o preço de tabela como se fosse o da pessoa. Celular
    sem token nenhum é ignorado (não é erro): o site antigo em cache cota
    assim na etapa "Seus dados" e segue vendo a tabela até a criação.

    POST e não GET: o carrinho pode ter dezenas de pares, e o telefone não deve
    ir para a URL (nem para log de acesso). Não devolve duração (o site não a
    exibe).
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

        # O celular só vale com o token de sessão do próprio número (PRD 061).
        token = body.get("token")
        if phone and token is None:
            phone = None
        elif phone and not verify_token(clinic_id, str(phone), str(token)):
            return http_response(401, {"status": "ERROR", "code": "TOKEN_INVALIDO", "message": MENSAGEM_TOKEN})

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

        # O que falta no cadastro deste celular, para o site pedir só isso
        # (PRD 032). Só nomes de campos, nunca valores; e só com o token.
        cadastro = carrinho.cadastro_para_o_site(
            carrinho.paciente_do_telefone(db, clinic_id, phone)) if phone else None

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
                "cadastro": cadastro,
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
