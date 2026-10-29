# -*- coding: utf-8 -*-
"""Cobrança do check-in de autoatendimento (PRD 026), independente de provedor.

O check-in fala só com esta interface. Hoje há dois provedores:

- `asaas`: o de verdade (sandbox em dev, produção em prod), escolhido quando
  `ASAAS_API_KEY` está configurada;
- `simulado`: sem chave, SÓ em dev, para validar a experiência no iPad antes
  de existir conta no Asaas. A confirmação vem do endpoint `simulate`.

Fora de dev sem chave, nenhum provedor: o check-in responde que o pagamento
está indisponível em vez de fingir que cobrou.
"""
import os
from datetime import date
from typing import NamedTuple, Optional

PIX = "PIX"
CREDITO = "CREDIT_CARD"
DEBITO = "DEBIT_CARD"
DINHEIRO = "CASH"
METODOS = (PIX, CREDITO, DEBITO, DINHEIRO)
# Link de cobrança mandado pelo WhatsApp (PRD 029): a paciente escolhe a forma
# na fatura. Não é escolha do iPad, por isso fica fora de METODOS.
LINK = "LINK"
METODOS_DO_CAIXA = METODOS + (LINK,)

# Status no NOSSO vocabulário (coluna appointment_payments.status).
PENDENTE = "PENDING"
AGUARDANDO_DINHEIRO = "AWAITING_CASH"
PAGO = "PAID"
CANCELADO = "CANCELLED"
FALHOU = "FAILED"
ESTORNADO = "REFUNDED"


class PagamentoIndisponivel(Exception):
    """Nenhum provedor configurado para este stage."""


class ErroDoProvedor(Exception):
    """O provedor recusou ou não respondeu. A mensagem é para log, não para a
    paciente."""


class Pagador(NamedTuple):
    nome: str
    cpf: str
    telefone: str


class Cobranca(NamedTuple):
    id: str
    status: str
    invoice_url: Optional[str] = None
    pix_payload: Optional[str] = None


class PaymentProvider:
    nome = ""
    # Só quem não movimenta dinheiro de verdade sabe "fingir" um pagamento: o
    # simulado e o Asaas em SANDBOX (`/sandbox/payment/{id}/confirm`). É o que
    # o botão "Simular pagamento (teste)" do iPad usa em dev.
    pode_simular = False

    def simula(self, cobranca_id: str) -> None:
        raise NotImplementedError

    def cria_cobranca(self, pagador: Pagador, metodo: str, valor_cents: int,
                      vencimento: date, descricao: str, referencia: str) -> Cobranca:
        raise NotImplementedError

    def cancela(self, cobranca_id: str) -> None:
        raise NotImplementedError

    def consulta_status(self, cobranca_id: str) -> Optional[str]:
        """O status atual no NOSSO vocabulário, ou None se não der para saber."""
        raise NotImplementedError

    def recebe_em_dinheiro(self, cobranca_id: str, valor_cents: int, data: date) -> None:
        raise NotImplementedError

    def estorna(self, cobranca_id: str) -> bool:
        """Devolve ao pagador uma cobrança paga por Pix ou cartão. True quando
        o provedor recebeu o pedido mas o dono da conta ainda precisa autorizar
        (no Asaas, "ação crítica" com token): o dinheiro só sai depois disso."""
        raise NotImplementedError


def cobranca_de_teste(provider_nome: Optional[str]) -> bool:
    """A cobrança não movimenta dinheiro de verdade: simulado, ou Asaas apontado
    para o sandbox (dev). A tela marca como TESTE e oferece "Simular pagamento"."""
    if provider_nome == "simulado":
        return True
    return provider_nome == "asaas" and "sandbox" in (os.environ.get("ASAAS_BASE_URL") or "")


def provedor_ativo() -> PaymentProvider:
    if os.environ.get("ASAAS_API_KEY"):
        from src.providers.asaas_provider import AsaasProvider
        return AsaasProvider(
            api_key=os.environ["ASAAS_API_KEY"],
            base_url=os.environ.get("ASAAS_BASE_URL") or "https://api-sandbox.asaas.com",
        )
    if os.environ.get("STAGE") == "dev":
        from src.providers.simulated_payment_provider import SimulatedPaymentProvider
        return SimulatedPaymentProvider()
    raise PagamentoIndisponivel("Nenhum provedor de pagamento configurado")
