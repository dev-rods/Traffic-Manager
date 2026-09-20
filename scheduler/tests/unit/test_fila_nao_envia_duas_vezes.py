# -*- coding: utf-8 -*-
"""O mesmo item da fila não sai duas vezes.

Caso real de 18/09/2026, Ana Clara. Um item na fila, `attempts: 2`, duas
mensagens de abertura com redação diferente:

    14:54:16  IniciarBot enfileira 125ad058 e acorda o dispatcher
    14:54:17  OutboundProcessor [d93fa8] START  -> leu o item PENDING
    14:54:23  OutboundProcessor [9d99ea] START  -> leu o MESMO item PENDING
    14:54:25  [d93fa8] enviou
    14:54:30  [9d99ea] enviou de novo

`pending_due` lê os itens PENDING e o `mark_sent` só acontece DEPOIS do envio -
uma janela de ~8 segundos, que é o tempo do agente escrever. Entre uma coisa e
outra não havia nada que dissesse "este item é meu".

A segunda execução foi o CRON, não um segundo clique: a cadência do dia mostra
14:24:23, 14:34:23, 14:44:23, 14:54:23, 15:04:22 - `rate(10 minutes)`, sempre no
segundo :23. Ou seja, não depende de comportamento humano nenhum: o cron roda
144 vezes por dia e todo clique abre a janela.

O cabeçalho do processador diz que "o próprio intervalo do cron é o limitador,
não precisa de lock". Era verdade antes de existir o `_acorda_o_dispatcher`,
que foi adicionado para a atendente não esperar 10 minutos olhando "na fila".
Duas decisões boas isoladamente; a interação entre elas é que falha.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from tests.unit.test_abordagem_com_retry import AGORA, CLINICA, FilaFalsa, item
import src.functions.outbound.processor as proc


def roda(itens, tomado_por_outro=False, falar_ok=(True, 1)):
    fila = FilaFalsa()
    fila._pendentes = itens
    fila.tomado_por_outro = tomado_por_outro
    db = mock.MagicMock()
    db.execute_query.return_value = [dict(CLINICA)]

    with mock.patch.object(proc, "OutboundQueueService", return_value=fila), \
         mock.patch.object(proc, "MessageTracker"), \
         mock.patch.object(proc, "PostgresService", return_value=db), \
         mock.patch.object(proc, "get_provider"), \
         mock.patch.object(proc, "_sessions_table"), \
         mock.patch.object(proc, "mark_conversation_eligible"), \
         mock.patch.object(proc, "_ja_esta_conversando", return_value=False), \
         mock.patch.object(proc, "falar", return_value=falar_ok) as falar, \
         mock.patch.object(proc, "datetime") as dt:
        dt.now.return_value = AGORA
        proc.handler({}, None)
    return fila.acoes, falar


class TestOItemEReivindicadoAntesDeEnviar(unittest.TestCase):
    def test_reivindica_antes_de_falar(self):
        """Se a reivindicação sumir, duas execuções voltam a enviar o mesmo item."""
        acoes, _ = roda([item()])

        nomes = [a[0] for a in acoes]
        self.assertIn("reivindicou", nomes,
                      "o item foi enviado sem ser reivindicado")
        self.assertLess(nomes.index("reivindicou"), nomes.index("enviou"),
                        "reivindicar DEPOIS de enviar não impede duplicata")


class TestQuemPerdeACorridaNaoEnvia(unittest.TestCase):
    """A segunda execução chega, encontra o item já tomado, e sai."""

    def test_nao_chama_o_agente(self):
        """Importa não só o envio: chamar o agente à toa custa uma chamada paga
        ao modelo, e foi o que gerou o segundo texto diferente."""
        acoes, falar = roda([item()], tomado_por_outro=True)

        falar.assert_not_called()

    def test_nao_marca_como_enviado(self):
        acoes, _ = roda([item()], tomado_por_outro=True)

        nomes = [a[0] for a in acoes]
        self.assertIn("perdeu_a_corrida", nomes)
        self.assertNotIn("enviou", nomes)

    def test_e_nao_marca_falha(self):
        """Perder a corrida é normal, não é erro: o item foi enviado por quem
        ganhou. Marcar FAILED poluiria o painel com falha que não houve."""
        acoes, _ = roda([item()], tomado_por_outro=True)

        self.assertNotIn("falha", [a[0] for a in acoes])


class TestAReivindicacaoNaoAtrapalhaQuemAdia(unittest.TestCase):
    """Uma guarda acima pode adiar, e adiar precisa deixar o item em PENDING
    para a próxima execução. Por isso a reivindicação fica no fim, e não no
    topo do laço."""

    def test_item_vencido_nao_e_reivindicado(self):
        vencido = item(expiresAt=(AGORA - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        acoes, _ = roda([vencido])

        nomes = [a[0] for a in acoes]
        self.assertNotIn("reivindicou", nomes)
        self.assertIn("expira", nomes)

    def test_fora_do_horario_nao_e_reivindicado(self):
        fechada = dict(CLINICA, business_hours={})
        fila = FilaFalsa()
        fila._pendentes = [item()]
        db = mock.MagicMock()
        db.execute_query.return_value = [fechada]

        with mock.patch.object(proc, "OutboundQueueService", return_value=fila), \
             mock.patch.object(proc, "MessageTracker"), \
             mock.patch.object(proc, "PostgresService", return_value=db), \
             mock.patch.object(proc, "get_provider"), \
             mock.patch.object(proc, "_sessions_table"), \
             mock.patch.object(proc, "mark_conversation_eligible"), \
             mock.patch.object(proc, "_ja_esta_conversando", return_value=False), \
             mock.patch.object(proc, "is_open", return_value=False), \
             mock.patch.object(proc, "falar", return_value=(True, 1)), \
             mock.patch.object(proc, "datetime") as dt:
            dt.now.return_value = AGORA
            proc.handler({}, None)

        nomes = [a[0] for a in fila.acoes]
        self.assertNotIn("reivindicou", nomes,
                         "item adiado não pode ser reivindicado: ele precisa "
                         "continuar PENDING para a próxima execução")
        self.assertIn("adia", nomes)


if __name__ == "__main__":
    unittest.main()
