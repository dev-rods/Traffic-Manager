# -*- coding: utf-8 -*-
"""A conversa de um lead, lida do MessageEvents (PRD 057).

E a unica fonte que tem DIRECAO e TEXTO: o espelho do z-api so diz que existe
conversa. Inclui o que a atendente manda pelo celular (chega como fromMe, autor
HUMANO). Retencao de 60 dias (PRD 022): conversa mais antiga nao esta aqui.

O OUTBOUND carrega o AUTOR (BOT, HUMANO, SISTEMA; PRD 034). A direcao decide
quem falou por ultimo; o autor so entra para saber se UMA PESSOA respondeu
depois de o bot pedir ajuda (PRD 058).

Uma query por variante do numero (com e sem o nono digito), unidas e ordenadas.
A chave e `pk = CLINIC#{clinic}#PHONE#{telefone}`, `sk = MSG#<iso>#<id>`; os
itens `STATUS#` ficam de fora pela propria condicao de chave, nao por filtro,
porque o Limit do DynamoDB corta antes do filtro.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from boto3.dynamodb.conditions import Key

from src.services.autoria_mensagem import HUMANO, autor_da_mensagem
from src.utils.phone import variantes_do_numero

logger = logging.getLogger(__name__)

NOS = "NOS"
LEAD = "LEAD"
_DIRECAO = {"OUTBOUND": NOS, "INBOUND": LEAD}
LIMITE_PADRAO = 40


@dataclass(frozen=True)
class Mensagem:
    de: str            # LEAD | NOS
    em: datetime       # UTC
    texto: str
    autor: Optional[str] = None   # BOT | HUMANO | SISTEMA para NOS; None para LEAD


def _quando(item: Dict) -> Optional[datetime]:
    bruto = str(item.get("createdAt") or "")
    for formato in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(bruto, formato).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def ultimas_mensagens(tabela, clinic_id: str, phone: str, limite: int = LIMITE_PADRAO) -> List[Mensagem]:
    """As ultimas `limite` mensagens, da mais antiga para a mais nova."""
    encontradas = []  # type: List[Mensagem]
    for variante in sorted(variantes_do_numero(phone)):
        pk = "CLINIC#{}#PHONE#{}".format(clinic_id, variante)
        try:
            resposta = tabela.query(
                KeyConditionExpression=Key("pk").eq(pk) & Key("sk").begins_with("MSG#"),
                ScanIndexForward=False,
                Limit=limite,
            )
        except Exception as e:
            logger.error("[Transcricao] query falhou para {}: {}".format(pk, e))
            continue
        for item in resposta.get("Items", []):
            de = _DIRECAO.get(item.get("direction"))
            em = _quando(item)
            if de and em:
                encontradas.append(Mensagem(de, em, str(item.get("content") or ""), autor_da_mensagem(item)))
    encontradas.sort(key=lambda m: m.em)
    return encontradas[-limite:]


def resumo(mensagens: List[Mensagem]) -> Dict:
    if not mensagens:
        return {"ultima_de": None, "ultima_em": None, "lead_ja_falou": False, "ultima_fala_humana_em": None}
    ultima = mensagens[-1]
    humanas = [m.em for m in mensagens if m.autor == HUMANO]
    return {"ultima_de": ultima.de, "ultima_em": ultima.em,
            "lead_ja_falou": any(m.de == LEAD for m in mensagens),
            "ultima_fala_humana_em": max(humanas) if humanas else None}
