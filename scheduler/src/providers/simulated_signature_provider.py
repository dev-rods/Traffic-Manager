# -*- coding: utf-8 -*-
"""Provedor de mentira, só para dev (PRD 036).

Sem chave da ClickSign em dev, o iPad mostra "Simular assinatura (teste)" no
lugar do widget, e este provedor "fecha" o envelope quando o endpoint
`simulate` chama `simula`. O PDF devolvido é um PDF mínimo gerado aqui, só
para o fluxo de guarda no S3 rodar de ponta a ponta. `provedor_ativo` nunca o
escolhe fora de dev, e o construtor recusa, por garantia dupla.

O estado vive na memória do processo (uma Lambda quente). Entre invocações
frias, um envelope "SIGNING" simulado some: `consulta` responde SIGNING para o
que não conhece, e o iPad continua esperando até o `simulate`.
"""
import os
import uuid
from datetime import datetime
from typing import Dict, Optional

from src.providers.signature_provider import (
    ASSINADO, ASSINANDO, AssinaturaIndisponivel, Signatario, SignatureProvider, TermoCriado,
)

_estado = {}  # type: Dict[str, str]
_referencias = {}  # type: Dict[str, str]


def pdf_minimo(texto: str) -> bytes:
    """Um PDF de uma página com `texto`, sem biblioteca. Serve para o S3 e
    para abrir no painel; não tem valor jurídico, e o nome já diz isso."""
    conteudo = "BT /F1 14 Tf 40 760 Td ({}) Tj ET".format(texto.replace("(", "[").replace(")", "]"))
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        "<< /Length {} >>\nstream\n{}\nendstream".format(len(conteudo), conteudo),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(saida.encode("latin-1")))
        saida += "{} 0 obj\n{}\nendobj\n".format(i, obj)
    xref = len(saida.encode("latin-1"))
    saida += "xref\n0 {}\n0000000000 65535 f \n".format(len(objetos) + 1)
    for off in offsets:
        saida += "{:010d} 00000 n \n".format(off)
    saida += "trailer\n<< /Size {} /Root 1 0 R >>\nstartxref\n{}\n%%EOF\n".format(len(objetos) + 1, xref)
    return saida.encode("latin-1")


class SimulatedSignatureProvider(SignatureProvider):
    nome = "simulado"
    pode_simular = True
    widget_endpoint = ""

    def __init__(self):
        if os.environ.get("STAGE") != "dev":
            raise AssinaturaIndisponivel("Provedor simulado de assinatura só existe em dev")

    def cria_termo(self, template_key: str, filename: str, dados: Dict[str, str],
                   signatario: Signatario, referencia: str, prazo: datetime) -> TermoCriado:
        sufixo = uuid.uuid4().hex[:16]
        envelope_id = "sim-env-{}".format(sufixo)
        _estado[envelope_id] = ASSINANDO
        _referencias[envelope_id] = referencia
        return TermoCriado(envelope_id, "sim-doc-{}".format(sufixo), "sim-signer-{}".format(sufixo))

    def consulta(self, envelope_id: str) -> str:
        return _estado.get(envelope_id, ASSINANDO)

    def baixa_pdf(self, envelope_id: str, document_id: str) -> bytes:
        return pdf_minimo("TCLE DE TESTE (simulado) - {}".format(_referencias.get(envelope_id, envelope_id)))

    def baixa_zip(self, envelope_id: str, document_id: str) -> Optional[bytes]:
        return None

    def cancela(self, envelope_id: str) -> None:
        _estado.pop(envelope_id, None)

    def simula(self, envelope_id: str) -> None:
        _estado[envelope_id] = ASSINADO
