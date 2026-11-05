# -*- coding: utf-8 -*-
"""ClickSign, API v3 (https://developers.clicksign.com).

A API é JSON:API: todo corpo é `{"data": {"type": ..., "attributes": ...}}`.
Criar um termo é uma sequência de cinco chamadas, que a API impõe:

1. envelope (a "pasta" do processo);
2. documento gerado do MODELO `.docx` com as variáveis (`template.data`);
3. signatário (nome, e-mail, celular, CPF, nascimento);
4. requisitos: qualificação (`agree`/`sign`) e as evidências de
   `REQUISITOS_DE_EVIDENCIA` (`whatsapp` e `handwritten`);
5. ativação (`status: running`).

Se qualquer passo depois do 1 falhar, o envelope é cancelado antes de relançar:
nunca sobra envelope ativo que o nosso banco não conhece.

Decisões que a API impõe:

- O widget embedded carrega pelo ID do signatário, no `widget_endpoint`
  (sandbox ou produção, sem `/api/v3`).
- URLs de download valem 5 minutos: `baixa_pdf` busca a URL e baixa na hora.
- O log de auditoria vem nas páginas finais do PDF assinado; o `.zip`
  (original + assinado) é opcional.
- Não há "simular": no sandbox se assina de verdade. `pode_simular` é False.
- Não há cancelamento de envelope ATIVO no v3 (conferido no sandbox em
  03/11/2026: `PATCH status` só aceita draft/running, DELETE só em draft).
  Um envelope abandonado morre pelo `deadline_at`, e
  `deadline_partial_signature_action: canceled` garante que, vencido sem
  assinatura, ele fica `canceled`, nunca `closed`. Assim `closed` significa
  assinado.
- O arquivo assinado vem em `links.files.signed` do documento (o original em
  `links.files.original`); a doc antiga fala em `signed_file_url`. Lemos os
  dois.
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests

from src.providers.signature_provider import (
    ASSINADO, ASSINANDO, CANCELADO, EXPIRADO, ErroDoProvedor, Signatario, SignatureProvider,
    TermoCriado,
)

logger = logging.getLogger(__name__)

TIMEOUT = 20
# O documento gerado do modelo é processado DEPOIS de criado (o `modified`
# muda ~9 s depois do `created`, medido em 05/11/2026). O widget aberto antes
# disso mostra o termo quebrado. `cria_termo` espera até aqui.
ESPERA_DOCUMENTO_S = 20
# O que a signatária prova dentro do widget: token no WhatsApp e assinatura
# desenhada na tela (decisão 2 do PRD 036). O widget embedded do v3 carrega
# pelo id do signatário SEM `embedded_signature`: conferido em 05/11/2026 num
# Chromium headless (documento renderizado, botão "Assinar"). Com
# `embedded_signature` o widget da ClickSign quebra com "ERRO 500" na tela,
# e a API recusa combiná-lo com qualquer outra evidência. Registrado em
# tests/integration/036-termo-de-consentimento.md.
REQUISITOS_DE_EVIDENCIA = ("whatsapp", "handwritten")

STATUS = {
    "running": ASSINANDO,
    "draft": ASSINANDO,
    "closed": ASSINADO,
    "canceled": CANCELADO,
    "cancelled": CANCELADO,
}


def _formata_cpf(digitos: str) -> str:
    return "{}.{}.{}-{}".format(digitos[:3], digitos[3:6], digitos[6:9], digitos[9:])


def _celular_nacional(telefone: str) -> str:
    """A ClickSign quer DDD + número (10 ou 11 dígitos), sem o 55."""
    digitos = "".join(ch for ch in telefone if ch.isdigit())
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    return digitos


def _rfc3339(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


class ClicksignProvider(SignatureProvider):
    nome = "clicksign"
    pode_simular = False

    def __init__(self, api_key: str, base_url: str):
        self.widget_endpoint = base_url.rstrip("/")
        self.base_url = self.widget_endpoint + "/api/v3"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
            "User-Agent": "clinic-scheduler",
        }

    # -- HTTP ---------------------------------------------------------------

    def _chama(self, metodo: str, caminho: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            resp = requests.request(metodo, self.base_url + caminho, headers=self.headers,
                                    json=payload, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise ErroDoProvedor("ClickSign sem resposta em {} {}: {}".format(metodo, caminho, e))
        if resp.status_code >= 400:
            # `errors[].detail` é o que explica a recusa. Log, nunca tela.
            raise ErroDoProvedor("ClickSign {} em {} {}: {}".format(
                resp.status_code, metodo, caminho, resp.text[:500]))
        return resp.json() if resp.content else {}

    def _baixa(self, url: str) -> bytes:
        try:
            resp = requests.get(url, timeout=60)
        except requests.RequestException as e:
            raise ErroDoProvedor("ClickSign: download falhou: {}".format(e))
        if resp.status_code >= 400:
            raise ErroDoProvedor("ClickSign: download respondeu {}".format(resp.status_code))
        return resp.content

    @staticmethod
    def _dado(tipo: str, atributos: Dict[str, Any],
              relacoes: Optional[Dict[str, Tuple[str, str]]] = None) -> Dict[str, Any]:
        dado = {"type": tipo, "attributes": atributos}  # type: Dict[str, Any]
        if relacoes:
            dado["relationships"] = {
                nome: {"data": {"type": tipo_rel, "id": id_rel}}
                for nome, (tipo_rel, id_rel) in relacoes.items()
            }
        return {"data": dado}

    # -- Interface ----------------------------------------------------------

    def cria_termo(self, template_key: str, filename: str, dados: Dict[str, str],
                   signatario: Signatario, referencia: str, prazo: datetime) -> TermoCriado:
        envelope = self._chama("POST", "/envelopes", self._dado("envelopes", {
            "name": "TCLE {}".format(referencia)[:255],
            "locale": "pt-BR",
            "auto_close": True,
            "remind_interval": None,
            "block_after_refusal": True,
            "deadline_at": _rfc3339(prazo),
            # Vencido sem assinatura: cancelado, não fechado (ver docstring).
            "deadline_partial_signature_action": "canceled",
        }))
        envelope_id = envelope["data"]["id"]
        try:
            documento = self._chama("POST", "/envelopes/{}/documents".format(envelope_id),
                                    self._dado("documents", {
                                        "filename": filename,
                                        "template": {"key": template_key, "data": dados},
                                        "metadata": {"referencia": referencia},
                                    }))
            document_id = documento["data"]["id"]

            signer = self._chama("POST", "/envelopes/{}/signers".format(envelope_id),
                                 self._dado("signers", {
                                     "name": signatario.nome,
                                     "email": signatario.email,
                                     "phone_number": _celular_nacional(signatario.telefone),
                                     "has_documentation": True,
                                     "documentation": _formata_cpf(signatario.cpf),
                                     "birthday": signatario.nascimento.isoformat(),
                                     # Convite e lembrete não: a assinatura é no iPad, agora.
                                     # A cópia assinada vai por e-mail (decisão 8 do PRD).
                                     "communicate_events": {
                                         "signature_request": "none",
                                         "signature_reminder": "none",
                                         "document_signed": "email",
                                     },
                                 }))
            signer_id = signer["data"]["id"]

            relacoes = {"document": ("documents", document_id), "signer": ("signers", signer_id)}
            self._chama("POST", "/envelopes/{}/requirements".format(envelope_id),
                        self._dado("requirements", {"action": "agree", "role": "sign"}, relacoes))
            for auth in REQUISITOS_DE_EVIDENCIA:
                self._chama("POST", "/envelopes/{}/requirements".format(envelope_id),
                            self._dado("requirements", {"action": "provide_evidence", "auth": auth}, relacoes))

            self._chama("PATCH", "/envelopes/{}".format(envelope_id),
                        {"data": {"id": envelope_id, "type": "envelopes", "attributes": {"status": "running"}}})
        except ErroDoProvedor:
            try:
                self.cancela(envelope_id)
            except ErroDoProvedor as e:
                logger.error("[ClicksignProvider] envelope {} ficou sem cancelar: {}".format(envelope_id, e))
            raise
        self._espera_documento(envelope_id, document_id)
        return TermoCriado(envelope_id, document_id, signer_id)

    def _espera_documento(self, envelope_id: str, document_id: str) -> None:
        """Bloqueia até o documento ter sido processado (`modified` depois de
        `created`) ou até `ESPERA_DOCUMENTO_S`. Nunca falha: no pior caso o
        widget abre um pouco antes, como abriria sem a espera."""
        limite = time.monotonic() + ESPERA_DOCUMENTO_S
        while True:
            try:
                atributos = self._chama("GET", "/envelopes/{}/documents/{}".format(envelope_id, document_id))                     .get("data", {}).get("attributes", {})
            except ErroDoProvedor as e:
                logger.warning("[ClicksignProvider] espera do documento {}: {}".format(document_id, e))
                return
            criado, modificado = atributos.get("created"), atributos.get("modified")
            if criado and modificado and modificado != criado:
                return
            if time.monotonic() >= limite:
                logger.warning("[ClicksignProvider] documento {} ainda em processamento após {}s".format(
                    document_id, ESPERA_DOCUMENTO_S))
                return
            time.sleep(1)

    def consulta(self, envelope_id: str) -> str:
        atributos = self._chama("GET", "/envelopes/{}".format(envelope_id)).get("data", {}).get("attributes", {})
        estado = STATUS.get(str(atributos.get("status") or "").lower(), ASSINANDO)
        if estado == ASSINANDO and _venceu(atributos.get("deadline_at")):
            return EXPIRADO
        return estado

    def _downloads(self, envelope_id: str, document_id: str) -> Dict[str, Any]:
        dado = self._chama("GET", "/envelopes/{}/documents/{}".format(envelope_id, document_id)).get("data", {})
        atributos = dado.get("attributes") or {}
        arquivos = (dado.get("links") or {}).get("files") or {}
        downloads = atributos.get("downloads") or {}
        return {
            "signed": arquivos.get("signed") or downloads.get("signed_file_url") or downloads.get("signed")
            or atributos.get("signed_file_url"),
            "zip": arquivos.get("zip") or downloads.get("ziped_file_url") or downloads.get("zip")
            or atributos.get("ziped_file_url"),
        }

    def baixa_pdf(self, envelope_id: str, document_id: str) -> bytes:
        url = self._downloads(envelope_id, document_id)["signed"]
        if not url:
            raise ErroDoProvedor("ClickSign: documento {} ainda sem PDF assinado".format(document_id))
        return self._baixa(url)

    def baixa_zip(self, envelope_id: str, document_id: str) -> Optional[bytes]:
        url = self._downloads(envelope_id, document_id)["zip"]
        return self._baixa(url) if url else None

    def cancela(self, envelope_id: str) -> None:
        """Apaga o envelope se ainda estiver em draft (falha antes de ativar).
        Ativo, a API não cancela: fica para o `deadline_at` cancelar sozinho,
        e isto é só um log."""
        try:
            self._chama("DELETE", "/envelopes/{}".format(envelope_id))
        except ErroDoProvedor as e:
            if "ClickSign 4" not in str(e):
                raise
            logger.info("[ClicksignProvider] envelope {} não apagado (ativo ou já encerrado); "
                        "vence pelo prazo: {}".format(envelope_id, str(e)[:160]))

    def simula(self, envelope_id: str) -> None:
        raise ErroDoProvedor("A ClickSign não simula assinatura; no sandbox assina-se pelo widget")


def _venceu(deadline: Optional[str]) -> bool:
    if not deadline:
        return False
    try:
        limite = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
    except ValueError:
        return False
    agora = datetime.now(limite.tzinfo) if limite.tzinfo else datetime.now()
    return agora > limite
