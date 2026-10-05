"""Esta conversion action e uma COMPRA: so sobe sessao que ja aconteceu.

A regra mudou tres vezes, e cada volta tem um motivo diferente. Sem isso
registrado, a proxima pessoa desfaz por achar que e descuido.

**Ate 27/09/2026.** Havia `a.appointment_date < CURRENT_DATE`: so subia depois
da sessao, como protecao contra cancelamento.

**27/09/2026 (Andre).** O guard saiu, para a conversao contar no AGENDAMENTO: o
sinal chegava antes (mediana medida depois: 13 dias) e a RETRACTION seria a
contrapartida do cancelamento.

**03/10/2026 (Google + Andre).** O Google fechou a RETRACTION - a Data Manager
API so permite *restatement* de valor, nunca negar a conversao. A contrapartida
que sustentava o desenho anterior deixou de existir.

Diante disso o Andre decidiu o contrario: esta action passa a ser PURCHASE
pura - confirmou E compareceu -, e o guard voltou. O evento de "WhatsApp
qualificado", que conta no agendamento e INCLUI quem cancelou, sera uma action
SEPARADA. Dois eventos honestos em vez de um hibrido afirmando as duas coisas.

**O limite que os testes travam:** o guard NAO prova comparecimento. O scheduler
nao registra presenca (so CONFIRMED e CANCELLED; 604 dos 618 CONFIRMED ficam
assim para sempre, e o prontuario cobre 4% das sessoes passadas), entao um
no-show entra como compra. E o melhor proxy disponivel, nao a regra final.

Taxa de cancelamento medida em 03/10/2026: 33% (10 de 30). O 42% que circulava
vinha de 5 de 12.
"""
import ast
import os
import re
import unittest
from unittest import mock

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "src")
UPLOADER = os.path.join(RAIZ, "functions", "conversions", "uploader.py")
CLIENTE = os.path.join(RAIZ, "services", "google_ads_client_service.py")
DATA_MANAGER = os.path.join(RAIZ, "services", "data_manager_service.py")


