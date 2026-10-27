# -*- coding: utf-8 -*-
"""O lote de lembretes de UM dia da agenda (PRD 027).

Um lembrete por agendamento confirmado, nunca repetido (`lembrete_enviado_em`
e `ENFILEIRADO` barram). O dia inteiro sai com o mesmo `send_at`: a
antecedencia e relativa ao primeiro horario do dia, nao a cada sessao.
Quem decide o `send_at` e o chamador (botao: agora; automatico: primeiro
horario menos a antecedencia), e os dois passam por `send_at_do_lote` para
respeitar a janela de silencio.
"""
import logging
from datetime import datetime, time, timezone
from typing import Dict, List, Optional

from src.services.business_hours import fim_do_silencio

logger = logging.getLogger(__name__)

DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _linhas_do_dia(db, clinic_id: str, dia: str) -> List[Dict]:
    return db.execute_query(
        """
        SELECT a.*, p.phone AS patient_phone, p.name AS patient_name,
               (SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at)
                  FROM scheduler.appointment_service_areas asa
                 WHERE asa.appointment_id = a.id) AS areas
          FROM scheduler.appointments a
          LEFT JOIN scheduler.patients p ON p.id = a.patient_id
         WHERE a.clinic_id = %s AND a.appointment_date = %s AND a.status = 'CONFIRMED'
         ORDER BY a.start_time
        """,
        (clinic_id, dia),
    )


def seleciona(db, clinic_id: str, dia: str) -> Dict:
    """Quem recebe, quem ja recebeu, quem ja esta na fila e quem nao tem telefone."""
    enfileiraveis, ja_lembrados, sem_telefone, antes = [], 0, 0, 0
    for a in _linhas_do_dia(db, clinic_id, dia):
        if a.get("lembrete_enviado_em"):
            ja_lembrados += 1
        elif a.get("lembrete_status") == "ENFILEIRADO":
            antes += 1
        elif not (a.get("patient_phone") or "").strip():
            sem_telefone += 1
        else:
            enfileiraveis.append(a)
    return {"enfileiraveis": enfileiraveis, "ja_lembrados": ja_lembrados,
            "sem_telefone": sem_telefone, "enfileirados_antes": antes}


def inicio_da_agenda(appointments: List[Dict]) -> Optional[time]:
    """O primeiro horario confirmado do dia; None sem agendamento."""
    horarios = [a["start_time"] for a in appointments
                if a.get("status", "CONFIRMED") == "CONFIRMED" and a.get("start_time")]
    return min(horarios) if horarios else None


def send_at_do_lote(clinic: Dict, agora: datetime) -> datetime:
    """Agora, ou o fim da janela de silencio se agora cai dentro dela."""
    return fim_do_silencio(clinic, agora)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def enfileira(db, reminder_service, clinic: Dict, dia: str, send_at: datetime,
              simular: bool = False) -> Dict:
    """Poe o lote na fila e marca cada agendamento como ENFILEIRADO.
    `simular` so conta: e a previa do botao."""
    sel = seleciona(db, clinic["clinic_id"], dia)
    if not simular:
        for a in sel["enfileiraveis"]:
            reminder_service.agenda_lembrete(a, clinic, send_at)
            db.execute_write(
                "UPDATE scheduler.appointments SET lembrete_status = 'ENFILEIRADO', "
                "lembrete_erro = NULL, updated_at = NOW() WHERE id = %s::uuid",
                (str(a["id"]),),
            )
    return {"enfileirados": len(sel["enfileiraveis"]), "ja_lembrados": sel["ja_lembrados"],
            "sem_telefone": sel["sem_telefone"], "enfileirados_antes": sel["enfileirados_antes"],
            "send_at": _iso_utc(send_at)}


def _com_e(partes: List[str]) -> str:
    partes = [p.strip() for p in partes if p and p.strip()]
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def variaveis_do_template(appt: Dict, clinic: Dict) -> Dict[str, str]:
    """O que entra em LEMBRETE_SESSAO: {{nome}}, {{areas}}, {{clinic_name}}, {{dia}}, {{hora}}."""
    nome_completo = appt.get("full_name") or appt.get("patient_name") or ""
    dia = appt.get("appointment_date")
    if not hasattr(dia, "weekday"):
        dia = datetime.strptime(str(dia)[:10], "%Y-%m-%d").date()
    hora = appt.get("start_time")
    hora_txt = hora.strftime("%H:%M") if hasattr(hora, "strftime") else str(hora)[:5]
    return {
        "nome": nome_completo.split(" ")[0] if nome_completo else "tudo bem",
        "areas": _com_e((appt.get("areas") or "").split(",")) or "depilação a laser",
        "clinic_name": clinic.get("display_name") or clinic.get("name") or "",
        "dia": f"{DIAS_PT[dia.weekday()]}, {dia.strftime('%d/%m')}",
        "hora": hora_txt,
    }
