# -*- coding: utf-8 -*-
"""Dois eventos, duas regras. Um otimiza, o outro mede.

PRD 017. A campanha `[Gestor]Depilacao_primeira_jardins` otimiza hoje com UM
sinal - uma tag de formulário na landing page -, porque a `Lead - Whatsapp`
morreu em 12/04/2026 e ficou invisível por 6 meses: a `Lead jardins` duplicada
mantinha o total parecendo saudável.

| | Compra (`7699541177`) | Agendamento (novo) |
|---|---|---|
| Elegibilidade | CONFIRMED + sessão passada + 90d | **só a janela de 90d** |
| Carimbo | data da SESSÃO | data do AGENDAMENTO |
| `eventSource` | `IN_STORE` | `MESSAGE` |
| Marcador | `uploaded_at` | `booking_uploaded_at` |
| Retratação | sim | **não** |

**O risco que estes testes guardam é a UNIFICAÇÃO.** As duas queries se parecem
e decidem coisas opostas: a compra afirma que a sessão aconteceu, o agendamento
afirma que a pessoa marcou. Juntá-las por economia faria uma das duas mentir.
"""
import ast
import os
import unittest
from unittest import mock

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "src")
UPLOADER = os.path.join(RAIZ, "functions", "conversions", "uploader.py")
DATA_MANAGER = os.path.join(RAIZ, "services", "data_manager_service.py")