def fonte(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


class TestSoSobeCompraRealizada(unittest.TestCase):
    def test_o_guard_da_sessao_passada_esta_de_volta(self):
        """Sem ele, "compra" seria afirmada no agendamento - antes de existir.

        Este teste ja existiu invertido, travando a ausência do guard entre
        27/09 e 03/10/2026. A inversão é deliberada, não descuido: ver o
        docstring do módulo antes de mexer.
        """
        texto = fonte(UPLOADER)

        # A cláusula inteira, não dois pedaços soltos: o docstring do módulo
        # cita `a.appointment_date < CURRENT_DATE` de propósito, para contar que
        # o guard saiu em 27/09 e voltou em 03/10. Um `assertNotIn` na forma
        # antiga casaria com essa explicação e reprovaria o código correto -
        # erro que já cometi duas vezes nesta suíte.
        #
        # Data da clínica, não do servidor: o banco roda em UTC, e entre 21h e
        # meia-noite BRT o `CURRENT_DATE` já é amanhã - a sessão de hoje
        # passaria por realizada numa invocação manual nessa faixa.
        self.assertIn(
            "AND a.appointment_date < (NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
            texto,
        )

    def test_o_limite_do_guard_esta_escrito(self):
        """O guard não prova comparecimento, e confundir as duas coisas é o
        erro fácil: alguém lê "sessão passou" e entende "a pessoa veio".

        Enquanto não houver registro de presença, o aviso tem de estar no
        código - não só no PR que ninguém relê.
        """
        texto = fonte(UPLOADER)

        self.assertIn("NAO prova presenca", texto)
        self.assertIn("no-show", texto)

    def test_o_carimbo_enviado_nunca_e_futuro(self):
        """Redundante com o guard, mantido como cinto de segurança: o Google
        recusa carimbo no futuro, e esta regra já mudou três vezes."""
        self.assertIn("LEAST(lc.conversion_date, NOW())", fonte(UPLOADER))

    def test_a_janela_de_90_dias_continua(self):
        """O Google recusa clique com mais de 90 dias. Esse filtro não era
        sobre cancelamento e não podia sair junto."""
        self.assertIn("INTERVAL '90 days'", fonte(UPLOADER))

    def test_so_agendamento_confirmado_sobe(self):
        self.assertIn("a.status = 'CONFIRMED'", fonte(UPLOADER))


class TestAApiFechadaNaoVolta(unittest.TestCase):
    """O Google recusa essas chamadas. Reintroduzi-las volta a falhar 100%.

    Esse é o teste que faltava em 03/10/2026: o `infra/` chamou por meses uma
    API que não respondia mais, e nada apontava isso.
    """

    def test_nenhum_arquivo_de_src_chama_o_servico_fechado(self):
        """Procura CHAMADA, não menção.

        Os nomes aparecem de propósito na documentação do módulo novo e na nota
        que proíbe reintroduzi-los; uma busca crua por texto reprovaria o
        código correto. O que importa é `get_service("...")` com o serviço
        fechado, e métodos da API antiga sendo invocados.
        """
        fechados = {"ConversionUploadService", "ConversionAdjustmentUploadService"}
        metodos_fechados = {"upload_click_conversions",
                            "upload_conversion_adjustments"}
        encontrados = []

        for pasta, _, arquivos in os.walk(RAIZ):
            if "__pycache__" in pasta:
                continue
            for arquivo in arquivos:
                if not arquivo.endswith(".py"):
                    continue
                caminho = os.path.join(pasta, arquivo)
                for no in ast.walk(ast.parse(fonte(caminho))):
                    if not isinstance(no, ast.Call):
                        continue
                    alvo = no.func
                    # get_service("ConversionUploadService")
                    if isinstance(alvo, ast.Attribute) and alvo.attr == "get_service":
                        for arg in no.args:
                            if isinstance(arg, ast.Constant) and arg.value in fechados:
                                encontrados.append((caminho, arg.value))
                    # client.upload_click_conversions(...)
                    if isinstance(alvo, ast.Attribute) and alvo.attr in metodos_fechados:
                        encontrados.append((caminho, alvo.attr))

        self.assertEqual(encontrados, [],
                         "API fechada pelo Google voltou ao código: %s" % encontrados)

    def test_os_metodos_antigos_sairam_do_servico_do_google_ads(self):
        texto = fonte(CLIENTE)

        self.assertNotIn("def upload_offline_conversions", texto)
        self.assertNotIn("def retract_offline_conversions", texto)


class TestValorZeradoDoCancelado(unittest.TestCase):
    def test_o_servico_novo_tem_o_metodo(self):
        self.assertIn("def restate_cancelled_to_zero", fonte(DATA_MANAGER))

    def test_o_nome_nao_promete_retratacao(self):
        """Chamar isso de "retract" faria o próximo leitor acreditar numa
        proteção que não existe. O nome tem de dizer o que de fato acontece."""
        texto = fonte(DATA_MANAGER)

        self.assertNotIn("def retract_offline_conversions", texto)
        self.assertIn("restate", texto)

    def test_o_limite_da_contagem_esta_documentado(self):
        """A contagem permanecer é a consequência que decide se o desenho de
        27/09 ainda se sustenta. Não pode ficar implícita."""
        texto = fonte(DATA_MANAGER)

        self.assertIn("CONTAGEM permanece", texto)
        self.assertIn("MAXIMIZE_CONVERSIONS", texto)

    def test_identifica_a_conversao_pelo_transaction_id(self):
        """A Data Manager casa o ajuste com a conversão original pelo
        `transactionId`. Era o par (gclid, conversion_date_time) na API antiga.

        Se o transactionId divergir entre upload e ajuste, a API cria uma
        conversão NOVA em vez de ajustar - dobrando o estrago.
        """
        self.assertIn("transactionId", fonte(DATA_MANAGER))

    def test_o_uploader_so_zera_o_que_subiu(self):
        """`uploaded_at IS NOT NULL` é a condição que importa: só há o que
        desfazer se chegou a existir no Google."""
        texto = fonte(UPLOADER)

        self.assertIn("lc.uploaded_at IS NOT NULL", texto)
        self.assertIn("lc.retracted_at IS NULL", texto)

    def test_zerar_cobre_cancelado_E_falta(self):
        """A compra que afirmamos ao Google não aconteceu nos dois casos.

        Era só `CANCELLED` até 04/10/2026. Deixar `NO_SHOW` de fora faria a
        falta descoberta depois do upload ficar com o valor cheio no Google -
        e ninguém tentaria de novo, porque `retracted_at` seguiria nulo sem
        nada acontecer.
        """
        texto = fonte(UPLOADER)

        self.assertIn("a.status IN ('CANCELLED', 'NO_SHOW')", texto)
        self.assertNotIn("a.status = 'CANCELLED'", texto,
                         "a forma antiga deixaria a falta de fora")

    def test_falta_nao_e_elegivel_para_subir(self):
        """O filtro de elegibilidade é `= CONFIRMED`, exato - então NO_SHOW sai
        sozinho, sem precisar de cláusula própria.

        Trocar por `IN` ou `!=` aqui deixaria a falta subir como compra, que é
        exatamente o que o status existe para impedir.
        """
        texto = fonte(UPLOADER)

        self.assertIn("a.status = 'CONFIRMED'", texto)
        self.assertNotIn("a.status != ", texto)

    def test_o_aviso_diz_que_depende_de_alguem_marcar(self):
        """NO_SHOW existir não fecha o problema: depende de adoção.

        Sem isso escrito, a existência do status viraria prova de presença na
        cabeça de quem lê - e promover a conversão a biddable seria prematuro.
        """
        texto = fonte(UPLOADER)

        self.assertIn("depende de", texto)
        self.assertIn("NO_SHOW", texto)

    def test_nenhum_passo_pode_ser_pulado(self):
        """O loop de clínicas não tem `continue`, e isso é o desenho.

        Este teste já checou outra coisa: que o zeramento vinha ANTES do
        `if not pending: continue`, porque aquele atalho pulava a clínica
        inteira quando não havia compra nova.

        O PRD 017 trocou a garantia por uma mais forte. Com três passos
        independentes - zerar, subir compras, subir agendamentos -, qualquer
        `continue` no meio pula um deles em silêncio. Então a propriedade a
        travar deixou de ser a ordem e passou a ser a ausência do atalho.
        """
        arvore = ast.parse(fonte(UPLOADER))

        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef) and no.name == "handler":
                for interno in ast.walk(no):
                    self.assertNotIsInstance(
                        interno, ast.Continue,
                        "um `continue` no handler pula um dos tres passos",
                    )
                return
        self.fail("handler nao encontrado")


