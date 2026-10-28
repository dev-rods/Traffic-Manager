# -*- coding: utf-8 -*-
"""Asaas, API v3 (https://docs.asaas.com).

Decisões que a API impõe:

- Débito: a API não cria cobrança de débito. A cobrança de cartão
  (`CREDIT_CARD`) abre a fatura hospedada (`invoiceUrl`), e é a fatura que
  oferece crédito E débito. Crédito e débito viram a mesma cobrança aqui;
  o método que a paciente escolheu fica no nosso registro.
- Dinheiro: cobrança `UNDEFINED` que a recepção baixa com `receiveInCash`
  quando recebe. O Asaas não movimenta saldo nesse caso, só registra.
- Cliente: o Asaas exige um cliente com CPF. Reaproveitamos pelo CPF antes de
  criar, para não duplicar a pessoa a cada visita. `notificationDisabled`:
  quem fala com a paciente é a clínica, pelo WhatsApp, não o Asaas por e-mail.
"""
import logging
from datetime import date
from typing import Any, Dict, Optional

import requests

from src.providers.payment_provider import (
    CANCELADO, CREDITO, DEBITO, DINHEIRO, ESTORNADO, PAGO, PENDENTE, PIX,
    Cobranca, ErroDoProvedor, Pagador, PaymentProvider,
)

logger = logging.getLogger(__name__)

TIPO_DE_COBRANCA = {PIX: "PIX", CREDITO: "CREDIT_CARD", DEBITO: "CREDIT_CARD", DINHEIRO: "UNDEFINED"}

STATUS = {
    "RECEIVED": PAGO,
    "CONFIRMED": PAGO,
    "RECEIVED_IN_CASH": PAGO,
    "REFUNDED": ESTORNADO,
    "DELETED": CANCELADO,
    "PENDING": PENDENTE,
    "OVERDUE": PENDENTE,
}

TIMEOUT = 15


def status_do_asaas(status: Optional[str]) -> Optional[str]:
    return STATUS.get(status or "")


class AsaasProvider(PaymentProvider):
    nome = "asaas"

    def __init__(self, api_key: str, base_url: str):
        # Sandbox confirma pagamento de teste por API; produção, nunca.
        self.pode_simular = "sandbox" in base_url
        self.base_url = base_url.rstrip("/") + "/v3"
        self.headers = {"access_token": api_key, "Content-Type": "application/json",
                        "User-Agent": "clinic-scheduler"}

    def _chama(self, metodo: str, caminho: str, **kwargs) -> Dict[str, Any]:
        try:
            resp = requests.request(metodo, self.base_url + caminho, headers=self.headers,
                                    timeout=TIMEOUT, **kwargs)
        except requests.RequestException as e:
            raise ErroDoProvedor(f"Asaas sem resposta em {metodo} {caminho}: {e}")
        if resp.status_code >= 400:
            # O corpo do erro do Asaas traz `errors[].description`, que é o que
            # explica a recusa. Vai para o log, nunca para a tela.
            raise ErroDoProvedor(f"Asaas {resp.status_code} em {metodo} {caminho}: {resp.text[:500]}")
        return resp.json() if resp.content else {}

    def _cliente(self, pagador: Pagador) -> str:
        achados = self._chama("GET", "/customers", params={"cpfCnpj": pagador.cpf}).get("data") or []
        if achados:
            return achados[0]["id"]
        criado = self._chama("POST", "/customers", json={
            "name": pagador.nome,
            "cpfCnpj": pagador.cpf,
            "mobilePhone": pagador.telefone[-11:],
            "notificationDisabled": True,
        })
        return criado["id"]

    def cria_cobranca(self, pagador: Pagador, metodo: str, valor_cents: int,
                      vencimento: date, descricao: str, referencia: str) -> Cobranca:
        cobranca = self._chama("POST", "/payments", json={
            "customer": self._cliente(pagador),
            "billingType": TIPO_DE_COBRANCA[metodo],
            "value": round(valor_cents / 100, 2),
            "dueDate": vencimento.isoformat(),
            "description": descricao[:500],
            "externalReference": referencia,
        })
        pix_payload = None
        if metodo == PIX:
            try:
                pix_payload = self._chama("GET", f"/payments/{cobranca['id']}/pixQrCode").get("payload")
            except ErroDoProvedor:
                try:
                    self.cancela(cobranca["id"])
                except ErroDoProvedor as e:
                    logger.error(f"[Asaas] cobrança {cobranca['id']} ficou viva sem QR do Pix: {e}")
                raise
        return Cobranca(
            id=cobranca["id"],
            status=status_do_asaas(cobranca.get("status")) or PENDENTE,
            invoice_url=cobranca.get("invoiceUrl"),
            pix_payload=pix_payload,
        )

    def cancela(self, cobranca_id: str) -> None:
        self._chama("DELETE", f"/payments/{cobranca_id}")

    def consulta_status(self, cobranca_id: str) -> Optional[str]:
        return status_do_asaas(self._chama("GET", f"/payments/{cobranca_id}").get("status"))

    def recebe_em_dinheiro(self, cobranca_id: str, valor_cents: int, data: date) -> None:
        self._chama("POST", f"/payments/{cobranca_id}/receiveInCash", json={
            "paymentDate": data.isoformat(),
            "value": round(valor_cents / 100, 2),
            "notifyCustomer": False,
        })

    def simula(self, cobranca_id: str) -> None:
        """Confirma uma cobrança no SANDBOX, como se a paciente tivesse pago.
        O Asaas avisa pelo webhook (`PAYMENT_RECEIVED`), como num pagamento real."""
        if not self.pode_simular:
            raise ErroDoProvedor("Simular pagamento só existe no sandbox do Asaas")
        self._chama("POST", f"/sandbox/payment/{cobranca_id}/confirm")
