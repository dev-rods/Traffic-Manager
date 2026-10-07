# Detectar atendimento humano e pausar o bot

> **Para quem for executar:** as tarefas abaixo são independentes e testáveis uma a uma. Cada uma termina com teste passando e commit.

**Objetivo:** quando um funcionário responde a conversa pelo WhatsApp do celular, o bot deve se calar por 24 horas, e o painel deve permitir devolver o controle a ele antes disso.

**Arquitetura:** o webhook já recebe as mensagens que a clínica envia (`fromMe: true`), já tem a função que pausa o bot com TTL de 24h, e o painel já sabe reativar. O que falta é uma coisa só: distinguir a mensagem digitada no celular do eco das mensagens que o próprio bot mandou.

**Stack:** Python 3.13, AWS Lambda, DynamoDB, React 19 + TypeScript.

## O incidente que originou isto

01/09/2026, contato +5511971885299 (Lívia). A cliente foi atendida por uma funcionária pelo celular, e o bot respondeu por cima cinco vezes. A cliente percebeu: *"Nao adiantou me mandar mensagem pra passar a mesma informação que recebi semana passada kakaka"*.

## Restrições globais

- A pausa dura **24 horas**, renovadas a cada nova mensagem do atendente. É o TTL que já existe (`ATTENDANT_TTL_SECONDS`).
- Nenhuma mensagem enviada pelo próprio bot pode ser confundida com atendimento humano - isso pausaria o bot em toda resposta que ele desse.
- A reativação antecipada acontece **só pelo painel**.
- O comportamento atual de clínicas sem atendente humano não pode mudar.

---

## Estado atual do código

O bloco em `scheduler/src/functions/webhook/handler.py:63-111` já faz quase tudo:

```python
if body.get("fromMe", False):
    # Messages sent via API/bot arrive with status=SENT; ignore them
    if body.get("status") == "SENT":
        return http_response(200, {"status": "OK"})   # <-- sempre entra aqui

    # status != SENT → manual attendant message
    ...
    _activate_attendant_mode(clinic_id, phone)   # <-- nunca alcançado
```

A premissa `status == "SENT" significa bot` está errada: **mensagem digitada no celular também chega com `status: "SENT"`**. Confirmado no payload real do incidente:

```json
{"fromMe": true, "status": "SENT", "phone": "5511971885299",
 "messageId": "3EB0E3041A2A1041F6857D", "senderName": "Clínica Essência Estética"}
```

Como o `return` acontece antes, `_activate_attendant_mode` nunca roda. A funcionalidade existe e está inalcançável.

**O que já funciona e não precisa ser tocado:**

| peça | onde | estado |
|---|---|---|
| Pausa com TTL de 24h | `_activate_attendant_mode` (`handler.py:408`) | pronta |
| Respeito à pausa | `should_bot_reply` (`bot_policy.py`) | pronta |
| Reativação pelo painel | `_handle_deactivate` (`attendant/handler.py`) | pronta |
| Rótulo "Atendimento humano em andamento" | `ConversationThread.tsx` | pronto |
| Registro da mensagem do atendente | `handler.py:92-108` | pronto |

---

## Task 1: Distinguir o eco do bot da mensagem do celular

**Arquivos:**
- Criar: `scheduler/src/services/autoria_mensagem.py`
- Criar: `scheduler/tests/unit/test_autoria_mensagem.py`

**Interfaces:**
- Produz: `foi_enviada_pelo_bot(eventos: list, provider_message_id: str) -> bool`

O critério é factual, não heurístico: ao enviar, o bot grava o `providerMessageId` devolvido pelo z-api no MessageEvents (`message_tracker.py:51`). Se o `messageId` que chega no webhook está lá, o eco é do bot. Se não está, alguém digitou no celular.

Isso depende da correção de 30/08 em `get_conversation_messages`, que passou a devolver as mensagens **mais recentes** - antes devolvia as mais antigas e a verificação sempre falharia em conversa longa.

- [ ] **Passo 1: escrever o teste**

