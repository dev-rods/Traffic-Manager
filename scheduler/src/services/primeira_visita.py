# -*- coding: utf-8 -*-
"""Quem está passando pela clínica pela primeira vez.

A pergunta já era respondida em dois lugares diferentes: o desconto de primeira
sessão contava agendamentos confirmados, e a agenda não sabia de nada. Agora a
resposta mora aqui, e quem precisa dela chama a mesma função.

Isso importa porque a marca fica GRAVADA no agendamento - a atendente precisa
poder desmarcar quando a pessoa já veio antes por fora do sistema. Campo gravado
que nasce de duas contas diferentes é o defeito que mais custou nesta base:
divergem em silêncio e ninguém percebe até alguém conferir à mão.
"""
import logging

logger = logging.getLogger(__name__)


def e_primeira_visita(db, clinic_id: str, phone: str, ignorar_id=None) -> bool:
    """A pessoa não tem nenhuma sessão confirmada além, talvez, desta.

    `ignorar_id` existe para perguntar DEPOIS de criar o agendamento: nesse
    momento ele já está no banco e contaria a si mesmo.

    Cancelada não conta. Quem marcou, desmarcou e voltou continua estreando -
    a sessão que não aconteceu não é uma visita.

    Falha fechada: sem resposta do banco, devolve False. Marcar "primeira vez"
    em quem já é cliente antigo é mais constrangedor na recepção do que deixar
    de marcar uma estreia.
    """
    try:
        parametros = [clinic_id, phone]
        filtro = ""
        if ignorar_id:
            filtro = "AND a.id <> %s::uuid"
            parametros.append(str(ignorar_id))

        linhas = db.execute_query(
            f"""
            SELECT COUNT(*) AS total
            FROM scheduler.appointments a
            JOIN scheduler.patients p ON p.id = a.patient_id
            WHERE a.clinic_id = %s AND p.phone = %s
              AND a.status = 'CONFIRMED' {filtro}
            """,
            tuple(parametros),
        )
        return int(linhas[0]["total"]) == 0 if linhas else False
    except Exception as e:
        logger.error(f"[PrimeiraVisita] Falha ao conferir {phone}: {e}")
        return False


def passa_a_marca_adiante(db, appointment_id) -> bool:
    """Cancelou a estreia? A próxima sessão confirmada vira a estreia.

    Decisão do André em 09/09/2026. Sem isso, uma pessoa que marcou, desmarcou e
    remarcou apareceria na agenda como veterana na sessão em que de fato pisa na
    clínica pela primeira vez - e a marca ficaria numa linha cancelada, que
    ninguém olha.

    Devolve True quando alguem herdou a marca.
    """
    try:
        cancelado = db.execute_query(
            "SELECT patient_id, clinic_id, is_first_visit FROM scheduler.appointments "
            "WHERE id = %s::uuid",
            (str(appointment_id),),
        )
        if not cancelado or not cancelado[0].get("is_first_visit"):
            return False

        db.execute_write(
            "UPDATE scheduler.appointments SET is_first_visit = FALSE, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (str(appointment_id),),
        )

        # A proxima em ordem de agenda, nao de criacao: quem estreia e quem
        # chega primeiro na clinica.
        herdeiro = db.execute_write_returning(
            """
            UPDATE scheduler.appointments SET is_first_visit = TRUE, updated_at = NOW()
            WHERE id = (
                SELECT id FROM scheduler.appointments
                WHERE patient_id = %s::uuid AND clinic_id = %s AND status = 'CONFIRMED'
                ORDER BY appointment_date, start_time
                LIMIT 1
            )
            RETURNING id
            """,
            (str(cancelado[0]["patient_id"]), cancelado[0]["clinic_id"]),
        )
        if herdeiro:
            logger.info(
                f"[PrimeiraVisita] marca passou de {appointment_id} para {herdeiro['id']}"
            )
        return bool(herdeiro)
    except Exception as e:
        # Nunca derruba o cancelamento: a paciente pediu para cancelar, e falhar
        # por causa de uma marca visual seria trocar o essencial pelo enfeite.
        logger.error(f"[PrimeiraVisita] Falha ao passar a marca de {appointment_id}: {e}")
        return False
