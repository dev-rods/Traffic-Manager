# -*- coding: utf-8 -*-
"""A lista fechada do que o funcionário alcança.

Este é o teste que protege contra o erro mais provável desta feature: abrir uma
rota sem perceber. Ele varre TODOS os handlers e compara o que encontrou com a
lista abaixo - trocar `require_api_key` por `require_acesso` em qualquer arquivo
quebra aqui até que alguém venha escrever a rota nova nesta lista, de propósito.

O outro lado também é coberto: as rotas do administrador são conferidas uma a
uma para garantir que continuam fechadas. Relatório financeiro, configuração da
clínica e conversa de WhatsApp foram os três itens que o André nomeou.
"""
import ast
import io
import os
import unittest

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "src", "functions")

# O que a funcionária alcança. Mexer aqui é uma decisão, nunca um efeito
# colateral de mexer noutro lugar.
ABERTAS = {
    # A agenda: ver, criar e editar.
    "appointment/list.py": "agenda.ler",
    "appointment/create.py": "agenda.escrever",
    "appointment/update.py": "agenda.escrever",
    "availability/slots.py": "agenda.ler",
    # As datas com atendimento, que é o que a tela da agenda pagina.
    "availability/rules.py": "agenda.ler",
    # Catálogo, só leitura: sem ele não há como montar um agendamento.
    "service/list.py": "catalogo.ler",
    "area/list.py": "catalogo.ler",
    "area/get.py": "catalogo.ler",
    "service_area/list.py": "catalogo.ler",
    "duration_rules/get.py": "catalogo.ler",
    "professional/list.py": "catalogo.ler",
    # Pacientes: achar, cadastrar e corrigir.
    "patient/list.py": "pacientes.ler",
    "patient/create.py": "pacientes.escrever",
    "patient/update.py": "pacientes.escrever",
    # Prontuário: registrar a sessão.
    "patient_record/list.py": "prontuario.ler",
    "patient_record/create.py": "prontuario.escrever",
    "patient_record/update.py": "prontuario.escrever",
    "patient_record/history.py": "prontuario.ler",
    "patient_record/protocol.py": "prontuario.ler",
    # O nome e o horário da clínica, sem as credenciais.
    "clinic/get.py": "clinica.basica",
}

# Os três itens que o André nomeou, e o resto do que não pode vazar junto.
FECHADAS = [
    "clinic/reports.py",        # relatório financeiro
    "clinic/dashboard.py",      # faturamento na home
    "clinic/bot_metrics.py",
    "clinic/update.py",         # configuração da clínica
    "clinic/create.py",
    "clinic/list.py",           # todas as clínicas
    "attendant/handler.py",     # conversas de WhatsApp
    "send/send.py",
    "lead/list.py",
    "faq/list.py",
    "template/list.py",
    "discount_rules/get.py",    # regra de preço
    "discount_rules/update.py",
    "duration_rules/update.py",
    "patient/delete.py",
    "patient_record/delete.py",
    "availability/exceptions.py",
    "service/create.py",
    "service/update.py",
    "area/create.py",
    "area/update.py",
    "area/delete.py",
]


def _chamadas(caminho):
    """(funcao, permissao) de cada require_acesso/require_api_key do arquivo."""
    arvore = ast.parse(io.open(caminho, encoding="utf-8").read())
    achadas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Name):
            continue
        if no.func.id == "require_acesso":
            arg = no.args[1] if len(no.args) >= 2 else None
            achadas.append(("require_acesso",
                            arg.value if isinstance(arg, ast.Constant) else None))
        elif no.func.id == "require_api_key":
            achadas.append(("require_api_key", None))
    return achadas


def _varre():
    encontrado = {}
    for raiz, _, arquivos in os.walk(RAIZ):
        for arquivo in arquivos:
            if not arquivo.endswith(".py"):
                continue
            caminho = os.path.join(raiz, arquivo)
            rel = os.path.relpath(caminho, RAIZ).replace(os.sep, "/")
            for funcao, permissao in _chamadas(caminho):
                if funcao == "require_acesso":
                    encontrado[rel] = permissao
    return encontrado


class TestAListaEFechada(unittest.TestCase):
    def setUp(self):
        self.encontrado = _varre()

    def test_nenhuma_rota_foi_aberta_por_engano(self):
        sobrando = set(self.encontrado) - set(ABERTAS)

        self.assertEqual(sobrando, set(), (
            "Estas rotas passaram a aceitar funcionário e não estão na lista. "
            "Se foi de propósito, escreva-as em ABERTAS; se não, volte para "
            "require_api_key."
        ))

    def test_nenhuma_rota_da_lista_fechou_sozinha(self):
        faltando = set(ABERTAS) - set(self.encontrado)

        self.assertEqual(faltando, set(),
                         "Estas rotas deveriam aceitar funcionário e não aceitam.")

    def test_cada_rota_pede_a_permissao_certa(self):
        for caminho, esperada in ABERTAS.items():
            with self.subTest(caminho):
                self.assertEqual(self.encontrado.get(caminho), esperada)


class TestOQueFicaSoComOAdmin(unittest.TestCase):
    """Os três itens que o André nomeou: relatório financeiro, configuração da
    clínica e conversa de WhatsApp."""

    def test_continuam_em_require_api_key(self):
        for rel in FECHADAS:
            caminho = os.path.join(RAIZ, *rel.split("/"))
            if not os.path.exists(caminho):
                continue  # o arquivo mudou de nome; o teste de varredura pega
            with self.subTest(rel):
                funcoes = {f for f, _ in _chamadas(caminho)}
                self.assertNotIn("require_acesso", funcoes)
                self.assertIn("require_api_key", funcoes)


class TestAsPermissoesExistem(unittest.TestCase):
    def test_toda_permissao_pedida_esta_concedida_ao_staff(self):
        """Pedir uma permissão que o STAFF não tem seria abrir a rota e mantê-la
        fechada ao mesmo tempo - o tipo de engano que só aparece em produção."""
        from src.utils.acesso import PERMISSOES_DO_STAFF

        for caminho, permissao in ABERTAS.items():
            with self.subTest(caminho):
                self.assertIn(permissao, PERMISSOES_DO_STAFF)


if __name__ == "__main__":
    unittest.main()