```python
"""Quem enviou a mensagem que a clínica acabou de mandar.

O z-api devolve toda mensagem enviada pelo número da clínica com fromMe=true e
status=SENT, tenha ela saído do bot ou do celular da atendente. A única
diferença confiável é o identificador: o bot registra o que o provider devolveu.
"""
import unittest
from src.services.autoria_mensagem import foi_enviada_pelo_bot


class TestAutoria(unittest.TestCase):
    def test_id_registrado_pelo_bot_e_eco(self):
        eventos = [{"providerMessageId": "ABC123"}, {"providerMessageId": "DEF456"}]
        self.assertTrue(foi_enviada_pelo_bot(eventos, "ABC123"))

    def test_id_desconhecido_veio_do_celular(self):
        eventos = [{"providerMessageId": "ABC123"}]
        self.assertFalse(foi_enviada_pelo_bot(eventos, "XYZ789"))

    def test_conversa_sem_historico(self):
        """Primeira mensagem da conversa, digitada pela atendente."""
        self.assertFalse(foi_enviada_pelo_bot([], "XYZ789"))

    def test_id_vazio_nao_e_do_bot(self):
        """Sem id não dá para afirmar que foi o bot; tratar como humano é o
        lado seguro: no máximo pausa um bot que já ia ficar quieto."""
        self.assertFalse(foi_enviada_pelo_bot([{"providerMessageId": "ABC"}], ""))

    def test_ignora_eventos_sem_provider_id(self):
        eventos = [{"providerMessageId": None}, {}, {"providerMessageId": "ABC123"}]
        self.assertTrue(foi_enviada_pelo_bot(eventos, "ABC123"))
```

- [ ] **Passo 2: rodar e ver falhar**

`python -m pytest tests/unit/test_autoria_mensagem.py -q` → ModuleNotFoundError

- [ ] **Passo 3: implementar**

```python
"""Quem enviou a mensagem que saiu do número da clínica.

O z-api entrega toda mensagem com fromMe=true e status=SENT, venha ela do bot
ou do celular da atendente. Distinguir pelo status não funciona - foi o que
deixou o bot responder por cima de um atendimento humano em 01/09/2026.

O identificador é factual: ao enviar, o bot guarda no MessageEvents o id que o
provider devolveu. Id conhecido é eco do próprio bot; id desconhecido foi
digitado no celular.
"""


def foi_enviada_pelo_bot(eventos, provider_message_id):
    if not provider_message_id:
        return False
    return any(
        (e or {}).get("providerMessageId") == provider_message_id
        for e in (eventos or [])
    )
```

- [ ] **Passo 4: rodar e ver passar**

- [ ] **Passo 5: commit**

```bash
git add scheduler/src/services/autoria_mensagem.py scheduler/tests/unit/test_autoria_mensagem.py
git commit -m "feat(webhook): distinguir eco do bot de mensagem digitada no celular"
```

---

## Task 2: Ligar a detecção no webhook

**Arquivos:**
- Modificar: `scheduler/src/functions/webhook/handler.py:63-111`

Esta é a mudança central, e é pequena: trocar o guard que sempre retorna pela verificação de autoria. `_activate_attendant_mode` continua como está - ele já grava `attendant_active_until` com 24h e renova a cada mensagem nova do atendente.

- [ ] **Passo 1: trocar o guard de status pela verificação de autoria**

```python
        if body.get("fromMe", False):
            logger.info(...)  # mantém o log existente

            # Distinguir eco do bot de mensagem digitada no celular. O status
            # não serve: os dois chegam como SENT. O id que o provider devolveu
            # no envio é o que separa um do outro.
            phone = body.get("phone", "")
            provider_id = body.get("messageId", "")
            db = PostgresService()
            clinic_id = _resolve_clinic_id(db, instance_id) if instance_id else None

            if clinic_id and phone:
                from src.services.autoria_mensagem import foi_enviada_pelo_bot
                eventos = MessageTracker().get_conversation_messages(clinic_id, phone, limit=20)
                if foi_enviada_pelo_bot(eventos, provider_id):
                    logger.info(f"[Webhook] Eco do próprio bot ({provider_id}), ignorando")
                    return http_response(200, {"status": "OK"})

                logger.info(f"[Webhook] Atendente humano respondeu {phone} pelo celular")
                _activate_attendant_mode(clinic_id, phone)   # TTL de 24h, renovável
                # ... segue o rastreamento da mensagem, que já existe
```

