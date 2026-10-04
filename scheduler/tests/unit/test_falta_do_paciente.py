# -*- coding: utf-8 -*-
"""Falta (`NO_SHOW`) é diferente de cancelamento, e a conversão depende disso.

Até 04/10/2026 o scheduler só tinha `CONFIRMED` e `CANCELLED`. Medido em
produção: **604 dos 618** CONFIRMED tinham data passada e ficavam assim para
sempre, e o prontuário - a outra fonte possível de presença - cobria **4%** das
sessões passadas. Um no-show era indistinguível de uma sessão realizada.

Isso importa porque a conversion action `Agendamento Real (Offline)` é uma
**COMPRA** (`PURCHASE`, com `final_price_cents`), e compra exige comparecimento.
Sem este status, `CONFIRMED` com data passada significava apenas "ninguém
cancelou", e um no-show subia ao Google Ads como venda.

Quem cancela com antecedência libera a agenda; quem não aparece queima o
horário. Os dois viravam `CANCELLED`, e a diferença se perdia.
"""
import ast
import os
import unittest
from unittest import mock

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "src")
SERVICE = os.path.join(RAIZ, "services", "appointment_service.py")
HANDLER = os.path.join(RAIZ, "functions", "appointment", "update.py")
SETUP = os.path.join(RAIZ, "scripts", "setup_database.py")


