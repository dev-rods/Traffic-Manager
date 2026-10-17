# -*- coding: utf-8 -*-
"""O carrinho do site público: duração, preço e desconto, do mesmo jeito que o agente.

O site calculava duração e preço no navegador, e o backend recalculava outra
coisa ao gravar:

- a grade de horários vinha da soma crua das durações, e a criação usava piso,
  teto e passo das `duration_rules` - o site oferecia horário que a agenda
  recusava (409), ou gravava sessão maior que a janela conferida;
- o preço não passava pelos combos nem pela política de desconto - o mesmo
  pedido custava mais pelo site do que pelo WhatsApp.

Agora as três rotas públicas que precisam disso (cotação, disponibilidade e
criação) chamam este módulo, e ele chama as mesmas funções do agente, na mesma
ordem: combos -> duração -> preço -> desconto. Nenhum handler monta preço ou
duração à mão.
"""
import logging
import re
from typing import Dict, List, NamedTuple, Optional

from src.services.combos import troca_no_catalogo
from src.services.duration_rules import duracao_do_carrinho, normaliza_pares
from src.services.politica_de_desconto import Decisao, aplica_desconto, decide, preco_de_tabela
from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Um atendimento não tem 50 serviços nem 100 áreas; o limite existe para uma
# requisição maliciosa não virar uma query com milhares de parâmetros.
MAX_SERVICOS = 20
MAX_PARES = 60


class CarrinhoInvalido(ValueError):
    """O carrinho não descreve um atendimento possível nesta clínica (vira 400)."""


class Cotacao(NamedTuple):
    pares: List[Dict]
    combos: List[Dict]
    duracao_minutos: int
    original_cents: Optional[int]
    final_cents: Optional[int]
    desconto: Decisao
    qtd_areas: int


def pares_do_corpo(raw) -> List[Dict]:
    """`serviceAreaPairs` do corpo HTTP (camelCase) em `service_id`/`area_id`."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise CarrinhoInvalido("serviceAreaPairs deve ser uma lista")
    return normaliza_pares(raw)


def pares_da_query(raw: Optional[str]) -> List[Dict]:
    """`serviceAreaPairs=svc:area,svc:area` da query string."""
    pares = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        service_id, sep, area_id = item.partition(":")
        if not sep:
            raise CarrinhoInvalido("serviceAreaPairs deve ser serviceId:areaId separados por vírgula")
        pares.append({"service_id": service_id.strip(), "area_id": area_id.strip()})
    return pares


def valida_carrinho(db, clinic_id: str, service_ids, service_area_pairs: List[Dict]) -> List[str]:
    """Confere que o carrinho é desta clínica e existe. Devolve os ids limpos.

    A criação pública aceitava qualquer `serviceIds` e pares: um serviço de
    outra clínica, ou uma área desativada, entravam no agendamento sem ninguém
    conferir. Pares de serviço fora do carrinho também - e somavam preço.
    """
    if not isinstance(service_ids, list) or not service_ids:
        raise CarrinhoInvalido("serviceIds deve ser uma lista com ao menos um serviço")
    ids = list(dict.fromkeys(str(s).strip() for s in service_ids if s))
    if len(ids) > MAX_SERVICOS or len(service_area_pairs) > MAX_PARES:
        raise CarrinhoInvalido("Carrinho grande demais")
    invalidos = [i for i in ids if not _UUID.match(i)]
    invalidos += [v for p in service_area_pairs for v in (p["service_id"], p["area_id"]) if not _UUID.match(str(v))]
    if invalidos:
        raise CarrinhoInvalido("Identificador inválido no carrinho")

    placeholders = ", ".join(["%s"] * len(ids))
    servicos = db.execute_query(
        f"SELECT id FROM scheduler.services WHERE clinic_id = %s AND active = TRUE AND id::text IN ({placeholders})",
        (clinic_id, *ids),
    ) or []
    if len({str(s["id"]) for s in servicos}) != len(ids):
        raise CarrinhoInvalido("Serviço não encontrado nesta clínica")

    if service_area_pairs:
        fora = [p for p in service_area_pairs if p["service_id"] not in ids]
        if fora:
            raise CarrinhoInvalido("Área de um serviço que não está no carrinho")
        valores = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
        params: tuple = ()
        for p in service_area_pairs:
            params += (p["service_id"], p["area_id"])
        linhas = db.execute_query(
            f"""SELECT COUNT(*) AS total
            FROM (VALUES {valores}) AS pares(service_id, area_id)
            JOIN scheduler.service_areas sa
              ON sa.service_id = pares.service_id AND sa.area_id = pares.area_id AND sa.active = TRUE
            JOIN scheduler.areas a ON a.id = sa.area_id AND a.active = TRUE""",
            params,
        ) or []
        unicos = {(p["service_id"], p["area_id"]) for p in service_area_pairs}
        if len(unicos) != len(service_area_pairs) or not linhas or int(linhas[0]["total"]) != len(service_area_pairs):
            raise CarrinhoInvalido("Área de tratamento indisponível")
    return ids


def duracao(db, clinic_id: str, service_ids: List[str], service_area_pairs: List[Dict]) -> int:
    """A duração que a agenda vai gravar para este carrinho (já com combos)."""
    pares, _ = troca_no_catalogo(db, clinic_id, service_area_pairs)
    return duracao_do_carrinho(db, clinic_id, service_ids, pares)


def cota(db, clinic_id: str, service_ids: List[str], service_area_pairs: List[Dict],
         phone: Optional[str] = None) -> Cotacao:
    """Preço, desconto e duração do carrinho - o que a criação vai gravar.

    `phone` decide primeira sessão e desconto personalizado; sem ele só a faixa
    de áreas vale (é o resumo antes de o cliente digitar o celular).
    """
    pares, combos = troca_no_catalogo(db, clinic_id, service_area_pairs)
    minutos = duracao_do_carrinho(db, clinic_id, service_ids, pares)
    original = preco_de_tabela(db, service_ids, pares)
    telefone = normalize_phone(phone) if phone else None
    decisao = decide(db, clinic_id, telefone, len(pares))
    final = aplica_desconto(original, decisao.pct) if original is not None else None
    return Cotacao(
        pares=pares,
        combos=combos,
        duracao_minutos=minutos,
        original_cents=original,
        final_cents=final,
        desconto=decisao,
        qtd_areas=len(pares),
    )
