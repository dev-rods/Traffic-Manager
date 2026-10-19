# -*- coding: utf-8 -*-
"""Provedor de mentira, só para dev (PRD 026).

Ainda não há conta no Asaas. Para validar o check-in no iPad com gente de
verdade, este provedor devolve um "copia e cola" e uma fatura fictícios, e
o pagamento só é confirmado pelo endpoint `simulate`, que existe apenas com
este provedor. `provedor_ativo` nunca o escolhe fora de dev.
"""
import uuid
from datetime import date
from typing import Optional

from src.providers.payment_provider import (
    AGUARDANDO_DINHEIRO, DINHEIRO, PENDENTE, PIX, Cobranca, Pagador, PaymentProvider,
)

PIX_SIMULADO = "00020126SIMULADO-NAO-PAGUE-ESTE-PIX-5204000053039865802BR6304ABCD"
FATURA_SIMULADA = "https://sandbox.asaas.com/i/simulado"


class SimulatedPaymentProvider(PaymentProvider):
    nome = "simulado"

    def cria_cobranca(self, pagador: Pagador, metodo: str, valor_cents: int,
                      vencimento: date, descricao: str, referencia: str) -> Cobranca:
        cobranca_id = f"sim_{uuid.uuid4().hex[:16]}"
        if metodo == PIX:
            return Cobranca(cobranca_id, PENDENTE, pix_payload=PIX_SIMULADO)
        if metodo == DINHEIRO:
            return Cobranca(cobranca_id, AGUARDANDO_DINHEIRO)
        return Cobranca(cobranca_id, PENDENTE, invoice_url=f"{FATURA_SIMULADA}/{cobranca_id}")

    def cancela(self, cobranca_id: str) -> None:
        return None

    def consulta_status(self, cobranca_id: str) -> Optional[str]:
        # O status do simulado mora no nosso banco; não há o que consultar.
        return None

    def recebe_em_dinheiro(self, cobranca_id: str, valor_cents: int, data: date) -> None:
        return None