- [ ] **Passo 2: remover os comandos de encerramento por WhatsApp**

O bloco `DEACTIVATION_COMMANDS` (`#encerrar`, `#fim`, etc.) sai: a reativação antecipada passa a ser só pelo painel.

**Nota para quem executar:** isso é uma perda de conveniência para a clínica, que hoje pode encerrar digitando no próprio WhatsApp. Foi decisão explícita do André em 02/09. Se for revertido depois, o caminho é reintroduzir só o `_deactivate_attendant_mode`.

Com o TTL de 24h, quem não usar o painel volta a ter o bot no dia seguinte - o que reduz o custo dessa remoção.

- [ ] **Passo 3: teste de integração com o payload real**

Reproduzir o payload de 01/09 (`messageId: 3EB0E3041A2A1041F6857D`, `fromMe: true`, `status: SENT`) e confirmar que:
- com o id presente no MessageEvents → ignora, bot segue ativo
- com o id ausente → pausa a conversa por 24h

- [ ] **Passo 4: rodar a suíte inteira** (`python -m pytest tests/unit/ -q`)

- [ ] **Passo 5: commit**

---

## Task 3: Confirmar o caminho de volta pelo painel

**Arquivos:**
- Verificar: `scheduler/src/functions/attendant/handler.py` (`_handle_deactivate`)
- Verificar: `frontend/src/pages/bot/components/ConversationThread.tsx`

Nada deve precisar de mudança aqui - `_handle_deactivate` já remove `attendant_active_until`, e o painel já mostra "Atendimento humano em andamento" com botão de retomar. A tarefa é **verificar**, não reescrever.

- [ ] **Passo 1: conferir que `_handle_deactivate` limpa `attendant_active_until`**

Se limpar, o botão funciona e não há o que fazer. Se não limpar, o clique mentiria para quem aperta - foi o bug que corrigimos em 29/08 com o `bot_enabled`.

- [ ] **Passo 2: conferir que `/attendant/status` devolve `pause_reason: "attendant"`**

O cálculo de `atendente_ativo` olha `session["state"]`, e `_activate_attendant_mode` grava `HUMAN_ATTENDANT_ACTIVE`. Deve funcionar sem alteração.

- [ ] **Passo 3: se algo faltar, corrigir e commitar; se estiver tudo certo, seguir**

---

## Task 4: Deploy e verificação em produção

- [ ] `cd scheduler && npx serverless deploy --stage prod --aws-profile dev-andre`
- [ ] Confirmar nos logs do `WhatsAppWebhook` que aparece "Eco do próprio bot" nas respostas do bot (e **não** "Atendente humano respondeu")
- [ ] Teste real: responder uma conversa pelo celular da clínica e confirmar nos logs que o bot pausou
- [ ] Confirmar no painel que a conversa aparece como pausada e que o botão devolve o bot

**Atenção no deploy:** o risco desta mudança é o falso positivo. Se `foi_enviada_pelo_bot` errar para o lado errado, toda resposta do bot pausaria o próprio bot - ele responderia uma vez por conversa e emudeceria por 24h. Verificar isso nos logs antes de considerar concluído.

---

## Fora de escopo (mas relacionado)

Dois problemas do mesmo incidente que **não** são resolvidos aqui:

1. **Elegibilidade da landing page sem prazo** - um lead de 24/08 liberou o bot em 01/09. `webhook/handler.py:217-227` não tem limite de idade.
2. **Execuções concorrentes** - a Lívia mandou 3 mensagens em 11 segundos e disparou 3 execuções simultâneas do agente; a última sobrescreveu o estado de handoff da primeira. Corrigir exige serializar por conversa.

O item 2 tem interação com este plano: se três execuções concorrentes rodarem, uma pode gravar a sessão por cima da pausa recém-criada. A pausa reduz a janela (o bot para na primeira detecção), mas não elimina a corrida.
