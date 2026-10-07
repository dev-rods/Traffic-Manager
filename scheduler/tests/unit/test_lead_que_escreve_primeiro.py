# -*- coding: utf-8 -*-
"""O lead da landing page que escreve primeiro é atendido — e não abordado de novo.

Caso real de 18/09/2026, Ana Clara, DDD 61:

    11:02:18  lead entra pela landing page      phone = 5561981864151 (com o 9)
    11:02:34  ela escreve no WhatsApp           chega como 556181864151 (sem o 9)
              -> o webhook procura o lead por telefone EXATO e não acha
              -> `bot_enabled` não é marcado
              -> política LEADS_ONLY: o bot fica CALADO
              -> `conversation_started_at` não é marcado: ela "nunca respondeu"
    14:02     a atendente percebe e assume a conversa na mão
    14:54     alguém vê o lead como "sem contato" e clica em "iniciar pelo bot"
              -> a trava JA_RESPONDEU não dispara, porque o campo está nulo
              -> o bot entra por cima da atendente, com DUAS mensagens

Três horas de silêncio, e depois uma intromissão. Tudo porque duas consultas do
webhook casavam o telefone por igualdade.

O projeto já sabia do nono dígito: `variantes_do_numero` existe desde 05/09 e é
usada no espelho do z-api, no `_ja_esta_conversando` e na listagem. Faltava
justamente nos dois lugares que decidem se o bot fala. A regra certa em alguns
lugares e não em todos - e a divergência é silenciosa.

Medido quando o defeito foi achado: dos 77 leads da landing page, 14 eram de DDD
fora da faixa 11-28, e os 14 estavam com `conversation_started_at` nulo. Zero de
14 registrados.
"""
import unittest

from src.utils.phone import variantes_do_numero

# Os quatro que já tinham escrito e o sistema não registrou, com o DDD real.
AFETADOS_REAIS = [
    ("ana", "5561981864151", "556181864151"),
    ("nicole", "5548984095519", "554884095519"),
    ("michelle", "5553997000722", "555397000722"),
    ("ricardo", "5562984661941", "556284661941"),
]


class TestOTelefoneDoLeadEODoWhatsAppSaoOMesmo(unittest.TestCase):
    """O que a correção precisa reconhecer."""

    def test_os_quatro_casos_reais_casam_por_variante(self):
        for nome, do_formulario, do_whatsapp in AFETADOS_REAIS:
            with self.subTest(lead=nome):
                self.assertIn(
                    do_formulario, variantes_do_numero(do_whatsapp),
                    f"{nome}: a mensagem chega como {do_whatsapp} e o lead está "
                    f"gravado como {do_formulario} - se não casarem, o bot cala",
                )

    def test_e_o_casamento_vale_nos_dois_sentidos(self):
        for nome, do_formulario, do_whatsapp in AFETADOS_REAIS:
            with self.subTest(lead=nome):
                self.assertIn(do_whatsapp, variantes_do_numero(do_formulario))

    def test_sao_paulo_continua_intocado(self):
        """Tirar o 9 de um número 11-28 produz o celular de OUTRA pessoa. A
        variante só existe fora dessa faixa."""
        self.assertEqual(variantes_do_numero("5511987654321"), {"5511987654321"})


class TestAsConsultasDoWebhookUsamVariante(unittest.TestCase):
    """Fiação: a função pode existir e o webhook não usá-la - foi exatamente o
    que acontecia, por cinco meses."""

    def _sql_sobre_leads(self):
        """Todo literal de SQL do webhook que filtra `scheduler.leads` por telefone.

        Lê pela AST e junta as partes concatenadas: as consultas são escritas em
        pedaços ("SELECT ..." "FROM ..."), e procurar no texto cru acha metade.
        """
        import ast
        import inspect

        import src.functions.webhook.handler as handler

        arvore = ast.parse(inspect.getsource(handler))
        achados = []
        for no in ast.walk(arvore):
            partes = []
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                partes = [no.value]
            elif isinstance(no, ast.BinOp):
                partes = [x.value for x in ast.walk(no)
                          if isinstance(x, ast.Constant) and isinstance(x.value, str)]
            texto = " ".join(partes)
            if "scheduler.leads" in texto and "phone" in texto:
                achados.append(" ".join(texto.split()))
        return achados

    def test_nenhuma_consulta_casa_telefone_por_igualdade(self):
        """`phone = %s` é o defeito. Tem de ser `phone = ANY(%s)`."""
        ruins = [q for q in self._sql_sobre_leads() if "phone = %s" in q]

        self.assertEqual(
            ruins, [],
            "Estas consultas voltaram a casar telefone por igualdade:\n"
            + "\n".join(f"  {q[:150]}" for q in ruins)
            + "\n\nLead de DDD fora de 11-28 nunca e encontrado: o bot fica "
              "calado e o lead fica como 'nunca respondeu'.",
        )

    def test_e_as_duas_consultas_continuam_existindo(self):
        """Se alguém apagar as consultas, o teste acima passaria vazio."""
        consultas = self._sql_sobre_leads()

        self.assertTrue(
            any("conversation_started_at" in q for q in consultas),
            "sumiu a marcação de que o lead respondeu",
        )
        self.assertTrue(
            any("landing-page" in q for q in consultas),
            "sumiu a busca do lead da landing page que habilita o bot",
        )
        for q in consultas:
            with self.subTest(sql=q[:60]):
                self.assertIn("ANY(%s)", q)

    def test_o_webhook_importa_a_funcao_de_variantes(self):
        import ast
        import inspect

        import src.functions.webhook.handler as handler

        importados = []
        for no in ast.walk(ast.parse(inspect.getsource(handler))):
            if isinstance(no, ast.ImportFrom):
                importados += [a.name for a in no.names]

        self.assertIn("variantes_do_numero", importados)


if __name__ == "__main__":
    unittest.main()
