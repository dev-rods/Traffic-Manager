"""A decisão de enviar, no momento do disparo ativo.

O dispatcher reconfere a política antes de enviar, porque a configuração pode ter
mudado depois que o item entrou na fila. Mas a sessão ainda não existe nesse
momento: é o próprio envio que vai criá-la.

Passar sessão vazia fazia a política LEADS_ONLY recusar todo item com
"politica_nao_permite", e o cenário de abordagem ativa nunca enviava nada. O bug
foi exatamente esse e só apareceu ao olhar a fila em produção — os testes cobriam
o enfileiramento, não o disparo.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

from src.services.bot_policy import should_bot_reply

# A sessão que o dispatcher passa: a elegibilidade vem do enfileiramento, não da
# sessão, que ainda não existe.
SESSAO_DO_DISPATCH = {"bot_enabled": True}
TELEFONE = "5511963352425"


class TestDispatchPorPolitica(unittest.TestCase):
    def test_leads_only_permite_enviar(self):
        """O caso que quebrou: item enfileirado, política LEADS_ONLY, sessão inexistente."""
        clinic = {"bot_autoreply_policy": "LEADS_ONLY"}

        self.assertTrue(should_bot_reply(clinic, SESSAO_DO_DISPATCH, TELEFONE))

    def test_sessao_vazia_seria_recusada(self):
        """Documenta o bug: é isso que acontecia antes da correção."""
        clinic = {"bot_autoreply_policy": "LEADS_ONLY"}

        self.assertFalse(should_bot_reply(clinic, {}, TELEFONE))

    def test_all_permite_enviar(self):
        self.assertTrue(should_bot_reply({"bot_autoreply_policy": "ALL"}, SESSAO_DO_DISPATCH, TELEFONE))

    def test_off_recusa(self):
        """Clínica que desligou o bot depois do enfileiramento não deve abordar."""
        self.assertFalse(should_bot_reply({"bot_autoreply_policy": "OFF"}, SESSAO_DO_DISPATCH, TELEFONE))

    def test_pilot_com_telefone_na_lista_permite(self):
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [TELEFONE]}

        self.assertTrue(should_bot_reply(clinic, SESSAO_DO_DISPATCH, TELEFONE))

    def test_pilot_com_telefone_fora_da_lista_recusa(self):
        """Item enfileirado durante o piloto, telefone removido da lista depois."""
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": ["5511900000000"]}

        self.assertFalse(should_bot_reply(clinic, SESSAO_DO_DISPATCH, TELEFONE))


if __name__ == "__main__":
    unittest.main()
