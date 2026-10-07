# -*- coding: utf-8 -*-
"""Nenhuma função carrega uma role que não usa.

A stack de prod chegou a 497 recursos de 500 - a próxima Lambda com endpoint
não subia. Eram 75 IAM roles para 74 funções, e **57 delas concediam
exatamente a mesma coisa**: logs mais `ssm:GetParameter`.

O `ssm` era permissão MORTA. Os segredos são resolvidos no deploy pelo
`${ssm:/...}` do serverless.yml e chegam como variável de ambiente; nenhuma
Lambda lê SSM em runtime. Fazer 57 cópias dessa política não comprava
isolamento - comprava o limite do CloudFormation.

Este teste existe porque o defeito volta por cópia e cola: o jeito de escrever
uma função nova é copiar a vizinha, e a vizinha tinha o bloco. Ele falha no
momento em que alguém reintroduz o desperdício, e não seis meses depois num
deploy que não sobe.

Regra: se a role de uma função concede apenas logs e/ou ssm, ela não deveria
existir - a função usa a role compartilhada do provider.
"""
import io
import os
import unittest

import yaml

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "sls", "functions")

# Só isto não justifica uma role própria. `ssm:GetParameter` está aqui porque é
# permissão morta; os logs porque a role compartilhada já os concede.
NAO_JUSTIFICAM = {
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents",
    "logs:TagResource",
    "ssm:GetParameter",
}


def funcoes():
    """(arquivo, nome, ações concedidas) de cada função com role própria."""
    saida = []
    for dominio in sorted(os.listdir(BASE)):
        caminho = os.path.join(BASE, dominio, "interface.yml")
        if not os.path.exists(caminho):
            continue
        dados = yaml.safe_load(io.open(caminho, encoding="utf-8")) or {}
        for nome, cfg in dados.items():
            if not isinstance(cfg, dict) or "iamRoleStatements" not in cfg:
                continue
            acoes = set()
            for st in cfg["iamRoleStatements"] or []:
                a = st.get("Action")
                acoes |= set(a if isinstance(a, list) else [a])
            saida.append((f"{dominio}/interface.yml", nome, acoes))
    return saida


class TestRolePropriaSoQuandoPrecisa(unittest.TestCase):
    def test_nenhuma_role_concede_apenas_logs_e_ssm(self):
        desperdicio = [
            (arq, nome) for arq, nome, acoes in funcoes()
            if acoes and not (acoes - NAO_JUSTIFICAM)
        ]

        self.assertEqual(
            desperdicio, [],
            "Estas funções têm role própria que só concede logs e/ou ssm:\n"
            + "\n".join(f"  {nome}  ({arq})" for arq, nome in desperdicio)
            + "\n\nTire o bloco `iamRoleStatements` e `iamRoleStatementsName` "
              "delas: caem na role compartilhada do provider, que já concede "
              "logs. Cada role a menos é um recurso de CloudFormation a menos, "
              "e a stack de prod vive perto do limite de 500.",
        )

    def test_ninguem_pede_ssm_em_runtime(self):
        """`ssm:GetParameter` numa role é sinal de que alguém achou que a Lambda
        lê SSM. Ela não lê - o serverless.yml resolve no deploy."""
        com_ssm = [
            (arq, nome) for arq, nome, acoes in funcoes()
            if "ssm:GetParameter" in acoes
        ]

        self.assertEqual(
            com_ssm, [],
            "Estas funções pedem ssm:GetParameter, que nenhuma Lambda usa:\n"
            + "\n".join(f"  {nome}  ({arq})" for arq, nome in com_ssm),
        )


class TestQuemFicouTemMotivo(unittest.TestCase):
    """As que mantiveram role própria tocam DynamoDB ou invocam outra Lambda -
    e aí a separação significa alguma coisa."""

    def test_toda_role_que_sobrou_concede_algo_de_verdade(self):
        for arq, nome, acoes in funcoes():
            with self.subTest(funcao=nome):
                reais = acoes - NAO_JUSTIFICAM
                self.assertTrue(
                    reais,
                    f"{nome} ({arq}) mantém role sem conceder nada de útil",
                )
                self.assertTrue(
                    any(a.startswith(("dynamodb:", "lambda:", "s3:", "sqs:", "events:"))
                        for a in reais),
                    f"{nome} concede {sorted(reais)}, que não é serviço conhecido "
                    f"deste projeto - confira se é mesmo necessário",
                )


if __name__ == "__main__":
    unittest.main()
