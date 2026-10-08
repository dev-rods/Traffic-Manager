import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

VERCEL_API_BASE = "https://api.vercel.com"


class VercelDomainError(Exception):
    pass


class VercelDomainService:
    """Liga/desliga o domínio customizado de uma clínica no projeto Vercel do
    booking-site.

    Só existe porque o booking-site é um projeto só, multi-tenant por
    clinic_id na URL — colocar um domínio próprio da clínica nele é uma
    chamada à API de domínios da Vercel, não infra nova. Nenhum recurso de
    CloudFormation é criado por isto: é uma chamada HTTP de dentro de um
    Lambda que já existe (UpdateClinic).
    """

    def __init__(self):
        self.token = os.environ.get("VERCEL_API_TOKEN", "")
        self.team_id = os.environ.get("VERCEL_TEAM_ID", "")
        self.project_id = os.environ.get("BOOKING_SITE_VERCEL_PROJECT_ID", "")

    @property
    def configured(self) -> bool:
        return bool(self.token and self.team_id and self.project_id)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _params(self) -> Dict[str, str]:
        return {"teamId": self.team_id} if self.team_id else {}

    def add_domain(self, domain: str) -> Dict[str, Any]:
        """Registra `domain` no projeto. Idempotente: a Vercel devolve 200 com
        os mesmos dados se o domínio já pertence a este projeto."""
        if not self.configured:
            raise VercelDomainError("Integração com a Vercel não configurada (VERCEL_API_TOKEN ausente)")

        url = f"{VERCEL_API_BASE}/v10/projects/{self.project_id}/domains"
        resp = requests.post(url, json={"name": domain}, headers=self._headers(), params=self._params(), timeout=15)

        if resp.status_code not in (200, 201):
            data = resp.json() if resp.content else {}
            code = (data.get("error") or {}).get("code")
            # domain_already_in_use com o MESMO projeto não é erro - é o estado
            # que já queremos. Só falha de verdade se for outro dono.
            if code == "domain_already_in_use":
                existing = self.get_domain(domain)
                if existing and existing.get("projectId") == self.project_id:
                    return existing
            raise VercelDomainError(f"Vercel recusou adicionar o domínio: {resp.status_code} {data}")

        return resp.json()

    def remove_domain(self, domain: str) -> None:
        if not self.configured:
            raise VercelDomainError("Integração com a Vercel não configurada (VERCEL_API_TOKEN ausente)")

        url = f"{VERCEL_API_BASE}/v9/projects/{self.project_id}/domains/{domain}"
        resp = requests.delete(url, headers=self._headers(), params=self._params(), timeout=15)

        # 404 = já não está la. Mesmo resultado que queríamos.
        if resp.status_code not in (200, 404):
            data = resp.json() if resp.content else {}
            raise VercelDomainError(f"Vercel recusou remover o domínio: {resp.status_code} {data}")

    def get_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        if not self.configured:
            return None

        url = f"{VERCEL_API_BASE}/v9/projects/{self.project_id}/domains/{domain}"
        resp = requests.get(url, headers=self._headers(), params=self._params(), timeout=15)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            logger.error(f"[VercelDomainService] Erro ao consultar domínio {domain}: {resp.status_code} {resp.text}")
            return None
        return resp.json()

    def get_domain_status(self, domain: str) -> Dict[str, Any]:
        """Status pronto pro painel mostrar: verificado ou não, e o(s)
        registro(s) de DNS que faltam, numa forma que o front só precisa
        renderizar - sem conhecer o formato da API da Vercel."""
        info = self.get_domain(domain)
        if not info:
            return {"registered": False, "verified": False, "dns_records": []}

        verified = bool(info.get("verified"))
        dns_records = []

        if not verified:
            for challenge in info.get("verification") or []:
                dns_records.append({
                    "type": challenge.get("type"),
                    "name": challenge.get("domain", domain),
                    "value": challenge.get("value"),
                })
        else:
            # Verificado, mas o painel ainda precisa saber ONDE apontar o
            # DNS: apex usa registro A, subdomínio usa CNAME.
            is_apex = domain.count(".") <= 1
            if is_apex:
                dns_records.append({"type": "A", "name": "@", "value": "76.76.21.21"})
            else:
                subdomain = domain.split(".")[0]
                dns_records.append({"type": "CNAME", "name": subdomain, "value": "cname.vercel-dns.com"})

        return {"registered": True, "verified": verified, "dns_records": dns_records}
