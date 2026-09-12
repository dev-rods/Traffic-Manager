"""De quem é a conversa, a partir dos payloads que o z-api manda de verdade.

Todos os corpos abaixo foram COPIADOS DOS LOGS de produção da conversa de
02/09/2026 com +5511970522647, não escritos à mão. A correção anterior falhou
justamente porque testei um payload que eu supus - com o número no campo
`phone` - enquanto o z-api mandava o LID.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.identidade_whatsapp import (
    chat_lid,
    deve_vincular_lid,
    telefone_da_conversa,
)

TELEFONE = "5511970522647"
LID = "176209673617532@lid"
NUMERO_DA_CLINICA = "5511963352425"

# ── Payloads reais, 02/09/2026 ────────────────────────────────────────────

CLIENTE_ESCREVEU = {  # 22:53:34
    "isStatusReply": False, "chatLid": LID, "connectedPhone": NUMERO_DA_CLINICA,
    "isGroup": False, "instanceId": "3F143E782FFCB14D71B9E29123FA23F4",
    "messageId": "3ACFE55F507CAC71D636", "phone": TELEFONE, "fromMe": False,
}

ECO_DO_BOT = {  # 22:53:39 — resposta enviada pela API
    "isStatusReply": False, "chatLid": LID, "connectedPhone": NUMERO_DA_CLINICA,
    "isGroup": False, "instanceId": "3F143E782FFCB14D71B9E29123FA23F4",
    "messageId": "3EB0FA99060A2B2F9BE336", "phone": TELEFONE,
    "fromMe": True, "status": "SENT",
}

ATENDENTE_NO_CELULAR = {  # 22:54:54 — a que era descartada
    "isStatusReply": False, "chatLid": LID, "connectedPhone": NUMERO_DA_CLINICA,
    "isGroup": False, "instanceId": "3F143E782FFCB14D71B9E29123FA23F4",
    "messageId": "3CF06BF15332DB483465", "phone": LID,
    "fromMe": True, "status": "RECEIVED", "chatName": "Amor ❤",
    "senderName": "Clínica Essência Estética",
}

MENSAGEM_DE_GRUPO = {  # 22:54:46
    "isStatusReply": False, "chatLid": None, "connectedPhone": NUMERO_DA_CLINICA,
    "isGroup": True, "instanceId": "3F143E782FFCB14D71B9E29123FA23F4",
    "messageId": "2A5C0C2191DE1948C19A", "phone": "120363160897729121-group",
    "fromMe": True,
}

SELF_CHAT = {  # 22:54:46 — a clínica falando com o próprio número
    "chatLid": "138418222801140@lid", "isGroup": False,
    "instanceId": "3F143E782FFCB14D71B9E29123FA23F4",
    "phone": NUMERO_DA_CLINICA, "connectedPhone": NUMERO_DA_CLINICA,
    "fromMe": True, "fromApi": False, "status": "RECEIVED",
}


class TestTelefoneDaConversa(unittest.TestCase):
    def test_cliente_escrevendo(self):
        self.assertEqual(telefone_da_conversa(CLIENTE_ESCREVEU), TELEFONE)

    def test_eco_do_bot_traz_o_numero(self):
        self.assertEqual(telefone_da_conversa(ECO_DO_BOT), TELEFONE)

    def test_atendente_no_celular_resolve_pelo_lid(self):
        """O caso que quebrou: sem o vínculo, a mensagem era descartada."""
        self.assertEqual(
            telefone_da_conversa(ATENDENTE_NO_CELULAR, telefone_do_lid=TELEFONE),
            TELEFONE,
        )

    def test_lid_desconhecido_continua_descartado(self):
        """Sem saber de quem é a conversa, manter o comportamento antigo."""
        self.assertIsNone(telefone_da_conversa(ATENDENTE_NO_CELULAR))

    def test_grupo_e_ignorado_mesmo_com_lid_conhecido(self):
        self.assertIsNone(telefone_da_conversa(MENSAGEM_DE_GRUPO, telefone_do_lid=TELEFONE))

    def test_self_chat_e_ignorado(self):
        """Evita o laço em que o bot responde a si mesmo."""
        self.assertIsNone(telefone_da_conversa(SELF_CHAT))

    def test_broadcast_e_ignorado(self):
        corpo = dict(CLIENTE_ESCREVEU, phone="120363000000000-broadcast")
        self.assertIsNone(telefone_da_conversa(corpo))

    def test_payload_sem_phone(self):
        self.assertIsNone(telefone_da_conversa({"chatLid": LID}))


class TestVinculoDoLid(unittest.TestCase):
    """Quais mensagens ensinam a quem pertence um LID."""

    def test_mensagem_do_cliente_ensina(self):
        self.assertTrue(deve_vincular_lid(CLIENTE_ESCREVEU))
        self.assertEqual(chat_lid(CLIENTE_ESCREVEU), LID)

    def test_eco_do_bot_ensina(self):
        self.assertTrue(deve_vincular_lid(ECO_DO_BOT))

    def test_mensagem_identificada_so_por_lid_nao_ensina(self):
        """Ela é justamente quem precisa da resposta; não pode ser a fonte."""
        self.assertFalse(deve_vincular_lid(ATENDENTE_NO_CELULAR))

    def test_grupo_nao_ensina(self):
        self.assertFalse(deve_vincular_lid(MENSAGEM_DE_GRUPO))

    def test_payload_sem_chatlid_nao_ensina(self):
        self.assertFalse(deve_vincular_lid({"phone": TELEFONE}))


class TestRoteamentoCompleto(unittest.TestCase):
    """A sequência real da conversa, na ordem em que aconteceu."""

    def test_a_conversa_de_02_09(self):
        vinculos = {}

        # 22:53:34 cliente escreve — ensina o vínculo
        tel = telefone_da_conversa(CLIENTE_ESCREVEU)
        self.assertEqual(tel, TELEFONE)
        if deve_vincular_lid(CLIENTE_ESCREVEU):
            vinculos[chat_lid(CLIENTE_ESCREVEU)] = tel

        # 22:53:39 bot responde
        self.assertEqual(telefone_da_conversa(ECO_DO_BOT), TELEFONE)

        # 22:54:54 atendente digita no celular — agora resolve
        tel_atendente = telefone_da_conversa(
            ATENDENTE_NO_CELULAR, telefone_do_lid=vinculos.get(chat_lid(ATENDENTE_NO_CELULAR))
        )
        self.assertEqual(
            tel_atendente, TELEFONE,
            "a mensagem digitada no celular precisa ser atribuída à conversa certa",
        )
