# -*- coding: utf-8 -*-
"""Assinatura eletrônica do termo de consentimento (PRD 036), independente de
provedor.

O serviço de consentimento fala só com esta interface. Há dois provedores:

- `clicksign`: o de verdade (sandbox em dev, produção em prod), escolhido
  quando `CLICKSIGN_API_KEY` está configurada;
- `simulado`: sem chave, SÓ em dev, para validar o fluxo do iPad sem conta.
  A assinatura é "concluída" pelo endpoint `simulate`, que só existe com ele.

Fora de dev sem chave, nenhum provedor: o check-in responde que a assinatura
está indisponível em vez de fingir que assinou.

Mesmo desenho de `payment_provider.py`: o provedor nunca recebe `db`, e o
serviço nunca fala HTTP.
"""
import os
from datetime import date, datetime
from typing import Dict, NamedTuple, Optional

# Estado do envelope no NOSSO vocabulário (coluna patient_consents.status).
ASSINANDO = "SIGNING"
ASSINADO = "SIGNED"
CANCELADO = "CANCELLED"
EXPIRADO = "EXPIRED"
PAPEL = "PAPER"


class AssinaturaIndisponivel(Exception):
    """Nenhum provedor configurado para este stage."""


class ErroDoProvedor(Exception):
    """O provedor recusou ou não respondeu. A mensagem é para log, não para a
    paciente."""


class Signatario(NamedTuple):
    nome: str
    cpf: str          # 11 dígitos
    nascimento: date
    telefone: str     # formato z-api, 55DDD9XXXXXXXX
    email: str


class TermoCriado(NamedTuple):
    envelope_id: str
    document_id: str
    signer_id: str


class SignatureProvider:
    nome = ""
    # Só quem não gera documento de verdade sabe "fingir" uma assinatura. A
    # ClickSign não tem isso nem no sandbox: lá se assina de verdade pelo
    # widget, com token no WhatsApp.
    pode_simular = False
    # Onde o widget embedded carrega ("https://sandbox.clicksign.com" ou
    # "https://app.clicksign.com"). Vazio no simulado: não há widget.
    widget_endpoint = ""

    def cria_termo(self, template_key: str, filename: str, dados: Dict[str, str],
                   signatario: Signatario, referencia: str, prazo: datetime) -> TermoCriado:
        """Cria e ATIVA o envelope com o documento gerado do modelo. Se falhar
        depois de criar, cancela o que criou: nunca sobra envelope ativo sem
        registro nosso."""
        raise NotImplementedError

    def consulta(self, envelope_id: str) -> str:
        """Estado atual no NOSSO vocabulário: SIGNING, SIGNED, CANCELLED ou EXPIRED."""
        raise NotImplementedError

    def baixa_pdf(self, envelope_id: str, document_id: str) -> bytes:
        """O PDF assinado, com o log de auditoria nas páginas finais."""
        raise NotImplementedError

    def baixa_zip(self, envelope_id: str, document_id: str) -> Optional[bytes]:
        """Original + assinado, quando o provedor oferecer. None se não."""
        raise NotImplementedError

    def cancela(self, envelope_id: str) -> None:
        raise NotImplementedError

    def simula(self, envelope_id: str) -> None:
        raise NotImplementedError


def termo_de_teste(provider_nome: Optional[str]) -> bool:
    """O documento não vale como termo de verdade: simulado, ou ClickSign
    apontada para o sandbox (dev). A tela marca como TESTE."""
    if provider_nome == "simulado":
        return True
    return provider_nome == "clicksign" and "sandbox" in (os.environ.get("CLICKSIGN_BASE_URL") or "")


def provedor_ativo() -> SignatureProvider:
    if os.environ.get("CLICKSIGN_API_KEY"):
        from src.providers.clicksign_provider import ClicksignProvider
        return ClicksignProvider(
            api_key=os.environ["CLICKSIGN_API_KEY"],
            base_url=os.environ.get("CLICKSIGN_BASE_URL") or "https://sandbox.clicksign.com",
        )
    if os.environ.get("STAGE") == "dev":
        from src.providers.simulated_signature_provider import SimulatedSignatureProvider
        return SimulatedSignatureProvider()
    raise AssinaturaIndisponivel("Nenhum provedor de assinatura configurado")