def fonte(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def _servico(retorno):
    """AppointmentService com o banco mockado, devolvendo `retorno`."""
    from src.services.appointment_service import AppointmentService

    db = mock.MagicMock()
    db.execute_write_returning.return_value = retorno
    return AppointmentService(db=db), db


class TestMarcarFalta(unittest.TestCase):
    def test_grava_no_show_e_devolve_a_linha(self):
        servico, db = _servico({"id": "abc", "status": "NO_SHOW"})

        resultado = servico.marca_no_show("abc")

        self.assertEqual(resultado["status"], "NO_SHOW")
        sql = db.execute_write_returning.call_args.args[0]
        self.assertIn("status = 'NO_SHOW'", sql)

    def test_os_tres_filtros_estao_no_WHERE(self):
        """Consultar primeiro e escrever depois deixa janela entre as duas: a
        recepção marca falta no mesmo instante em que a paciente cancela pelo
        bot, e o segundo UPDATE sobrescreve o primeiro sem ninguém notar.

        No WHERE, o banco decide, e quem perdeu recebe NotFoundError.
        """
        servico, db = _servico({"id": "abc"})

        servico.marca_no_show("abc")

        sql = " ".join(db.execute_write_returning.call_args.args[0].split())
        self.assertIn("WHERE id = %s::uuid", sql)
        self.assertIn("status = 'CONFIRMED'", sql)
        # Data de SÃO PAULO, não do servidor: o banco roda em UTC, que está à
        # frente do Brasil. Entre 21h e meia-noite BRT o `CURRENT_DATE` já é
        # amanhã, e a sessão de hoje poderia receber falta antes de terminar.
        self.assertIn("appointment_date < (NOW() AT TIME ZONE", sql)
        self.assertNotIn("appointment_date < CURRENT_DATE", sql)

    def test_incrementa_a_version(self):
        """A tabela usa lock otimista; pular o incremento faria uma edição
        concorrente passar por cima sem conflito."""
        servico, db = _servico({"id": "abc"})

        servico.marca_no_show("abc")

        self.assertIn("version = version + 1",
                      db.execute_write_returning.call_args.args[0])

    def test_sem_linha_levanta_NotFoundError(self):
        from src.services.appointment_service import NotFoundError

        servico, _ = _servico([])

        with self.assertRaises(NotFoundError):
            servico.marca_no_show("abc")

    def test_a_mensagem_de_erro_distingue_os_casos(self):
        """São ações diferentes de quem lê: sessão futura é "espere", status
        errado é "já está resolvido"."""
        from src.services.appointment_service import NotFoundError

        servico, _ = _servico(None)

        with self.assertRaises(NotFoundError) as ctx:
            servico.marca_no_show("abc")

        msg = str(ctx.exception)
        self.assertIn("CONFIRMED", msg)
        self.assertIn("ainda nao aconteceu", msg)


class TestDesmarcarFalta(unittest.TestCase):
    def test_volta_para_confirmed(self):
        servico, db = _servico({"id": "abc", "status": "CONFIRMED"})

        servico.desmarca_no_show("abc")

        sql = " ".join(db.execute_write_returning.call_args.args[0].split())
        self.assertIn("status = 'CONFIRMED'", sql)

    def test_so_age_sobre_quem_esta_em_falta(self):
        """Sem `status = 'NO_SHOW'` no WHERE, desmarcar falta viraria um jeito
        oblíquo de descancelar - e cancelamento já liberou o horário, que pode
        ter sido ocupado por outra pessoa.
        """
        servico, db = _servico({"id": "abc"})

        servico.desmarca_no_show("abc")

        sql = " ".join(db.execute_write_returning.call_args.args[0].split())
        self.assertIn("status = 'NO_SHOW'", sql)

    def test_sem_linha_levanta_NotFoundError(self):
        from src.services.appointment_service import NotFoundError

        servico, _ = _servico([])

        with self.assertRaises(NotFoundError):
            servico.desmarca_no_show("abc")


class TestFaltaNaoMexeNaMarcaDeEstreia(unittest.TestCase):
    """`passa_a_marca_adiante` move `is_first_visit` e NÃO tem inverso.

    Como marcar falta é reversível, espelhá-la tornaria o desmarcar lossy: a
    marca de estreia não voltaria. A decisão está documentada no docstring de
    `marca_no_show`, e este teste impede que alguém a desfaça "por simetria com
    o cancelamento".

    O preço está registrado: quem falta na estreia mantém a marca na linha da
    falta, e a sessão em que de fato pisa na clínica aparece como veterana.
    """

    def _chamadas(self, nome):
        """Nomes CHAMADOS dentro da função - não mencionados.

        A diferença importa: o docstring de `marca_no_show` cita
        `passa_a_marca_adiante` de propósito, para explicar por que ela NÃO é
        chamada. Uma busca por texto acharia a explicação e reprovaria o
        código correto.
        """
        for no in ast.walk(ast.parse(fonte(SERVICE))):
            if isinstance(no, ast.FunctionDef) and no.name == nome:
                chamados = set()
                for interno in ast.walk(no):
                    if not isinstance(interno, ast.Call):
                        continue
                    alvo = interno.func
                    if isinstance(alvo, ast.Name):
                        chamados.add(alvo.id)
                    elif isinstance(alvo, ast.Attribute):
                        chamados.add(alvo.attr)
                return chamados
        self.fail("funcao %s nao encontrada" % nome)

    def test_marcar_nao_chama_passa_a_marca_adiante(self):
        self.assertNotIn("passa_a_marca_adiante", self._chamadas("marca_no_show"))

    def test_desmarcar_nao_chama_passa_a_marca_adiante(self):
        self.assertNotIn("passa_a_marca_adiante", self._chamadas("desmarca_no_show"))

    def test_cancelar_CONTINUA_chamando(self):
        """A decisão de 09/09/2026 vale para cancelamento e não foi revogada."""
        self.assertIn("passa_a_marca_adiante", self._chamadas("cancel_appointment"))

    def test_nenhum_dos_dois_toca_lembrete(self):
        """Só se marca falta de sessão que já passou - o lembrete dela já
        disparou, e cancelá-lo seria trabalho sem efeito."""
        for nome in ("marca_no_show", "desmarca_no_show"):
            with self.subTest(nome):
                self.assertNotIn("cancel_reminder", self._chamadas(nome))

    def test_a_razao_esta_escrita_no_codigo(self):
        """Sem o porquê registrado, a assimetria parece descuido."""
        self.assertIn("nao tem inverso", fonte(SERVICE))


class TestOStatusEValidadoAntesDeEscrever(unittest.TestCase):
    """O status era escrito CRU, sem lista de valores aceitos.

    Um typo como "NOSHOW" era gravado em silêncio e tirava o agendamento das
    DUAS queries do uploader de conversão: não elegível (`= CONFIRMED`) e sem
    valor zerado (`= CANCELLED`). A conversão ficava órfã - viva no Google e
    invisível aqui.
    """

    def test_existe_lista_de_status_validos(self):
        texto = fonte(HANDLER)

        self.assertIn("STATUS_VALIDOS", texto)
        for s in ("CONFIRMED", "CANCELLED", "NO_SHOW"):
            self.assertIn(s, texto)

    def test_a_validacao_vem_antes_de_qualquer_escrita(self):
        """Validar depois do primeiro UPDATE deixaria metade da operação feita
        com um status que a outra metade recusa."""
        texto = fonte(HANDLER)

        pos_validacao = texto.index("status invalido")
        pos_cancel = texto.index("service.cancel_appointment")
        pos_update = texto.index("UPDATE scheduler.appointments")

        self.assertLess(pos_validacao, pos_cancel)
        self.assertLess(pos_validacao, pos_update)

    def test_falta_e_exclusiva_como_o_cancelamento(self):
        """O guard de "sessão já passou" vive no WHERE do UPDATE. Combinar com
        um reschedule no mesmo pedido mudaria a data que o guard confere."""
        texto = fonte(HANDLER)

        self.assertIn('if new_status == "NO_SHOW":', texto)
        self.assertIn("service.marca_no_show", texto)

    def test_confirmed_sobre_cancelado_e_recusado(self):
        """Sem isso, `status = CONFIRMED` cairia no UPDATE genérico e passaria
        por cima de CANCELLED - descancelando um horário que pode já ter sido
        ocupado."""
        texto = fonte(HANDLER)

        self.assertIn('if atual[0]["status"] == "CANCELLED":', texto)
        self.assertIn("409", texto)


class TestAMigrationExiste(unittest.TestCase):
    def test_a_constraint_lista_os_tres_status(self):
        texto = fonte(SETUP)

        self.assertIn("appointments_status_check", texto)
        self.assertIn("'CONFIRMED', 'CANCELLED', 'NO_SHOW'", texto)

    def test_e_idempotente(self):
        """O script é reexecutável por convenção do projeto."""
        texto = fonte(SETUP)

        self.assertIn("DROP CONSTRAINT IF EXISTS appointments_status_check", texto)
        self.assertIn("WHERE conname = 'appointments_status_check'", texto)

    def test_aceita_NULL(self):
        """A coluna é nullable e o default nunca preencheu linha antiga; uma
        CHECK que proibisse NULL reprovaria essas linhas."""
        texto = fonte(SETUP)

        self.assertIn("status IS NULL OR status IN", texto)

    def test_o_create_table_ficou_em_sincronia(self):
        """Convenção do CLAUDE.md: `CREATE TABLE` e migration não divergem."""
        texto = fonte(SETUP)
        i = texto.index("status VARCHAR(20) DEFAULT 'CONFIRMED'")

        self.assertIn("NO_SHOW", texto[i - 400:i])


class TestOsArquivosCompilam(unittest.TestCase):
    def test_ast_valido(self):
        for caminho in (SERVICE, HANDLER, SETUP):
            with self.subTest(os.path.basename(caminho)):
                ast.parse(fonte(caminho))


if __name__ == "__main__":
    unittest.main()
