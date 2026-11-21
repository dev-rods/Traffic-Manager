# -*- coding: utf-8 -*-
"""Uma sessao por mes, o lado do painel (PRD 056).

A regra mora em `AppointmentService` (criar e remarcar levantam
`SessaoNoMesmoMes`). Aqui fica so o que os dois handlers do painel repetem:
a resposta 409 que a tela transforma em aviso, e a unica excecao a regra,
"manter as duas", que e de ADMIN e exige motivo. STAFF nao a tem: quem quebra
a regra e um especialista, e fica gravado quem e por que.
"""
from src.utils.http import http_response

SAME_MONTH_APPOINTMENT = "SAME_MONTH_APPOINTMENT"


def autor_do_painel(identidade) -> str:
    """Quem fez, para o rastro: nome do funcionario, ou o papel."""
    return (getattr(identidade, "nome", None) or getattr(identidade, "papel", None) or "painel")


def excecao_das_duas(identidade, body):
    """(permitir_duas, erro). `manterAsDuas` por STAFF e 403; por ADMIN sem
    motivo, 400. Sem o campo, (False, None)."""
    if body.get("manterAsDuas") is not True:
        return False, None
    if not getattr(identidade, "e_admin", False):
        return False, http_response(403, {
            "status": "ERROR",
            "message": "Só o administrador pode manter duas sessões no mesmo mês",
        })
    if not (body.get("motivoDasDuas") or "").strip():
        return False, http_response(400, {
            "status": "ERROR",
            "message": "Para manter duas sessões no mesmo mês, informe o motivo",
        })
    return True, None


def resposta_409(existente):
    """O conflito como a tela precisa: a sessao existente, para o aviso
    "{nome} já tem sessão em {data} às {hora}; será cancelada e remarcada"."""
    return http_response(409, {
        "status": "ERROR",
        "code": SAME_MONTH_APPOINTMENT,
        "message": "Esta paciente já tem sessão confirmada neste mês.",
        "existing": {
            "id": str(existente.get("id")),
            "date": str(existente.get("appointment_date")),
            "time": str(existente.get("start_time"))[:5],
            "areas": existente.get("areas_display"),
            "patientName": existente.get("patient_name"),
        },
    })
