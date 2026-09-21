# -*- coding: utf-8 -*-
"""O que um funcionário vê, depois de o servidor decidir.

Decisões do André em 21/09/2026:

- **Nenhum valor em reais.** Não só relatório: preço de agendamento, preço de
  serviço, desconto do paciente. Tudo sai da resposta.
- **A agenda começa HOJE.** Sem passado, com a consequência assumida de que
  uma sessão não registrada no mesmo dia sai do alcance dele.

Isto roda no SERVIDOR, e não na tela. Esconder um campo no React não esconde
nada de quem abre o DevTools ou chama a rota direto - e o funcionário tem um
token válido na mão.
"""
import logging
import re
from datetime import date, datetime
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Casado por SUFIXO, e não por nome exato. `price_cents` pega
# `original_price_cents` e `final_price_cents` de uma vez, e um campo novo que
# siga a convenção do projeto já nasce coberto.
SUFIXOS_DE_VALOR = (
    "price_cents",
    "discount_pct",
    "total_price",
    "price",
    "revenue",
    "faturamento",
    "valor",
)

# Segredos da clínica. Nunca saem para funcionário, e alguns nem deveriam sair
# para o painel do admin - mas isso e outra conversa.
CAMPOS_SECRETOS = (
    "zapi_instance_id",
    "zapi_instance_token",
    "owner_email",
    "google_spreadsheet_id",
    "google_sheet_name",
)


def _e_valor(chave: str) -> bool:
    baixa = chave.lower()
    return any(baixa.endswith(s) for s in SUFIXOS_DE_VALOR)


def sem_valores(dado: Any) -> Any:
    """Remove dinheiro de qualquer estrutura, em qualquer profundidade.

    Recursivo de propósito: a resposta de agendamentos é uma lista dentro de um
    dicionário, a de serviços tem áreas dentro de serviços, e tratar só o
    primeiro nível deixaria o valor passar no segundo.
    """
    if isinstance(dado, dict):
        return {
            k: sem_valores(v)
            for k, v in dado.items()
            if not _e_valor(k)
        }
    if isinstance(dado, (list, tuple)):
        return [sem_valores(x) for x in dado]
    return dado


def sem_segredos(clinica: dict) -> dict:
    """A clínica como o funcionário pode vê-la: identidade e horário, nada de
    credencial."""
    return {k: v for k, v in (clinica or {}).items() if k not in CAMPOS_SECRETOS}


def para_o_staff(identidade, dado: Any) -> Any:
    """A resposta como esta pessoa pode vê-la.

    Quem decide é `identidade.mostra_valores`: admin sempre, e o funcionário
    conforme o interruptor que o administrador ligou para ele. Nem toda
    recepção é igual - quem cobra no balcão precisa do valor, quem só agenda
    não precisa.
    """
    if identidade is None or identidade.mostra_valores:
        return dado
    return sem_valores(dado)


# -- Janela da agenda --------------------------------------------------------

_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _para_data(valor) -> Optional[date]:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and _DATA.match(valor.strip()):
        try:
            return datetime.strptime(valor.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def dentro_da_janela(identidade, valor) -> bool:
    """Esta data está no alcance deste usuário?

    Data ilegível responde `False`. Numa decisão de acesso, não conseguir ler o
    pedido não pode significar liberar.
    """
    if identidade is None or identidade.e_admin:
        return True

    from src.utils.acesso import janela_da_agenda

    alvo = _para_data(valor)
    if alvo is None:
        return False

    inicio, fim = janela_da_agenda(identidade)
    return inicio <= alvo <= fim


def pode_tocar_agendamento(identidade, db, appointment_id) -> bool:
    """Pode mexer NESTE agendamento?

    Duas perguntas, porque a rota de edição é `PUT /appointments/{id}` e não
    carrega clínica nenhuma na URL:

    1. **É da clínica dele?** Sem isto, o `_confere_a_clinica` não alcança:
       ele confere o `clinicId` do caminho, que aqui não existe. Um id de
       agendamento da Nobre Laser passaria direto.
    2. **Está na janela dele?** Sem isto, a janela protegeria só a LISTAGEM, e
       bastaria ter o id de um agendamento de dezembro para editá-lo.
    """
    if identidade is None or identidade.e_admin:
        return True

    try:
        linhas = db.execute_query(
            "SELECT appointment_date, clinic_id FROM scheduler.appointments "
            "WHERE id = %s::uuid",
            (appointment_id,),
        )
    except Exception as e:
        logger.error(f"[staff] Falha ao conferir {appointment_id}: {e}")
        return False

    if not linhas:
        # Não existe. Quem decide o 404 é o serviço, logo adiante - e responder
        # 403 aqui contaria a quem sondasse que aquele id existe em outro lugar.
        return True

    if linhas[0].get("clinic_id") != identidade.clinic_id:
        logger.info(f"[staff] {identidade.user_id} tentou agendamento de outra clinica")
        return False

    return dentro_da_janela(identidade, linhas[0]["appointment_date"])


def clinica_confere(identidade, clinic_id) -> bool:
    """Para as rotas que recebem a clínica no CORPO, e não no caminho."""
    if identidade is None or identidade.e_admin:
        return True
    return bool(clinic_id) and clinic_id == identidade.clinic_id


def fora_da_janela():
    """A recusa, com o mesmo texto em todos os pontos."""
    from src.utils.http import http_response

    return http_response(403, {
        "status": "ERROR",
        "message": "Esta data está fora do período liberado para o seu usuário",
    })


def limita_intervalo(identidade, de, ate) -> Tuple[Optional[str], Optional[str]]:
    """Aperta o intervalo pedido até caber na janela.

    Apertar em vez de recusar: o painel pede "de 15/09 a 30/09" e recebe de
    volta só o pedaço que lhe cabe, em vez de um erro que o obrigaria a
    adivinhar o intervalo certo. Quem pedir INTEIRAMENTE fora da janela recebe
    uma lista vazia, que é a resposta honesta.
    """
    if identidade is None or identidade.e_admin:
        return de, ate

    from src.utils.acesso import janela_da_agenda

    inicio, fim = janela_da_agenda(identidade)

    pedido_de = _para_data(de) or inicio
    pedido_ate = _para_data(ate) or fim

    return (
        max(pedido_de, inicio).isoformat(),
        min(pedido_ate, fim).isoformat(),
    )
