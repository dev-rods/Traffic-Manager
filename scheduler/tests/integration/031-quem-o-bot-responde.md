# Quem o bot responde: os três cenários (PRD/Spec `031`)

A pergunta: **lead cadastrado por qualquer caminho (menos o próprio WhatsApp)
recebe o bot; mensagem avulsa fica fora da regra, aparece assim na lista, e
"Ativar bot" responde o que ficou pendente?**

```bash
cd scheduler && source .env
BASE="https://SEU_API_GATEWAY.execute-api.us-east-1.amazonaws.com/dev"
H=(-H "x-api-key: $SCHEDULER_API_KEY" -H "Content-Type: application/json")
CLINIC="clinicadorods-da7b62"   # política LEADS_ONLY
```

Pré-requisito: clínica em `LEADS_ONLY`, bot despausado, fora da janela de
silêncio. Dois números de teste: `LEAD` (vai ser cadastrado) e `AVULSO`.

---

## 1. Lead cadastrado fora da landing page escreve primeiro (cenário 1)

```bash
curl -s -X POST "${H[@]}" -d "{\"phone\":\"$LEAD\",\"name\":\"Teste 031\",\"source\":\"painel\"}" "$BASE/clinics/$CLINIC/leads"
```

Mande "oi" do `LEAD` para o WhatsApp da clínica.

**Esperado:** o bot responde. Em `GET /clinics/$CLINIC/conversations` a linha
do `LEAD` vem com `pause_reason: null` e `bot_paused: false`.

## 2. "Iniciar pelo Bot" acende para origem `painel` (cenário 2)

`GET /clinics/$CLINIC/leads`: o lead de origem `painel` que ainda não escreveu
vem com `pode_iniciar_pelo_bot: true`. Um lead de origem `whatsapp` vem com
`false` e motivo "Quem chegou pelo WhatsApp não pode ser iniciado pelo bot."

## 3. Mensagem avulsa fica fora da regra (cenário 3)

Mande "quanto custa a axila?" do `AVULSO` (número sem lead).

**Esperado:** nenhuma resposta. Em `GET /clinics/$CLINIC/conversations` a
linha do `AVULSO` vem com `pause_reason: "not_eligible"`, `bot_paused: true`.
No painel: selo "Fora da regra", filtro "Fora da regra" a isola, botão "Ativar
bot" na linha.

## 4. "Ativar bot" responde a pergunta pendente

```bash
curl -s -X POST "${H[@]}" -d "{\"clinic_id\":\"$CLINIC\",\"phone\":\"$AVULSO\"}" "$BASE/attendant/deactivate"
```

**Esperado:** `200`, `answering_open_question: true`,
`motivo_sem_resposta: null`; em alguns segundos o bot responde a pergunta no
WhatsApp, uma vez só. Repetir o POST: `answering_open_question: false` (a
última fala agora é do bot).

## 5. Fora do horário não promete

Com a clínica na janela de silêncio (ou `bot_paused: true`), o mesmo POST
devolve `answering_open_question: false` e `motivo_sem_resposta:
"fora_do_horario"` (ou `"bot_pausado"`). Nada é enviado; a conversa fica
ativada.

## 6. Selos dos outros motivos

Responda a `LEAD` pelo celular da clínica: a linha vira "Com atendente"
(`pause_reason: "attendant"`). Pause o bot da clínica: as linhas sem pessoa
viram "Bot pausado".
