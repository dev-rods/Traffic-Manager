import logging
import os
import re
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.phone import is_valid_br_phone, normalize_phone
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService, ConflictError, NotFoundError
from src.services.template_service import TemplateService
from src.services.orientacoes_pos_sessao import texto as orientacoes_da_clinica
from src.services.politica_de_desconto import texto_do_preco
from src.services import carrinho, mes_vigente
from src.providers.zapi_provider import ZApiProvider

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


def _format_date_br(iso_date: str) -> str:
    try:
        y, m, d = iso_date.split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return iso_date


_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _final_do_telefone(phone):
    return f"***{str(phone)[-4:]}" if phone else "-"


def _send_confirmation_whatsapp(db: PostgresService, clinic: dict, phone: str, appointment: dict, qtd_areas: int) -> None:
    """
    A mesma confirmação que o agente de WhatsApp manda ao fechar um
    agendamento: o template "BOOKED" (customizável por clínica), com o valor
    já com desconto, e em seguida as orientações pré-sessão da clínica, numa
    mensagem própria - como o agente faz (`TOOLS_QUE_MARCAM_SESSAO` em
    conversation_agent): a orientação vai crua, do jeito que a clínica escreveu.

    O valor sai do que foi GRAVADO, não da cotação. Cada envio tem seu próprio
    try: falha num não impede o outro, e nenhuma derruba a criação - o
    agendamento já está persistido.
    """
    provider = ZApiProvider(
        instance_id=clinic.get("zapi_instance_id") or "",
        instance_token=clinic.get("zapi_instance_token") or "",
        client_token=os.environ.get("ZAPI_CLIENT_TOKEN", ""),
    )
    template_service = TemplateService(db)

    try:
        duration_minutes = appointment.get("total_duration_minutes")
        hours, mins = divmod(int(duration_minutes or 0), 60)
        duration_str = f"{hours}h{mins:02d}min" if hours else f"{duration_minutes}min"

        variables = {
            "date": _format_date_br(str(appointment.get("appointment_date", ""))[:10]),
            "time": str(appointment.get("start_time", ""))[:5],
            "duration": duration_str,
            "price": texto_do_preco(
                appointment.get("original_price_cents"),
                appointment.get("final_price_cents"),
                appointment.get("discount_pct"),
                appointment.get("discount_reason"),
                qtd_areas,
            ),
        }
        content = template_service.get_and_render(clinic["clinic_id"], "BOOKED", variables)
        result = provider.send_text(phone, content)
        if not result.success:
            logger.error(f"[PublicBooking] Falha ao enviar confirmação por WhatsApp: {result.error}")
    except Exception as e:
        logger.error(f"[PublicBooking] Erro ao montar/enviar confirmação por WhatsApp: {e}", exc_info=True)

    try:
        orientacoes = orientacoes_da_clinica(template_service, clinic["clinic_id"])
        if orientacoes:
            result = provider.send_text(phone, orientacoes)
            if not result.success:
                logger.error(f"[PublicBooking] Falha ao enviar orientações pré-sessão: {result.error}")
    except Exception as e:
        logger.error(f"[PublicBooking] Erro ao enviar orientações pré-sessão: {e}", exc_info=True)


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/appointments

    Body:
    {
        "phone": "string",
        "fullName": "string",
        "serviceIds": ["uuid", ...], // carrinho — 1+ serviços
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "professionalId": "uuid",     // opcional
        "serviceAreaPairs": [          // opcional — quando os serviços têm áreas
            {"serviceId": "uuid", "areaId": "uuid"}
        ]
    }

    Sem verificação por código: o agendamento é criado direto e a confirmação
    chega pelo próprio WhatsApp (mesmo template "BOOKED" do bot) — a posse do
    número não precisa ser confirmada antes de agendar, só de ver/cancelar
    (endpoints /my-appointments e /appointments/{id}/cancel continuam exigindo
    o token de /verify/confirm).
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

        phone = body.get("phone")
        service_ids = body.get("serviceIds")
        appt_date = body.get("date")
        appt_time = body.get("time")
        full_name = (body.get("fullName") or "").strip()

        if not all([phone, service_ids, appt_date, appt_time, full_name]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: phone, serviceIds, date, time, fullName",
            })
        if not is_valid_br_phone(str(phone)):
            return http_response(400, {"status": "ERROR", "message": "Telefone inválido"})
        phone = normalize_phone(str(phone))

        try:
            data = datetime.strptime(str(appt_date), "%Y-%m-%d").date()
        except ValueError:
            return http_response(400, {"status": "ERROR", "message": "date deve ser YYYY-MM-DD"})
        if not _HORA.match(str(appt_time)):
            return http_response(400, {"status": "ERROR", "message": "time deve ser HH:MM"})

        db = PostgresService()

        clinics = db.execute_query(
            "SELECT clinic_id, timezone, zapi_instance_id, zapi_instance_token FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        pares = carrinho.pares_do_corpo(body.get("serviceAreaPairs"))
        service_ids = carrinho.valida_carrinho(db, clinic_id, service_ids, pares)

        # A janela do site vale aqui também, não só na tela: o calendário não
        # oferece fora dela, mas uma requisição direta não passa pelo calendário.
        agora = mes_vigente.agora_na_clinica(clinics[0].get("timezone"))
        hh, mm = (int(x) for x in str(appt_time).split(":"))
        passou = data == agora.date() and hh * 60 + mm < mes_vigente.minutos_de_agora(agora)
        if not mes_vigente.dentro(data, agora) or passou:
            return http_response(400, {
                "status": "ERROR",
                "message": "Esta data não está disponível para agendamento online.",
            })

        # Combos, duração e desconto pelas mesmas funções do agente. Os pares
        # que seguem para a criação são os de DEPOIS do combo: duração, preço e
        # o que fica gravado são os que o WhatsApp gravaria para o mesmo pedido.
        cotacao = carrinho.cota(db, clinic_id, service_ids, pares, phone)

        logger.info(
            f"[PublicBooking][create] {clinic_id} {appt_date} {appt_time} "
            f"dur={cotacao.duracao_minutos} tel={_final_do_telefone(phone)} "
            f"razao={cotacao.desconto.razao} pct={cotacao.desconto.pct}"
        )

        professional_id = carrinho.profissional_da_clinica(db, clinic_id, body.get("professionalId"))
        if body.get("professionalId") and not professional_id:
            logger.warning(f"[PublicBooking][create] {clinic_id} professionalId legado ignorado")

        service = AppointmentService.completo(db)

        try:
            result = service.create_appointment(
                clinic_id=clinic_id,
                phone=phone,
                service_id=service_ids[0],
                date=appt_date,
                time=appt_time,
                # Front antigo em cache ainda manda; ausente, o serviço escolhe
                # (o conflito de horário é checado na clínica inteira).
                professional_id=professional_id,
                service_ids=service_ids,
                service_area_pairs=cotacao.pares or None,
                discount_pct=cotacao.desconto.pct,
                discount_reason=cotacao.desconto.razao,
                full_name=full_name,
            )
        except ConflictError:
            # Sem este log o 409 não deixava rastro: era o "agendamento que
            # não chegou no banco" sem nada para investigar.
            logger.warning(
                f"[PublicBooking][create] 409 {clinic_id} {appt_date} {appt_time} "
                f"dur={cotacao.duracao_minutos}"
            )
            raise

        _send_confirmation_whatsapp(db, clinics[0], phone, result, cotacao.qtd_areas)

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Agendamento criado com sucesso",
            "appointment": _serialize_row(result),
        })

    except carrinho.CarrinhoInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao criar agendamento público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