class TestMigrationCriaAColuna(unittest.TestCase):
    def test_migration_cria_retracted_at(self):
        caminho = os.path.join(
            RAIZ, "..", "..", "scheduler", "src", "scripts", "setup_database.py")
        texto = fonte(os.path.normpath(caminho))

        self.assertIn("retracted_at", texto)
        self.assertIn("ADD COLUMN IF NOT EXISTS retracted_at", texto)


class TestCarimboISO8601(unittest.TestCase):
    """A Data Manager pede ISO 8601 estrito. A API antiga aceitava espaço.

    Trocar de API sem trocar o separador faria todo evento ser recusado, e a
    mensagem do Google não aponta para o formato.
    """

    def _formata(self, dt):
        import importlib.util
        spec = importlib.util.spec_from_file_location("up_fmt", UPLOADER)
        # Importar o módulo inteiro puxaria boto3 e o PostgresService; só o
        # formatador interessa, então ele é lido e avaliado isolado.
        texto = fonte(UPLOADER)
        arvore = ast.parse(texto)
        alvo = next(n for n in arvore.body
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "_format_conversion_dt")
        escopo = {}
        preambulo = ("from datetime import datetime, timezone\n"
                     "from zoneinfo import ZoneInfo\n"
                     '_SP_TZ = ZoneInfo("America/Sao_Paulo")\n')
        exec(preambulo + ast.unparse(alvo), escopo)  # noqa: S102
        return escopo["_format_conversion_dt"](dt)

    def test_usa_T_como_separador(self):
        from datetime import datetime, timezone
        saida = self._formata(datetime(2026, 9, 15, 17, 30, tzinfo=timezone.utc))

        self.assertIn("T", saida)
        self.assertNotIn(" ", saida)

    def test_converte_para_o_fuso_de_sao_paulo(self):
        """17:30 UTC é 14:30 em São Paulo. Carimbar -03:00 sobre a hora UTC
        deslocaria toda conversão em três horas."""
        from datetime import datetime, timezone
        saida = self._formata(datetime(2026, 9, 15, 17, 30, tzinfo=timezone.utc))

        self.assertEqual(saida, "2026-09-15T14:30:00-03:00")


