# -*- coding: utf-8 -*-
"""O stack não pode voltar a estourar o limite do CloudFormation.

Em 05/09/2026 adicionar UMA Lambda quebrou o deploy: "Number of resources, 502,
is greater than maximum allowed, 500". Cada função carregava um
`AWS::Lambda::Version` que nada referencia - o projeto não usa alias nem
provisioned concurrency. Desligar a publicação de versão liberou 65 recursos.

Este teste não conta o template (empacotar leva 25s e depende de rede). Ele
prende a decisão: se alguém reativar o versionamento, o deploy volta a quebrar,
e o erro aparece no CloudFormation em vez de aqui.
"""
import re
import unittest
from pathlib import Path

SERVERLESS = Path(__file__).resolve().parents[2] / "serverless.yml"


class TestVersionamentoDesligado(unittest.TestCase):
    def test_version_functions_continua_falso(self):
        texto = SERVERLESS.read_text(encoding="utf-8")

        self.assertRegex(
            texto, r"(?m)^\s*versionFunctions:\s*false\s*$",
            "versionFunctions voltou a ser true: sao 65 AWS::Lambda::Version "
            "que ninguem referencia, e o stack estoura o limite de 500 recursos "
            "do CloudFormation no proximo deploy.",
        )

    def test_a_razao_esta_escrita_junto(self):
        """Sem o porquê, a próxima pessoa reativa achando que é descuido."""
        texto = SERVERLESS.read_text(encoding="utf-8")
        trecho = texto[max(0, texto.index("versionFunctions") - 900):
                       texto.index("versionFunctions")]

        self.assertIn("500", trecho)


class TestNumeroDeFuncoes(unittest.TestCase):
    """A folga é finita, e o número agora é medido, não estimado.

    Em 21/09/2026 contei os recursos do stack de produção direto no
    CloudFormation: **440 de 500**, com **74 funções**. Isso dá **~5,9 recursos
    por função** - função, log group, permission, method e resource de API
    Gateway. (A role deixou de contar: o PR #60 passou as 57 funções que tinham
    role própria a usar a compartilhada.)

    Com as 2 funções de gestão de acesso, são 76 -> ~452, e sobram ~8 funções.

    Quando essa folga acabar, o próximo movimento já está mapeado no PRD 013:
    remover os 74 log groups explícitos devolve o stack para ~366. Depois disso
    é dividir o stack (serverless-plugin-split-stacks) ou separar o serviço.
    """

    # 76 em uso + 2 de margem. Subir isto exige MEDIR de novo, e não só somar:
    #   aws cloudformation list-stack-resources --stack-name clinic-scheduler-infra-prod
    LIMITE_DE_FUNCOES = 78

    def test_cabe_no_stack(self):
        pasta = SERVERLESS.parent / "sls" / "functions"
        declaradas = sum(
            len(re.findall(r"^\s*handler:\s*src\.", arq.read_text(encoding="utf-8"), re.M))
            for arq in pasta.glob("*/interface.yml")
        )

        self.assertGreater(declaradas, 0, "o contador parou de achar funcao")
        self.assertLessEqual(
            declaradas, self.LIMITE_DE_FUNCOES,
            f"{declaradas} funcoes: perto do limite de 500 recursos do "
            f"CloudFormation. Antes de somar mais uma, dividir o stack "
            f"(serverless-plugin-split-stacks) ou separar o servico.",
        )


if __name__ == "__main__":
    unittest.main()
