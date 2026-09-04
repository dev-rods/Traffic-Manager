# -*- coding: utf-8 -*-
"""A role da Lambda permite tudo que o código do webhook chama no DynamoDB.

Em 04/09/2026 o agrupamento de rajada subiu para produção sem
`dynamodb:UpdateItem` na role. Nada acusou: 426 testes verdes, `serverless
deploy` com exit 0, e o recurso simplesmente não funcionava - caía no fallback
e o bot respondia mensagem por mensagem, como antes.

Permissão não é coisa que teste unitário veja, porque o dublê de tabela não tem
IAM. O que dá para conferir é a coerência entre as duas fontes: o método que o
código chama e a ação que o interface.yml declara. Elas divergem em silêncio, e
essa é exatamente a classe de falha que já custou caro nesta base.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "sls" / "functions" / "webhook" / "interface.yml"

# Módulos que rodam dentro da WhatsAppWebhook e falam com o DynamoDB.
MODULOS = [
    RAIZ / "src" / "functions" / "webhook" / "handler.py",
    RAIZ / "src" / "services" / "agregador_de_mensagens.py",
    RAIZ / "src" / "services" / "session_store.py",
]

ACAO_DO_METODO = {
    "get_item": "dynamodb:GetItem",
    "put_item": "dynamodb:PutItem",
    "update_item": "dynamodb:UpdateItem",
    "delete_item": "dynamodb:DeleteItem",
    "query": "dynamodb:Query",
    "scan": "dynamodb:Scan",
}

_CHAMADA = re.compile(r"\.(get_item|put_item|update_item|delete_item|query|scan)\s*\(")


def metodos_usados():
    achados = {}
    for caminho in MODULOS:
        texto = caminho.read_text(encoding="utf-8")
        for metodo in set(_CHAMADA.findall(texto)):
            achados.setdefault(metodo, []).append(caminho.name)
    return achados


def acoes_declaradas():
    """As ações dentro do bloco WhatsAppWebhook do interface.yml.

    O arquivo declara várias funções; ler o arquivo inteiro faria o teste passar
    com a permissão na função errada.
    """
    texto = INTERFACE.read_text(encoding="utf-8")
    inicio = texto.index("WhatsAppWebhook:")
    # A próxima função começa em coluna zero.
    resto = texto[inicio + len("WhatsAppWebhook:"):]
    fim = re.search(r"^\S", resto, re.MULTILINE)
    bloco = resto[: fim.start()] if fim else resto
    return set(re.findall(r"-\s+(dynamodb:\w+)", bloco))


class TestPermissoesDoWebhook(unittest.TestCase):
    def test_toda_chamada_ao_dynamo_tem_permissao(self):
        declaradas = acoes_declaradas()

        for metodo, arquivos in sorted(metodos_usados().items()):
            acao = ACAO_DO_METODO[metodo]
            with self.subTest(metodo=metodo):
                self.assertIn(
                    acao, declaradas,
                    f"{metodo}() é chamado em {', '.join(sorted(set(arquivos)))} "
                    f"mas {acao} não está na role da WhatsAppWebhook. "
                    f"Em produção isso é AccessDeniedException, não erro de teste.",
                )

    def test_o_agregador_precisa_de_update_e_delete(self):
        """Prende as duas que faltaram, por nome.

        O balde faz append com UpdateItem atômico e drena com DeleteItem
        condicionado à versão - as duas são o mecanismo, não detalhe.
        """
        declaradas = acoes_declaradas()

        self.assertIn("dynamodb:UpdateItem", declaradas)
        self.assertIn("dynamodb:DeleteItem", declaradas)

    def test_o_scanner_realmente_acha_chamada(self):
        """Se o regex parasse de casar, o teste acima passaria vazio e não
        provaria nada - é o modo de falha que já apareceu duas vezes aqui."""
        usados = metodos_usados()

        self.assertIn("update_item", usados)
        self.assertIn("delete_item", usados)
        self.assertGreaterEqual(len(usados), 4)

    def test_o_bloco_lido_e_so_o_da_webhook(self):
        """Ler o arquivo inteiro faria a permissão de outra função valer aqui."""
        texto = INTERFACE.read_text(encoding="utf-8")

        self.assertIn("WhatsAppStatusWebhook:", texto)
        self.assertNotIn("WhatsAppStatusWebhook", _bloco_da_webhook())


def _bloco_da_webhook():
    texto = INTERFACE.read_text(encoding="utf-8")
    inicio = texto.index("WhatsAppWebhook:")
    resto = texto[inicio + len("WhatsAppWebhook:"):]
    fim = re.search(r"^\S", resto, re.MULTILINE)
    return resto[: fim.start()] if fim else resto


if __name__ == "__main__":
    unittest.main()