class TestTransporteDataManager(unittest.TestCase):
    """Comportamento do transporte novo, com a rede mockada."""

    def _servico(self):
        import importlib
        import sys
        sys.path.insert(0, os.path.normpath(os.path.join(RAIZ, "..")))
        modulo = importlib.import_module("src.services.data_manager_service")
        servico = modulo.DataManagerService()
        servico._token = "token-de-teste"  # evita o refresh real
        return modulo, servico

    def _conversoes(self, quantas=2):
        return [
            {"identifier": "id-%d" % i, "gclid": "gclid-%d" % i,
             "conversion_date_time": "2026-09-15T14:30:00-03:00",
             "conversion_value": 280.0}
            for i in range(quantas)
        ]

    def test_sucesso_devolve_os_identifiers(self):
        modulo, servico = self._servico()
        resposta = mock.Mock(status_code=200, content=b"{}")
        resposta.json.return_value = {"requestId": "req-1"}

        with mock.patch.object(modulo.requests, "post", return_value=resposta):
            r = servico.ingest_offline_conversions("4601912200", "7699541177",
                                                   self._conversoes())

        self.assertTrue(r["success"])
        self.assertEqual(r["uploaded_identifiers"], ["id-0", "id-1"])
        self.assertEqual(r["failed"], 0)

    def test_erro_http_nao_devolve_identifier_nenhum(self):
        """Marcar como enviado o que falhou faz a conversão desaparecer para
        sempre: ninguém tentaria de novo."""
        modulo, servico = self._servico()
        resposta = mock.Mock(status_code=403, content=b"sem permissao",
                             text="PERMISSION_DENIED")

        with mock.patch.object(modulo.requests, "post", return_value=resposta):
            r = servico.ingest_offline_conversions("4601912200", "7699541177",
                                                   self._conversoes())

        self.assertFalse(r["success"])
        self.assertEqual(r["uploaded_identifiers"], [])
        self.assertEqual(r["failed"], 2)
        self.assertIn("PERMISSION_DENIED", r["error"])

    def test_validate_only_nao_marca_nada_como_enviado(self):
        """O ensaio não grava no Google. Marcar `uploaded_at` queimaria a
        conversão sem ela ter subido."""
        modulo, servico = self._servico()
        resposta = mock.Mock(status_code=200, content=b"{}")
        resposta.json.return_value = {}

        with mock.patch.object(modulo.requests, "post", return_value=resposta) as post:
            r = servico.ingest_offline_conversions(
                "4601912200", "7699541177", self._conversoes(), validate_only=True)

        self.assertEqual(r["uploaded_identifiers"], [])
        self.assertEqual(r["validated"], 2)
        self.assertIs(post.call_args.kwargs["json"]["validateOnly"], True)

    def test_zerar_envia_valor_zero_com_o_mesmo_transaction_id(self):
        modulo, servico = self._servico()
        resposta = mock.Mock(status_code=200, content=b"{}")
        resposta.json.return_value = {"requestId": "req-2"}

        with mock.patch.object(modulo.requests, "post", return_value=resposta) as post:
            servico.restate_cancelled_to_zero("4601912200", "7699541177",
                                              self._conversoes(1))

        evento = post.call_args.kwargs["json"]["events"][0]
        self.assertEqual(evento["conversionValue"], 0.0)
        self.assertEqual(evento["transactionId"], "id-0")

    def test_o_destino_usa_a_conversion_action_como_productDestinationId(self):
        modulo, servico = self._servico()
        resposta = mock.Mock(status_code=200, content=b"{}")
        resposta.json.return_value = {}

        with mock.patch.object(modulo.requests, "post", return_value=resposta) as post:
            servico.ingest_offline_conversions(
                "460-191-2200", "7699541177", self._conversoes(1),
                login_customer_id="123-456-7890")

        destino = post.call_args.kwargs["json"]["destinations"][0]
        self.assertEqual(destino["productDestinationId"], "7699541177")
        # hifens saem: a API quer o id puro
        self.assertEqual(destino["operatingAccount"]["accountId"], "4601912200")
        self.assertEqual(destino["loginAccount"]["accountId"], "1234567890")

    def test_manda_event_source(self):
        """A referência REST diz que é opcional; o destino do Google Ads exige.

        O primeiro ensaio em produção (03/10/2026) voltou
        `events.events[0].event_source: Required field is missing`. Sem este
        teste, alguém "limpando campo redundante" reintroduz a falha.
        """
        modulo, servico = self._servico()
        resposta = mock.Mock(status_code=200, content=b"{}")
        resposta.json.return_value = {}

        with mock.patch.object(modulo.requests, "post", return_value=resposta) as post:
            servico.ingest_offline_conversions("4601912200", "7699541177",
                                               self._conversoes(1))

        self.assertEqual(post.call_args.kwargs["json"]["events"][0]["eventSource"],
                         "IN_STORE")

    def test_o_erro_do_google_nao_e_truncado_cedo(self):
        """`fieldViolations` traz uma entrada por campo. Cortar em 800 escondeu
        quantas violações existiam no primeiro ensaio."""
        self.assertIn("resposta.text[:4000]", fonte(DATA_MANAGER))

    def test_lista_vazia_nao_chama_a_rede(self):
        modulo, servico = self._servico()

        with mock.patch.object(modulo.requests, "post") as post:
            r = servico.ingest_offline_conversions("4601912200", "7699541177", [])

        post.assert_not_called()
        self.assertTrue(r["success"])

    def test_credencial_ausente_falha_com_mensagem_util(self):
        """O erro tem de dizer QUAL variável falta e qual escopo é exigido -
        senão o diagnóstico vira adivinhação, como o `501` de hoje."""
        modulo, servico = self._servico()
        servico._token = None

        with mock.patch.dict(os.environ, {"OAUTH2_CLIENT_ID": "",
                                          "OAUTH2_CLIENT_SECRET": "",
                                          "DATA_MANAGER_REFRESH_TOKEN": ""},
                             clear=False):
            with self.assertRaises(ValueError) as ctx:
                servico._bearer()

        self.assertIn("DATA_MANAGER_REFRESH_TOKEN", str(ctx.exception))
        self.assertIn("datamanager", str(ctx.exception))


