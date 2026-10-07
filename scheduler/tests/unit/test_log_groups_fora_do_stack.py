# -*- coding: utf-8 -*-
"""Os log groups saem do stack sem apagar grupo nem parar de logar.

Prod está em 496 dos 500 recursos do CloudFormation; 78 são log groups, um
por função. `disableLogs: true` do Serverless 3 não serve: ele acrescenta um
Deny de logs:PutLogEvents na role. O plugin em sls/plugins faz a saída em
duas etapas (retain, depois remove). Aqui o plugin roda de verdade, via node,
contra um template pequeno.
"""
import json
import os
import shutil
import subprocess
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(RAIZ, "sls", "plugins", "log-groups-fora-do-stack.js")

HARNESS = r"""
const Plugin = require(process.argv[1]);
const entrada = JSON.parse(require("fs").readFileSync(0, "utf8"));
class Erro extends Error {}
const serverless = {
  classes: { Error: Erro },
  cli: { log: () => {} },
  service: {
    custom: { logGroups: entrada.modo },
    provider: { compiledCloudFormationTemplate: entrada.template },
  },
};
try {
  new Plugin(serverless).aplica();
  console.log(JSON.stringify({ ok: true, template: entrada.template }));
} catch (e) {
  console.log(JSON.stringify({ ok: false, erro: e.message }));
}
"""


def template():
    return {"Resources": {
        "ALogGroup": {"Type": "AWS::Logs::LogGroup", "Properties": {"LogGroupName": "/aws/lambda/a"}},
        "BLogGroup": {"Type": "AWS::Logs::LogGroup", "Properties": {"LogGroupName": "/aws/lambda/b"}},
        "ALambdaFunction": {"Type": "AWS::Lambda::Function", "DependsOn": ["ALogGroup", "AIamRole"], "Properties": {}},
        "BLambdaFunction": {"Type": "AWS::Lambda::Function", "DependsOn": ["BLogGroup"], "Properties": {}},
        "AIamRole": {"Type": "AWS::IAM::Role", "Properties": {}},
    }}


def roda(modo, tpl=None):
    saida = subprocess.run(
        ["node", "-e", HARNESS, "--", PLUGIN],
        input=json.dumps({"modo": modo, "template": tpl or template()}),
        capture_output=True, text=True, encoding="utf-8",
    )
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout.strip().splitlines()[-1])


@unittest.skipUnless(shutil.which("node"), "node não está no PATH")
class TestModos(unittest.TestCase):
    def test_sem_modo_nao_toca_no_template(self):
        r = roda("")
        self.assertTrue(r["ok"])
        self.assertEqual(r["template"], template())

    def test_retain_marca_todos_os_grupos_e_nada_mais(self):
        r = roda("retain")
        res = r["template"]["Resources"]
        for g in ("ALogGroup", "BLogGroup"):
            self.assertEqual(res[g]["DeletionPolicy"], "Retain")
            self.assertEqual(res[g]["UpdateReplacePolicy"], "Retain")
        self.assertNotIn("DeletionPolicy", res["ALambdaFunction"])
        self.assertEqual(res["ALambdaFunction"]["DependsOn"], ["ALogGroup", "AIamRole"])

    def test_remove_tira_os_grupos_e_o_depends_on(self):
        r = roda("remove")
        res = r["template"]["Resources"]
        self.assertNotIn("ALogGroup", res)
        self.assertNotIn("BLogGroup", res)
        # Só a dependência do log group sai; a da role fica.
        self.assertEqual(res["ALambdaFunction"]["DependsOn"], ["AIamRole"])
        self.assertNotIn("DependsOn", res["BLambdaFunction"])
        self.assertIn("AIamRole", res)

    def test_modo_desconhecido_e_erro(self):
        r = roda("apagar")
        self.assertFalse(r["ok"])
        self.assertIn("retain", r["erro"])


class TestFiacao(unittest.TestCase):
    def test_plugin_declarado_e_modo_por_param(self):
        yml = open(os.path.join(RAIZ, "serverless.yml"), encoding="utf-8").read()
        self.assertIn("./sls/plugins/log-groups-fora-do-stack.js", yml)
        self.assertIn("logGroups: ${param:logGroups, 'remove'}", yml)

    def test_nenhuma_funcao_usa_disable_logs(self):
        """disableLogs no Serverless 3 e um Deny de PutLogEvents: desliga o log."""
        for pasta, _, arquivos in os.walk(os.path.join(RAIZ, "sls", "functions")):
            for nome in arquivos:
                if nome.endswith(".yml"):
                    texto = open(os.path.join(pasta, nome), encoding="utf-8").read()
                    self.assertNotIn("disableLogs", texto, f"{nome} usa disableLogs")


if __name__ == "__main__":
    unittest.main()
