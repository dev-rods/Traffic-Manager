# 048 - Termo e anamnese antes da sessão, pelo link no WhatsApp

Roteiro de conferência em **produção** (decisão do PRD: direto em prod, só
Essência por ora). Tudo com paciente de teste no telefone do André; nenhum
nome real aqui nem nos prints.

Pré-requisitos:

- `scheduler/` deployado em prod e `setup_database.py` rodado (coluna
  `appointments.consent_link_sent_at`).
- `checkin-prod` publicado com a rota `/:clinicId/documentos`;
  `https://documentos.draclaradourado.com.br/clinicaessenciaestetica-9668a4/documentos`
  abre a tela de telefone, e `/clinicaessenciaestetica-9668a4` segue o iPad.
- Painel na Vercel com o merge.

## 1. Envio pelo painel

1. Sessão futura confirmada da paciente de teste, sem termo vigente.
2. Agenda → popover → "Termo e anamnese" mostra "Pendente" e o botão
   **Enviar link dos documentos**. Clicar.
3. Esperado: toast "Link dos documentos enviado pelo WhatsApp"; abaixo do
   botão, "Link enviado em dd/mm às hh:mm"; o botão vira "Reenviar".
4. WhatsApp do André recebe a mensagem do número da clínica, com o link
   `https://documentos.draclaradourado.com.br/clinicaessenciaestetica-9668a4/documentos`.
5. DynamoDB `clinic-scheduler-infra-prod-message-events`: o evento SENT tem
   `metadata.origem = DOCUMENTOS`. A sessão da conversa **não** ficou com o
   bot pausado (PRD 034).

## 2. Fluxo no celular

Safari iOS e Chrome Android.

1. Abrir o link: tela "Qual é o seu celular?" com o teclado do aparelho.
2. Telefone → "Receber código" → código chega no WhatsApp → digitar (o iOS
   sugere o código).
3. "Olá, {nome}. Sua sessão é ..." → **Começar**.
4. Termo de consentimento: dados preenchidos, uso de imagem → Continuar.
5. Ficha: 4 telas. Parar na tela 2, **fechar a aba**, reabrir o link, entrar
   de novo → a tela 1 vem com as respostas marcadas (retomada).
6. Terminar a ficha → "Preparando o documento" → widget da ClickSign em tela
   cheia: código no WhatsApp, assinatura manuscrita. **1 crédito.**
7. "Tudo certo, {nome}! Documento assinado. No dia, é só confirmar e pagar na
   recepção." e "Pode fechar esta página." Sem botão de pagamento em nenhum
   momento.

## 3. Painel depois

1. Agenda: a sessão passa de "Pendente" para "Assinado"; o selo DOCS some.
2. Pasta da paciente → Termo e anamnese: PDF e trilha disponíveis; alertas da
   ficha, se houver.
3. Reabrir o link e entrar de novo → "Tudo certo, {nome}. Não há nada para
   preencher agora."

## 4. iPad no dia

Check-in da mesma sessão: telefone → código → sessão → **vai direto à
conferência do agendamento** → pagamento. Sem termo nem ficha.

## 5. Negativos

| Caso | Esperado |
|---|---|
| Link aberto com número sem sessão pendente | "Tudo certo... nada para preencher" |
| `curl` em `checkin/appointments/{id}/confirm` com o token de documentos | 401 "Sua sessão expirou" |
| `curl` em `checkin/appointments/{id}/payments` com o token de documentos | 401 |
| Sessão passada no popover | botão ausente |
| Sessão já assinada no popover | botão ausente |
| Clínica sem domínio (dev) | 400 "Esta clínica não tem domínio próprio" no toast |
| WhatsApp da clínica fora | caixa âmbar com o link para copiar |

## 6. Curls

```bash
source .env   # API da clínica para o painel; chave pública do booking para o check-in
C=clinicaessenciaestetica-9668a4

# Painel: envia o link
curl -s -X POST -H "x-api-key: $API_KEY" "$API/clinics/$C/consents/appointments/$APPT/link"

# Celular: OTP com escopo documentos
curl -s -X POST -H "x-api-key: $BOOKING_KEY" -H 'Content-Type: application/json' \
  -d '{"phone":"55DDDNNNNNNNN"}' "$API/public/clinics/$C/verify/send"
curl -s -X POST -H "x-api-key: $BOOKING_KEY" -H 'Content-Type: application/json' \
  -d '{"phone":"55DDDNNNNNNNN","code":"123456","scope":"documentos"}' "$API/public/clinics/$C/verify/confirm"

# Com o token de documentos: lista passa (com anamnesisAnswers), confirm e payments 401
curl -s -H "x-api-key: $BOOKING_KEY" "$API/public/clinics/$C/checkin/appointments?phone=55DDDNNNNNNNN&token=$TOKEN"
curl -s -X POST -H "x-api-key: $BOOKING_KEY" -H 'Content-Type: application/json' \
  -d "{\"phone\":\"55DDDNNNNNNNN\",\"token\":\"$TOKEN\"}" "$API/public/clinics/$C/checkin/appointments/$APPT/confirm"
```
