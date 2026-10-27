# Lembrete de sessão (PRD/Spec `027`)

Casos de teste do lembrete por dia da agenda: botão com prévia, lote na fila,
entrega pelo processador, sobreposição no bot e confirmação de presença.

A pergunta que todos respondem: **cada pessoa com sessão confirmada no dia
recebe UM lembrete, sem link e sem citar cancelar, e quem pede para sair recebe
o link em vez de o bot executar?**

```bash
cd scheduler && source .env
BASE="https://SEU_API_GATEWAY.execute-api.us-east-1.amazonaws.com/dev"
H=(-H "x-api-key: $SCHEDULER_API_KEY" -H "Content-Type: application/json")
CLINIC="clinicadorods-da7b62"
DIA="$(date -d tomorrow +%F)"
```

Pré-requisito: 3 agendamentos `CONFIRMED` em `$DIA` com telefones de teste
(um deles com conversa em atendimento humano, para testar o destravar) e a
clínica com `custom_domain` preenchido.

---

## 1. Prévia

```bash
curl -s -X POST "${H[@]}" "$BASE/clinics/$CLINIC/agenda/$DIA/lembretes?simular=true"
```

**Esperado:** `200`, `enfileirados: 3`, `ja_lembrados: 0`, `sem_telefone: 0`,
`adiados_para: null` (em horário comercial), `tem_link_de_autoatendimento: true`.
Nada gravado: `lembrete_status` continua `NULL` nos 3.

---

## 2. Envio

```bash
curl -s -X POST "${H[@]}" "$BASE/clinics/$CLINIC/agenda/$DIA/lembretes"
```

**Esperado:** `200`, `enfileirados: 3`. Em até 1 minuto (o endpoint acorda o
`ReminderProcessor`) as 3 mensagens chegam, sem link e sem "cancelar" ou
"remarcar" no texto. No banco: `lembrete_status = 'ENVIADO'`,
`lembrete_enviado_em` preenchido. Na agenda do painel: badge **PENDENTE** nos 3.

❌ **Falha conhecida se o `REMINDER_PROCESSOR_FUNCTION_NAME` faltar:** a
mensagem só sai no cron horário (minuto 0).

---

## 3. Segundo clique não repete

Repetir o passo 1.

**Esperado:** `enfileirados: 0`, `ja_lembrados: 3`. O botão do painel mostra
"3 já lembrados" e fica desabilitado.

---

## 4. Fora do horário enfileira

Rodar o passo 2 depois das 22:59 (ou com `janela_de_silencio` da clínica
cobrindo agora).

**Esperado:** `adiados_para` com a hora de saída (04:59 local, em UTC),
`lembrete_status = 'ADIADO'` ou `'ENFILEIRADO'`; as mensagens saem no primeiro
cron depois do fim do silêncio.

---

## 5. Cancelado entre enfileirar e enviar

Enfileirar fora do horário (passo 4), cancelar um dos agendamentos
(`PUT /appointments/{id}` com `{"status": "CANCELLED"}`), esperar o cron.

**Esperado:** o cancelado não recebe; `lembrete_status` dele volta a `NULL`; o
item da fila fica `FAILED` com `agendamento_nao_confirmado`.

---

## 6. Pedido de remarcar vira link

No WhatsApp de um dos 3 números, responder "preciso remarcar".

**Esperado:** o bot envia `https://{custom_domain}/` e diz que resolve por lá.
**Nenhum** agendamento muda (`status` segue `CONFIRMED`, data e hora iguais).

Com a clínica **sem** `custom_domain`: o bot remarca pela conversa como antes.

---

## 7. Resposta positiva vira Confirmado

Em outro número, responder "ok, confirmado".

**Esperado:** `confirmado_em` preenchido, `confirmado_por = 'PACIENTE'`; badge
**CONFIRMADO** na agenda; o popover mostra "Presença: Confirmada".

---

## 8. Confirmação pela equipe

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/APPOINTMENT_UUID" -d '{"confirmado": true}'
curl -s -X PUT "${H[@]}" "$BASE/appointments/APPOINTMENT_UUID" -d '{"confirmado": false}'
```

**Esperado:** `200` nos dois; o primeiro grava `confirmado_por = 'EQUIPE'`, o
segundo limpa. Combinar com outro campo recusa:

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/APPOINTMENT_UUID" -d '{"confirmado": true, "notes": "x"}'
```

**Esperado:** `400` "'confirmado' vai sozinho no corpo".

---

## 9. Recusas do endpoint

```bash
curl -s -X POST "${H[@]}" "$BASE/clinics/$CLINIC/agenda/2020-01-01/lembretes"   # dia passado
curl -s -X POST "${H[@]}" "$BASE/clinics/$CLINIC/agenda/01-11-2026/lembretes"   # formato
```

**Esperado:** `400` nos dois. Sem `x-api-key` ou com sessão de STAFF de outra
clínica: `401`/`403`.

---

## 10. Automático

```bash
curl -s -X PUT "${H[@]}" "$BASE/clinics/$CLINIC" -d '{"lembrete_automatico": true, "lembrete_antecedencia_horas": 24}'
```

Criar um agendamento para amanhã com primeiro horário tal que
`primeiro horário - 24h` já tenha passado. Esperar o cron do minuto 5
(`LembretesAutomaticos`) e o do minuto 0 seguinte (`ReminderProcessor`).

**Esperado:** o lote do dia inteiro enfileirado de uma vez e entregue; dias sem
agendamento não geram nada; o dia já lembrado não repete na hora seguinte.

```bash
curl -s -X PUT "${H[@]}" "$BASE/clinics/$CLINIC" -d '{"lembrete_antecedencia_horas": 0}'
```

**Esperado:** `400` (mínimo 1, máximo 72).

---

## Limpeza

Desligar `lembrete_automatico` na clínica de teste e cancelar os agendamentos
criados.
