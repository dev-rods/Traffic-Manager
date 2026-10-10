# -*- coding: utf-8 -*-
"""Nível 3: o que vai para uma pessoa ANTES de o modelo ler (PRD 020 §4.3).

Risco vence confiança. Reclamação, pedido de reembolso, problema depois da
sessão, questão médica e ameaça de exposição não são assunto para o bot
decidir se responde: a decisão é de código, por lista de termos, e o modelo
nem vê a mensagem. Depender do modelo para classificar risco seria depender
dele para decidir quando não confiar nele.

Espelho de `fora_do_escopo`: lista no código, termos extras por clínica em
`clinics.bot_termos_de_risco`, texto fixo de saída, e a instrução para o
painel. A lista erra para o lado de transferir demais, de propósito; os logs
`[Risco]` medem e a lista se ajusta com dados reais.

Decisões do André (09/10/2026): pagamento (pix, parcelamento, forma de
pagamento) NÃO é risco - é FAQ. Só dinheiro que já saiu (reembolso, estorno,
"não caiu") vai a pessoa.

A regra de colisão (§3.16 da Spec): "grávida" e "medicamento" estão aqui e
no FAQ de contraindicações. Para o grupo MÉDICO, se o FAQ da clínica cobre o
assunto, vale o FAQ - a clínica escreveu a resposta. Os outros grupos não
têm colisão: "ficou com ferida depois da sessão" é problema real, mesmo que
o FAQ de contraindicações cite "feridas"; vai a pessoa sempre.
"""
import logging
import re
from typing import Dict, List, Optional, Sequence, Tuple

from src.services.bot_policy import (
    MOTIVO_AMEACA,
    MOTIVO_MEDICO,
    MOTIVO_POS_SESSAO,
    MOTIVO_RECLAMACAO,
    MOTIVO_REEMBOLSO,
)
from src.services.fora_do_escopo import _normaliza

logger = logging.getLogger(__name__)

COLUNA_DA_CLINICA = "bot_termos_de_risco"

# (motivo, regex sobre o texto normalizado, consulta canônica ao FAQ para a
# regra de colisão - só o grupo médico tem).
TERMOS: Tuple[Tuple[str, str, Optional[str]], ...] = (
    (MOTIVO_RECLAMACAO,
     r"\breclama\w*\b|\babsurd\w*\b|\bpessim\w*\b|\bhorrivel\b|\bhorrive\w*\b|\bprocon\b|"
     r"\badvogad\w*\b|\bprocess(o|ar|o judicial)\b|\breclame aqui\b|\bvergonh\w*\b|\bdesrespeit\w*\b",
     None),
    (MOTIVO_REEMBOLSO,
     r"\breembols\w*\b|\bestorn\w*\b|\bdevolv\w* (o |meu )?dinheiro\b|\bdinheiro de volta\b|"
     r"\bcancelar? (o |meu )?pagamento\b|"
     r"\bnao caiu\b|\bcobra(ram|do|da|nca) (errad|dupl|duas vezes|em dobro)\w*\b|\bcobranca indevida\b",
     None),
    (MOTIVO_POS_SESSAO,
     r"\bqueim\w*\b|\bbolha\w*\b|\bmancha\w*\b|\bferid\w*\b|\binflam\w*\b|\balerg\w*\b|"
     r"\bdoendo muito\b|\bardendo\b|\bardeu\b|\bvermelh\w* (demais|muito|ainda)\b|\bcicatriz\w*\b",
     None),
    (MOTIVO_MEDICO,
     r"\bremedio\w*\b|\bmedicament\w*\b|\bgravid\w*\b|\bgestante\w*\b|\bamament\w*\b|"
     r"\broacutan\b|\bisotretino\w*\b|\banticoagulante\w*\b|\bantibiotic\w*\b|\bquimioterap\w*\b|"
     r"\bepilep\w*\b|\blupus\b|\bdiabet\w*\b|\bmarcapasso\b",
     "gestante lactante gravidez medicamentos roacutan isotretinoina anticoagulante contraindicacoes"),
    (MOTIVO_AMEACA,
     r"\bvou (te )?(expor|denunciar|postar|publicar|processar)\b|\bvou (colocar|botar|jogar) (no|na) (instagram|internet|rede)\w*\b",
     None),
)

_COMPILADOS = tuple((motivo, re.compile(padrao), consulta) for motivo, padrao, consulta in TERMOS)

# A ordem importa: ameaça e reclamação antes de médico. "Vou processar porque
# fiquei com queimadura" é reclamação, não dúvida médica.
_ORDEM = (MOTIVO_AMEACA, MOTIVO_RECLAMACAO, MOTIVO_REEMBOLSO, MOTIVO_POS_SESSAO, MOTIVO_MEDICO)


def _extras(clinic: Optional[Dict]) -> List[tuple]:
    """Os termos que a clínica acrescentou (texto, não regex), como motivo de
    reclamação - é o grupo mais genérico. Termo inválido é ignorado com log."""
    termos = (clinic or {}).get(COLUNA_DA_CLINICA) or []
    compilados = []
    for termo in termos:
        texto = _normaliza(str(termo)).strip()
        if not texto:
            continue
        try:
            compilados.append((MOTIVO_RECLAMACAO, re.compile(rf"\b{re.escape(texto)}\b"), None))
        except re.error as e:
            logger.warning(f"[Risco] termo inválido {termo!r}: {e}")
    return compilados


def detecta(texto: str, clinic: Optional[Dict] = None) -> Optional[Tuple[str, Optional[str]]]:
    """(motivo, consulta_ao_faq) se a mensagem casa um termo de risco; None se
    não. `consulta_ao_faq` só vem no grupo médico: é o que o chamador usa para
    a regra de colisão (se o FAQ cobre, vale o FAQ)."""
    if not texto:
        return None
    limpo = _normaliza(texto)
    casados = {}
    for motivo, padrao, consulta in tuple(_COMPILADOS) + tuple(_extras(clinic)):
        if motivo not in casados and padrao.search(limpo):
            casados[motivo] = consulta
    for motivo in _ORDEM:
        if motivo in casados:
            return motivo, casados[motivo]
    return None


def termos_da_clinica(clinic: Optional[Dict]) -> Sequence[str]:
    """Os termos extras configurados, para a tela de configuração mostrar."""
    return (clinic or {}).get(COLUNA_DA_CLINICA) or []