def fonte(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def _corpo(caminho, nome):
    """O código de uma função, sem o docstring.

    Sem cortar o docstring, uma busca por `a.status` acharia a explicação de
    por que o filtro NÃO está lá - e reprovaria o código correto. Erro que já
    custou duas idas e voltas nesta suíte.
    """
    for no in ast.walk(ast.parse(fonte(caminho))):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            corpo = list(no.body)
            if (corpo and isinstance(corpo[0], ast.Expr)
                    and isinstance(corpo[0].value, ast.Constant)
                    and isinstance(corpo[0].value.value, str)):
                corpo = corpo[1:]
            return "\n".join(ast.unparse(x) for x in corpo)
    raise AssertionError("funcao %s nao encontrada" % nome)


class TestAsDuasRegrasSaoDistintas(unittest.TestCase):
    def test_o_agendamento_NAO_filtra_status(self):
        """É a diferença central. Cancelado e falta sobem igual, porque quem
        marcou e desmarcou agendou de verdade - o lead era qualificado,
        escolheu data e serviço. Cancelar depois não desfaz o fato."""
        corpo = _corpo(UPLOADER, "_get_pending_bookings")

        self.assertNotIn("a.status", corpo)
        self.assertNotIn("CONFIRMED", corpo)

    def test_a_compra_CONTINUA_filtrando_status_e_sessao_passada(self):
        """A regra da compra não foi tocada pelo PRD 017."""
        corpo = _corpo(UPLOADER, "_get_pending_conversions")

        self.assertIn("a.status = 'CONFIRMED'", corpo)
        self.assertIn("appointment_date <", corpo)

    def test_sao_duas_queries_separadas(self):
        """Juntá-las numa função com parâmetro seria o erro: elas decidem
        coisas opostas, e um `tipo=` convidaria a mexer nas duas de uma vez."""
        texto = fonte(UPLOADER)

        self.assertIn("def _get_pending_conversions", texto)
        self.assertIn("def _get_pending_bookings", texto)

    def test_cada_evento_marca_so_a_sua_coluna(self):
        """Marcar o errado faria uma conversão parecer enviada sem ter sido, e
        ninguém tentaria de novo."""
        compra = _corpo(UPLOADER, "_mark_uploaded")
        agendamento = _corpo(UPLOADER, "_mark_booking_uploaded")

        self.assertIn("uploaded_at = NOW()", compra)
        self.assertNotIn("booking_uploaded_at", compra)

        self.assertIn("booking_uploaded_at = NOW()", agendamento)


class TestOCarimboDoAgendamento(unittest.TestCase):
    def test_usa_LEAST_entre_created_at_e_a_sessao(self):
        """O momento é quando a pessoa MARCOU - mais folga na janela de 90 dias
        (pior caso medido: 41 dias do clique, contra 69 da compra).

        Mas as 16 linhas do backfill de 28/09/2026 têm `created_at` da data em
        que o backfill rodou, não do agendamento real. Sem o `LEAST`, o carimbo
        delas sairia semanas depois do fato.
        """
        corpo = _corpo(UPLOADER, "_get_pending_bookings")

        self.assertIn("LEAST(lc.created_at, lc.conversion_date)", corpo)

    def test_nunca_carimba_antes_do_clique(self):
        """O Google recusa conversão anterior ao clique."""
        corpo = _corpo(UPLOADER, "_get_pending_bookings")

        self.assertIn("> lc.click_date", corpo)

    def test_a_janela_de_90_dias_vale_para_os_dois(self):
        for nome in ("_get_pending_conversions", "_get_pending_bookings"):
            with self.subTest(nome):
                self.assertIn("INTERVAL '90 days'", _corpo(UPLOADER, nome))


class TestNaoHaRetratacaoDoAgendamento(unittest.TestCase):
    """A ausência é decisão, não esquecimento.

    Num evento de agendamento, cancelar depois não desfaz o fato de a pessoa
    ter marcado. É a propriedade que torna este evento mais simples que o de
    compra - e que dissolve o problema de 03/10/2026, quando descobrimos que a
    Data Manager API não oferece retratação.
    """

    def test_o_caminho_do_agendamento_nao_zera_valor(self):
        corpo = _corpo(UPLOADER, "_sobe_agendamentos")

        self.assertNotIn("restate", corpo)
        self.assertNotIn("retracted", corpo)

    def test_o_servico_nao_tem_metodo_de_retratar_agendamento(self):
        texto = fonte(DATA_MANAGER)

        self.assertNotIn("def restate_booking", texto)
        self.assertNotIn("def retract_booking", texto)

    def test_a_razao_esta_escrita(self):
        """Sem o porquê, a ausência parece bug e alguém "conserta"."""
        self.assertIn("agendou de verdade", fonte(UPLOADER))


class TestOEventSourceNaoEHerdado(unittest.TestCase):
    def test_duas_constantes_distintas(self):
        texto = fonte(DATA_MANAGER)

        self.assertIn('EVENT_SOURCE_COMPRA = "IN_STORE"', texto)
        self.assertIn('EVENT_SOURCE_AGENDAMENTO = "MESSAGE"', texto)

    def test_event_source_e_obrigatorio_no_evento(self):
        """Sem default, de propósito: um default faria o evento de agendamento
        herdar `IN_STORE` em silêncio, e o erro apareceria como atribuição
        estranha no Google semanas depois - não como falha."""
        for no in ast.walk(ast.parse(fonte(DATA_MANAGER))):
            if isinstance(no, ast.FunctionDef) and no.name == "_evento":
                nomes = [a.arg for a in no.args.args]
                self.assertIn("event_source", nomes)
                # `defaults` alinha pela DIREITA; event_source e o 2o de 3,
                # entao so pode ter default se houver 2 ou mais.
                self.assertLessEqual(
                    len(no.args.defaults), 1,
                    "event_source ganhou default - veja o docstring",
                )
                return
        self.fail("_evento nao encontrado")


class TestAClinicaComUmaActionSoAparece(unittest.TestCase):
    def test_o_where_exige_ao_menos_uma_action(self):
        """Exigir as DUAS faria uma clínica com só o evento novo ligado não
        aparecer, e o uploader sairia com `clinics: 0` em silêncio - que é
        exatamente o defeito de 28/09/2026."""
        corpo = _corpo(UPLOADER, "_get_mapped_clinics")

        self.assertIn("OR booking_conversion_action_id IS NOT NULL", corpo)
        self.assertIn("google_ads_customer_id IS NOT NULL", corpo)

    def test_cada_passo_confere_a_action_dele(self):
        """Consequência do WHERE afrouxado: sem o guard por passo, o destino
        iria com `None` e o Google recusaria o lote inteiro."""
        for nome, coluna in (("_sobe_compras", "offline_conversion_action_id"),
                             ("_sobe_agendamentos", "booking_conversion_action_id")):
            with self.subTest(nome):
                corpo = _corpo(UPLOADER, nome)
                self.assertIn(coluna, corpo)
                self.assertIn("if not action", corpo)


class TestTransporteDoAgendamento(unittest.TestCase):
    """Comportamento de `ingest_bookings`, com a rede mockada."""

    def _servico(self):
        import importlib
        import sys
        sys.path.insert(0, os.path.normpath(os.path.join(RAIZ, "..")))
        modulo = importlib.import_module("src.services.data_manager_service")
        servico = modulo.DataManagerService()
        servico._token = "token-de-teste"
        return modulo, servico

    def _itens(self, quantas=2):
        return [
            {"identifier": "id-%d" % i, "gclid": "g-%d" % i,
             "conversion_date_time": "2026-09-15T14:30:00-03:00",
             "conversion_value": 280.0}
            for i in range(quantas)
        ]

    def _resposta(self, status=200, corpo=None):
        r = mock.Mock(status_code=status, content=b"{}", text="erro")
        r.json.return_value = corpo or {}
        return r

    def test_manda_eventSource_MESSAGE(self):
        modulo, servico = self._servico()

        with mock.patch.object(modulo.requests, "post",
                               return_value=self._resposta()) as post:
            servico.ingest_bookings("4601912200", "999", self._itens(1))

        evento = post.call_args.kwargs["json"]["events"][0]
        self.assertEqual(evento["eventSource"], "MESSAGE")

    def test_a_compra_continua_mandando_IN_STORE(self):
        modulo, servico = self._servico()

        with mock.patch.object(modulo.requests, "post",
                               return_value=self._resposta()) as post:
            servico.ingest_offline_conversions("4601912200", "888", self._itens(1))

        evento = post.call_args.kwargs["json"]["events"][0]
        self.assertEqual(evento["eventSource"], "IN_STORE")

    def test_sucesso_devolve_os_identifiers(self):
        modulo, servico = self._servico()

        with mock.patch.object(modulo.requests, "post",
                               return_value=self._resposta()):
            r = servico.ingest_bookings("4601912200", "999", self._itens())

        self.assertTrue(r["success"])
        self.assertEqual(r["uploaded_identifiers"], ["id-0", "id-1"])

    def test_erro_http_nao_devolve_identifier_nenhum(self):
        """Marcar como enviado o que falhou faz a conversão desaparecer: o
        `booking_uploaded_at` ficaria preenchido e ninguém tentaria de novo."""
        modulo, servico = self._servico()

        with mock.patch.object(modulo.requests, "post",
                               return_value=self._resposta(403)):
            r = servico.ingest_bookings("4601912200", "999", self._itens())

        self.assertFalse(r["success"])
        self.assertEqual(r["uploaded_identifiers"], [])
        self.assertEqual(r["failed"], 2)

    def test_validate_only_nao_marca_nada(self):
        modulo, servico = self._servico()

        with mock.patch.object(modulo.requests, "post",
                               return_value=self._resposta()) as post:
            r = servico.ingest_bookings("4601912200", "999", self._itens(),
                                        validate_only=True)

        self.assertEqual(r["uploaded_identifiers"], [])
        self.assertEqual(r["validated"], 2)
        self.assertIs(post.call_args.kwargs["json"]["validateOnly"], True)

    def test_lista_vazia_nao_chama_a_rede(self):
        modulo, servico = self._servico()

        with mock.patch.object(modulo.requests, "post") as post:
            r = servico.ingest_bookings("4601912200", "999", [])

        post.assert_not_called()
        self.assertTrue(r["success"])


class TestOResumoSeparaOsDois(unittest.TestCase):
    def test_o_summary_tem_contadores_do_agendamento(self):
        """Somar os dois no mesmo `uploaded` esconderia qual dos dois falhou."""
        texto = fonte(UPLOADER)

        self.assertIn('"bookings_uploaded": 0', texto)
        self.assertIn('"bookings_failed": 0', texto)


class TestOsArquivosCompilam(unittest.TestCase):
    def test_ast_valido(self):
        for caminho in (UPLOADER, DATA_MANAGER):
            with self.subTest(os.path.basename(caminho)):
                ast.parse(fonte(caminho))


if __name__ == "__main__":
    unittest.main()
