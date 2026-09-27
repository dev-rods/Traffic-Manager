# -*- coding: utf-8 -*-
"""Nenhum módulo pode prender o código a uma versão da API do Google Ads.

Em 27/09/2026 `google_ads_mcc_service.py` importava assim:

    from google.ads.googleads.v20.services... import CustomerClientLinkServiceClient

Três imports, todos usados APENAS como anotação de tipo - nenhum tipo era
instanciado. E o custo foi alto: o `requirements.txt` pede o SDK 27.0.0 (que
traz v20), o ambiente local tinha o 31.2.0 (v21..v25), e o módulo inteiro
deixava de carregar fora da Lambda. Nem as funções que não têm nada a ver com
link de MCC.

O problema maior é o futuro: o Google descontinua versões da API com o tempo.
Quando v20 sair do ar e alguém atualizar o SDK, isto quebra no import - e o
erro não diz "sua versão da API morreu", diz `ModuleNotFoundError`.

`client.get_service(...)` e `client.get_type(...)` resolvem a versão a partir
do SDK instalado. É o caminho que a documentação do Google recomenda, e o que
o resto do projeto já usava.
"""
import ast
import os
import unittest

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "src")


def _imports_com_versao(caminho):
    """Linhas que importam de `google.ads.googleads.vNN`."""
    with open(caminho, encoding="utf-8") as f:
        arvore = ast.parse(f.read(), filename=caminho)

    achados = []
    for no in ast.walk(arvore):
        modulo = None
        if isinstance(no, ast.ImportFrom):
            modulo = no.module or ""
        elif isinstance(no, ast.Import):
            modulo = " ".join(a.name for a in no.names)
        if not modulo:
            continue

        for parte in modulo.split("."):
            # `v20`, `v21`... mas não `versions` nem `v` sozinho.
            if (len(parte) >= 2 and parte[0] == "v" and parte[1:].isdigit()
                    and "googleads" in modulo):
                achados.append((no.lineno, modulo))
                break
    return achados


def _todos_os_fontes():
    for raiz, _, arquivos in os.walk(RAIZ):
        for arquivo in arquivos:
            if arquivo.endswith(".py"):
                yield os.path.join(raiz, arquivo)


class TestNenhumaVersaoFixa(unittest.TestCase):
    def test_nenhum_modulo_importa_versao_especifica(self):
        presos = []
        for caminho in _todos_os_fontes():
            for linha, modulo in _imports_com_versao(caminho):
                rel = os.path.relpath(caminho, RAIZ).replace(os.sep, "/")
                presos.append("%s:%d  %s" % (rel, linha, modulo))

        self.assertEqual(presos, [], (
            "Estes imports prendem o código a uma versão da API do Google Ads. "
            "Use client.get_service(...) e client.get_type(...), que resolvem "
            "a versão a partir do SDK instalado.\n  " + "\n  ".join(presos)
        ))


class TestOServicoDeMccCarrega(unittest.TestCase):
    """O teste que teria pego o defeito: o módulo importa, no SDK que existe."""

    def test_importa_sem_estourar(self):
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        from src.services import google_ads_mcc_service

        self.assertTrue(hasattr(google_ads_mcc_service, "GoogleAdsMCCService"))

    def test_os_metodos_publicos_continuam_la(self):
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        from src.services.google_ads_mcc_service import GoogleAdsMCCService

        for metodo in ("get_mcc_client", "send_link_invitation",
                       "get_link_status", "cancel_link_invitation"):
            with self.subTest(metodo):
                self.assertTrue(callable(getattr(GoogleAdsMCCService, metodo, None)))


if __name__ == "__main__":
    unittest.main()
