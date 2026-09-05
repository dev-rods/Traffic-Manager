"""Guardas contra disparo indevido de abordagem ativa.

Há 44 leads cadastrados, vários com conversa em andamento com atendentes humanos.
Uma mensagem enviada por engano chega no WhatsApp de uma pessoa real e não tem
desfazer, então cada guarda é testada isoladamente e em conjunto.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

from src.functions.lead.create import should_start_conversation

AGORA = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
PILOTO = "5511970521647"
CLINICA = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO]}


def _lead(**over):
    lead = {
        "phone": PILOTO,
        "source": "landing-page",
        "created_at": AGORA,
        "updated_at": AGORA,
    }
    lead.update(over)
    return lead


class TestLeadNovo(unittest.TestCase):
    def test_lead_novo_da_landing_page_dispara(self):
        self.assertTrue(should_start_conversation(_lead(), CLINICA, agora=AGORA))

    def test_lead_recorrente_nao_dispara(self):
        """Caiu em UPDATE no upsert: já existia, não é primeiro contato."""
        lead = _lead(created_at=AGORA - timedelta(days=30))

        self.assertFalse(should_start_conversation(lead, CLINICA, agora=AGORA))


class TestOrigem(unittest.TestCase):
    def test_whatsapp_nao_dispara(self):
        """Lead de whatsapp já está conversando: abordar seria falar por cima."""
        self.assertFalse(should_start_conversation(_lead(source="whatsapp"), CLINICA, agora=AGORA))

    def test_harmonizacao_nao_dispara(self):
        self.assertFalse(should_start_conversation(_lead(source="harmonizacao"), CLINICA, agora=AGORA))

    def test_origem_ausente_nao_dispara(self):
        self.assertFalse(should_start_conversation(_lead(source=None), CLINICA, agora=AGORA))


class TestIdade(unittest.TestCase):
    def test_lead_antigo_nao_dispara_mesmo_parecendo_novo(self):
        """A guarda que protege contra backfill.

        Um script que reprocessasse leads antigos criaria linhas com
        created_at == updated_at, passando pela primeira guarda. A idade barra.
        """
        antigo = AGORA - timedelta(hours=2)
        lead = _lead(created_at=antigo, updated_at=antigo)

        self.assertFalse(should_start_conversation(lead, CLINICA, agora=AGORA))

    def test_lead_de_um_minuto_atras_dispara(self):
        recente = AGORA - timedelta(minutes=1)
        lead = _lead(created_at=recente, updated_at=recente)

        self.assertTrue(should_start_conversation(lead, CLINICA, agora=AGORA))

    def test_exatamente_no_limite_nao_dispara(self):
        limite = AGORA - timedelta(minutes=11)
        lead = _lead(created_at=limite, updated_at=limite)

        self.assertFalse(should_start_conversation(lead, CLINICA, agora=AGORA))

    def test_created_at_sem_timezone_e_lido_como_utc(self):
        """O psycopg2 pode devolver naive dependendo da coluna."""
        naive = datetime(2026, 9, 1, 11, 59)
        lead = _lead(created_at=naive, updated_at=naive)

        self.assertTrue(should_start_conversation(lead, CLINICA, agora=AGORA))

    def test_sem_created_at_nao_dispara(self):
        self.assertFalse(should_start_conversation(_lead(created_at=None, updated_at=None),
                                                   CLINICA, agora=AGORA))


class TestPolitica(unittest.TestCase):
    """A politica saiu do enfileiramento e passou a ser conferida no DISPARO.

    Ela era conferida aqui, e o efeito foi caro: com o piloto ligado o lead nem
    entrava na fila, e desligar o piloto depois nao trazia ninguem de volta - a
    decisao tinha sido tomada e descartada num instante que nao volta.

    A garantia continua valendo, so mudou de lugar: quem nao pode receber
    continua nao recebendo. Os testes disso vivem em
    `test_abordagem_com_retry.py`, contra o processor.
    """

    def test_enfileira_mesmo_com_politica_restritiva(self):
        for clinic in (CLINICA,
                       {"bot_autoreply_policy": "OFF"},
                       {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": []}):
            with self.subTest(policy=clinic.get("bot_autoreply_policy")):
                self.assertTrue(should_start_conversation(
                    _lead(phone="5511988887777"), clinic, agora=AGORA))

    def test_o_que_e_imutavel_continua_decidindo_aqui(self):
        """Origem, telefone e primeiro contato nao mudam entre o cadastro e o
        envio - conferir no disparo so adiaria a mesma resposta."""
        self.assertFalse(should_start_conversation(_lead(source="whatsapp"), CLINICA, agora=AGORA))
        self.assertFalse(should_start_conversation(_lead(phone=""), CLINICA, agora=AGORA))


class TestEntradasInvalidas(unittest.TestCase):
    def test_lead_none(self):
        self.assertFalse(should_start_conversation(None, CLINICA, agora=AGORA))

    def test_clinica_none(self):
        self.assertFalse(should_start_conversation(_lead(), None, agora=AGORA))

    def test_sem_telefone(self):
        self.assertFalse(should_start_conversation(_lead(phone=None), CLINICA, agora=AGORA))


if __name__ == "__main__":
    unittest.main()
