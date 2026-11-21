import json
import logging
from datetime import datetime, date, time

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import (
    clinica_confere,
    dentro_da_janela,
    fora_da_janela,
    para_o_staff,
)
from src.utils.http import parse_body, http_response, extract_query_param
from src.utils.phone import is_valid_br_phone
from src.services import carrinho
from src.services.carrinho import CarrinhoInvalido
from src.services.db.postgres import PostgresService
from src.services.appointment_service import (
    AppointmentService, ConflictError, NotFoundError, SessaoNoMesmoMes)
from src.services.mesmo_mes import SAME_MONTH_APPOINTMENT, autor_do_painel, excecao_das_duas, resposta_409
from src.services.duracao_manual import DuracaoInvalida
from src.services.desconto_personalizado import DescontoInvalido, normaliza_centavos
from src.services.politica_de_desconto import RAZAO_NENHUM

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _final_do_telefone(phone):
    return f"***{str(phone)[-4:]}" if phone else "-"


def _simula(clinic_id, body, identidade):
    """A cotacao do painel (PRD 053). Diferente da rota publica do site:
    devolve a razao mesmo com telefone (e a recepcao olhando a propria
    paciente) e diz se o banco considera esta a primeira sessao."""
    phone = body.get("phone") or None
    if phone and not is_valid_br_phone(str(phone)):
        return http_response(400, {"status": "ERROR", "message": "Telefone invalido"})
    service_ids = body.get("serviceIds") or ([body.get("serviceId")] if body.get("serviceId") else None)
    try:
        db = PostgresService()
        pares = carrinho.pares_do_corpo(body.get("serviceAreaPairs"))
        service_ids = carrinho.valida_carrinho(db, clinic_id, service_ids, pares)
        cotacao = carrinho.cota(db, clinic_id, service_ids, pares, phone)
    except CarrinhoInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})

    logger.info(
        f"[Quote] {clinic_id} tel={_final_do_telefone(phone)}: pares={cotacao.qtd_areas} "
        f"original={cotacao.original_cents} final={cotacao.final_cents} "
        f"razao={cotacao.desconto.razao} pct={cotacao.desconto.pct}"
    )
    return http_response(200, para_o_staff(identidade, {
        "status": "SUCCESS",
        "quote": {
            "originalPriceCents": cotacao.original_cents,
            "discountPct": float(cotacao.desconto.pct or 0),
            "discountReason": cotacao.desconto.razao,
            "finalPriceCents": cotacao.final_cents,
            "areaCount": cotacao.qtd_areas,
            "isFirst": bool(cotacao.desconto.is_first),
        },
    }))