class TestOsArquivosCompilam(unittest.TestCase):
    def test_ast_valido(self):
        for caminho in (UPLOADER, CLIENTE, DATA_MANAGER):
            with self.subTest(os.path.basename(caminho)):
                ast.parse(fonte(caminho))


if __name__ == "__main__":
    unittest.main()


class TestAPeriodicidadeNaoDivergiu(unittest.TestCase):
    """O cron e afirmado em 7 lugares. Divergir nao levanta erro em lugar nenhum.

    Em 03/10/2026 a periodicidade mudou de semanal para o ultimo dia do mes, e
    um dos lugares era texto que a clinica LE no painel ("O envio roda toda
    segunda"). Um desses esquecido mente para o usuario, em silencio.

    Este teste cobre o par mais perigoso: o cron de fato (interface.yml) contra
    o docstring do modulo que o descreve. Os outros cinco estao listados no
    proprio docstring do uploader.
    """

    INTERFACE = os.path.join(
        os.path.dirname(__file__), "..", "..", "sls", "functions",
        "conversions", "interface.yml")

    def _cron(self):
        texto = fonte(os.path.normpath(self.INTERFACE))
        m = re.search(r"rate:\s*(cron\([^)]*\))", texto)
        self.assertIsNotNone(m, "nao achei o cron no interface.yml")
        return m.group(1)

    def test_o_cron_e_mensal_no_ultimo_dia(self):
        """`L` no campo dia-do-mes. Se alguem voltar para `? * MON *`, o
        docstring e o texto do painel passam a mentir."""
        cron = self._cron()

        self.assertIn(" L ", cron, "o cron deixou de ser no ultimo dia do mes: %s" % cron)

    def test_o_docstring_concorda_com_o_cron(self):
        cron = self._cron()
        doc = fonte(UPLOADER)[:2000]

        if " L " in cron:
            self.assertIn("ULTIMO DIA", doc,
                           "o cron e mensal mas o docstring nao diz isso")
            self.assertNotIn("Roda toda segunda", doc)
        else:
            self.assertNotIn("ULTIMO DIA", doc,
                             "o docstring diz mensal mas o cron nao e")

    def test_o_docstring_lista_onde_mais_a_periodicidade_aparece(self):
        """Sem a lista, quem muda o cron nao tem como saber o que mais mudar."""
        doc = fonte(UPLOADER)[:2000]

        self.assertIn("LeadsPage.tsx", doc)
        self.assertIn("interface.yml", doc)
