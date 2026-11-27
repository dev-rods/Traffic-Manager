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

import yaml

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

    # Medido em 07/10/2026, DEPOIS de os 78 log groups sairem do stack
    # (sls/plugins/log-groups-fora-do-stack.js): prod em 418 de 500 com 78
    # funcoes, ~5,4 recursos por funcao. Sobram 82 recursos, ~15 funcoes.
    # 78 em uso + 2 da fase 3 (ExpiraAtendimentos, Tarefas) + margem.
    # Subir isto exige MEDIR de novo, e nao so somar:
    #   aws cloudformation list-stack-resources --stack-name clinic-scheduler-infra-prod
    # 21/11/2026 (PRD 055): o cors: true saiu das rotas e os 76 OPTIONS
    # sairam do stack. Prod e dev MEDIDOS em 418 de 500 com 86 funcoes.
    # Funcao nova com um endpoint custa ~4 (funcao, permission, resource,
    # metodo): 82 livres / 4 = 20, menos folga de ~2 funcoes. Subir isto exige
    # medir de novo:
    #   aws cloudformation list-stack-resources --stack-name clinic-scheduler-infra-prod
    # 26/11/2026 (PRD 066): +1 OPTIONS (/leads, LP da Essencia). Prod MEDIDO
    # em 430 de 500 depois do deploy (o resto do crescimento desde 21/11 veio
    # dos PRDs 057 a 062).
    LIMITE_DE_FUNCOES = 104

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


class TestCorsSoOndeChamamDeFora(unittest.TestCase):
    """CORS exatamente nas rotas chamadas de fora da Vercel (PRD 055 e 066).

    Painel, site e checkin chegam ao API Gateway por rewrite da Vercel no
    proprio dominio: sem origem cruzada, sem preflight, e cada `cors: true`
    so custaria um metodo OPTIONS no stack (eram 76 de 494).

    Quem chama do navegador em OUTRO dominio precisa do preflight. Sem ele o
    browser barra o POST antes de sair e o erro e silencioso: a LP da Essencia
    perdeu todos os leads de 21/11 a 26/11/2026 assim. Por isso a lista abaixo
    diz quem e cada excecao, e o teste confere nos dois sentidos.
    """

    CHAMADAS_DE_FORA_DA_VERCEL = {
        "sls/functions/lead/interface.yml": {
            "CreateLead": "LP da Essencia (draclaradourado.com.br, Lovable estatico) grava do "
                          "browser; sai quando gravar pelo servidor (PRD 066)",
        },
    }

    @staticmethod
    def _cors_por_funcao():
        """{(arquivo, funcao): [cors de cada evento http]} de todos os interface.yml."""
        raiz = SERVERLESS.parent
        achado = {}
        for arq in sorted((raiz / "sls" / "functions").glob("*/interface.yml")):
            doc = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
            rel = arq.relative_to(raiz).as_posix()
            for nome, funcao in doc.items():
                if not isinstance(funcao, dict):
                    continue
                eventos = [e["http"] for e in funcao.get("events") or []
                           if isinstance(e, dict) and isinstance(e.get("http"), dict)]
                if eventos:
                    achado[(rel, nome)] = [e.get("cors") for e in eventos]
        return achado

    def test_o_leitor_acha_as_rotas(self):
        self.assertGreater(len(self._cors_por_funcao()), 50, "o leitor parou de achar rota")

    def test_rota_chamada_de_fora_tem_cors(self):
        rotas = self._cors_por_funcao()
        for arquivo, funcoes in self.CHAMADAS_DE_FORA_DA_VERCEL.items():
            for nome in funcoes:
                with self.subTest(funcao=nome):
                    self.assertIn((arquivo, nome), rotas, f"{nome} sumiu de {arquivo}: atualize a lista")
                    self.assertTrue(
                        all(rotas[(arquivo, nome)]),
                        f"{nome} e chamada de fora da Vercel e esta sem cors: o browser barra "
                        f"no preflight e o erro e silencioso (PRD 066)",
                    )

    def test_nenhuma_outra_rota_tem_cors(self):
        permitidas = {(a, n) for a, fs in self.CHAMADAS_DE_FORA_DA_VERCEL.items() for n in fs}
        com_cors = sorted(
            f"{a}:{n}" for (a, n), cors in self._cors_por_funcao().items()
            if any(cors) and (a, n) not in permitidas
        )
        self.assertEqual(
            com_cors, [],
            "cors em rota que chega pela Vercel: custa um OPTIONS no stack (PRD 055). "
            "Se alguem de outro dominio chama do navegador, registre em CHAMADAS_DE_FORA_DA_VERCEL.",
        )


if __name__ == "__main__":
    unittest.main()