def handler(event, context):
    """
    POST /appointments[?simular=true]

    `simular=true` NAO cria: devolve o que a politica da clinica decide para
    esta paciente e estas areas (`quote`), com a MESMA conta da criacao
    (`carrinho.cota`), para o modal mostrar o total que vai ser gravado
    (PRD 053). Mora aqui, e nao numa rota propria, porque o stack de prod
    esta em 494 dos 500 recursos do CloudFormation (medido em 20/11/2026) e
    uma Lambda nova custa 5. No modo simular so clinicId e as areas sao
    obrigatorios; `phone` e opcional (sem ele, so a faixa por areas vale).

    Body:
    {
        "clinicId": "laser-beauty-sp-abc123",
        "phone": "5511999999999",
        "serviceId": "uuid",            // single service (backwards compat)
        "serviceIds": ["uuid", "uuid"],  // multiple services (preferred)
        "date": "2026-02-10",
        "time": "10:00",
        "serviceAreaPairs": [            // optional, for services with areas
            {"serviceId": "uuid", "areaId": "uuid"}
        ],
        "professionalId": "uuid",        // optional
        "manualDurationMinutes": 75,     // optional, fixa a duracao DESTE
                                         // agendamento; vazio = calculada
        "substituir": true,              // PRD 056: confirmou que a sessao do
                                         // mesmo mes sera cancelada e remarcada
        "manterAsDuas": true,            // PRD 056: so ADMIN, com motivoDasDuas
        "motivoDasDuas": "..."
    }

    Uma sessao por mes (PRD 056): paciente com sessao confirmada futura no mes
    da data responde 409 `code: SAME_MONTH_APPOINTMENT` com `existing`; o
    painel avisa e repete com `substituir`. `manterAsDuas` e a unica excecao,
    por ADMIN e com motivo (403 para STAFF, 400 sem motivo).
    """
    try:
        identidade, error_response = require_acesso(event, "agenda.escrever")
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        clinic_id = body.get("clinicId")
        phone = body.get("phone")
        service_id = body.get("serviceId")
        service_ids = body.get("serviceIds")
        appt_date = body.get("date")
        appt_time = body.get("time")

        # Esta rota recebe a clinica no CORPO, e nao no caminho: o
        # `_confere_a_clinica` do require_acesso le o path e aqui nao alcanca.
        # Sem esta linha, um token da Essencia agendaria na Nobre Laser.
        if not clinica_confere(identidade, clinic_id):
            return http_response(403, {
                "status": "ERROR",
                "message": "Seu usuario nao tem acesso a esta clinica"})

        if (extract_query_param(event, "simular") or "").lower() in ("1", "true"):
            return _simula(clinic_id, body, identidade)

        if not dentro_da_janela(identidade, appt_date):
            return fora_da_janela()

        # Accept either serviceId (string) or serviceIds (array)
        if not service_id and not service_ids:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: clinicId, phone, serviceId ou serviceIds, date, time"
            })

        if not all([clinic_id, phone, appt_date, appt_time]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: clinicId, phone, serviceId ou serviceIds, date, time"
            })

        # Normalize: if serviceIds provided, use it; otherwise wrap serviceId
        if not service_ids:
            service_ids = [service_id]
        if not service_id:
            service_id = service_ids[0]

        # Desconto em reais (PRD 050). Exclusivo com o percentual.
        if "discountCents" in body and body.get("discountPct"):
            return http_response(400, {
                "status": "ERROR", "message": "Mande discountPct ou discountCents, nao os dois"})
        ok, discount_cents = normaliza_centavos(body.get("discountCents"))
        if not ok:
            return http_response(400, {
                "status": "ERROR",
                "message": "discountCents deve ser um inteiro de centavos maior que zero"})
        # "Sem desconto" escolhido no painel (PRD 053): pct 0 com razao "none".
        # E o que impede o servico de aplicar a politica da clinica por cima.
        # Razao "none" com desconto junto e contradicao, nao escolha.
        if body.get("discountReason") == RAZAO_NENHUM and (body.get("discountPct") or discount_cents):
            return http_response(400, {
                "status": "ERROR", "message": "discountReason 'none' nao combina com desconto"})

        duas, erro_das_duas = excecao_das_duas(identidade, body)
        if erro_das_duas:
            return erro_das_duas

        db = PostgresService()

        # `.completo(db)` e nao o construtor: sem o lead_service, a conversao
        # do gclid nao e registrada e o agendamento fica invisivel para o
        # Google Ads. Era esse o caso ate 27/09/2026.
        service = AppointmentService.completo(db)

        # Parse serviceAreaPairs from body
        raw_pairs = body.get("serviceAreaPairs")
        service_area_pairs = None
        if raw_pairs and isinstance(raw_pairs, list):
            service_area_pairs = [
                {"service_id": p.get("serviceId"), "area_id": p.get("areaId")}
                for p in raw_pairs
                if p.get("serviceId") and p.get("areaId")
            ]

        result = service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=service_id,
            date=appt_date,
            time=appt_time,
            professional_id=body.get("professionalId"),
            service_ids=service_ids,
            service_area_pairs=service_area_pairs if service_area_pairs else None,
            full_name=body.get("fullName"),
            # Observação curta que a atendente escreve ao marcar. Aparece no
            # popover da agenda; a edição já aceitava, a criação não.
            notes=(body.get("notes") or "").strip()[:500] or None,
            discount_pct=body.get("discountPct", 0),
            discount_reason=body.get("discountReason"),
            discount_cents=discount_cents,
            # Sempre um booleano, nunca None: pelo painel a estreia e decisao de
            # quem esta na recepcao, e o padrao e desmarcado. A contagem
            # automatica so enxerga este banco, e a clinica atende desde antes
            # dele existir.
            is_first_visit=bool(body.get("isFirstVisit")),
            # A duracao que a recepcao fixou para ESTE agendamento. Nao mexe na
            # regra da clinica, e o bot nao chega aqui: nenhuma tool do agente
            # expoe este campo. Ver duracao_manual.
            manual_duration_minutes=body.get("manualDurationMinutes"),
            substituir_mesmo_mes=body.get("substituir") is True,
            permitir_duas=duas,
            autor=autor_do_painel(identidade),
            motivo_das_duas=body.get("motivoDasDuas"),
        )

        appointment = _serialize_row(result)

        return http_response(201, para_o_staff(identidade, {
            "status": "SUCCESS",
            "message": "Agendamento criado com sucesso",
            "appointment": appointment,
        }))

    except (DuracaoInvalida, DescontoInvalido) as e:
        # Dedo errado no formulario e 400, nao 500.
        return http_response(400, {"status": "ERROR", "message": str(e)})

    except SessaoNoMesmoMes as e:
        return resposta_409(e.existente)

    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})

    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})

    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
