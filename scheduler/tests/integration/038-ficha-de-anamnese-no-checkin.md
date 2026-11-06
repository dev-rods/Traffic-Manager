# 038 - Ficha de anamnese no check-in, compilada no modelo do termo

PRD: `docs/work/prd/038-ficha-de-anamnese-no-checkin.md`. Spec: `docs/work/spec/038-ficha-de-anamnese-no-checkin.md`.
Base: tudo do 036 (`036-termo-de-consentimento.md`) continua valendo; aqui só o que mudou.

## O que está no ar em dev (06/11/2026)

- Scheduler: `anamnese.py`, `patient_consents.answers` + `FILLING`/`REVOKED`, rota `POST appointments/{id}/anamnesis`, `POST consents/{id}/renew`, respostas e alertas na rota do painel, catálogo no `bootstrap`. Migrations aplicadas em dev (constraint de status, índice `uq_patient_consents_em_andamento`, colunas).
- SSM dev: `/dev/TCLE_VERSION = 2026-12`, `/dev/CLICKSIGN_TCLE_TEMPLATE_KEY` = modelo compilado do sandbox (`1d2b35f6-e9a1-4657-8f76-248ac228ad95`).
- `checkin-dev`: 4 telas da anamnese + "Preparando o documento".
- Painel: pela Vercel, no merge.

## Modelo compilado

`docs/work/assets/038-modelo-compilado/gera_modelo.js` → `TCLE_anamnese_modelo_clicksign_2026-12.docx`. O script de montagem (`monta_gerador_038.py`, sessão de 05/11) copia o TCLE do gerador do 036 byte a byte e confere por `assert`. Ficha V03 = V02 sem a seção 8, 10.8 sem marca, sem linhas de assinatura; seções 9 e 10 renumeradas para 8 e 9. 68 variáveis distintas (17 do termo + 50 da ficha + a âncora). PDF de 8 páginas: TCLE 1 a 5, ficha 6 a 8, assinatura no fim.

Criar o modelo numa conta: o mesmo `modelo_prod.py` do 036, apontando para o `.docx` acima; em prod, gravar a chave em `/prod/CLICKSIGN_TCLE_TEMPLATE_KEY` e `/prod/TCLE_VERSION = 2026-12` e redeployar.

## Achados do E2E em dev (05 e 06/11/2026)

| Ponto | Resultado |
|---|---|
| `bootstrap` | traz `anamnesis` com 4 telas (18, 8, 13 e 11 perguntas) e 6 fototipos; `null` sem `TCLE_VERSION` |
| Percurso no checkin-dev (Chromium, viewport iPad, token forjado) | dados → 4 telas → "Preparando o documento" → widget com o PDF compilado. Condicional "Se sim, quais?" só aparece com "Sim"; sem default, "Continuar" sem responder marca as perguntas |
| Gravação por tela | um `POST anamnesis` por "Continuar", só com as chaves da tela; a condicional cujo pai virou "Não" sai da gravação |
| PDF carimbado (antes de assinar) | 8 páginas, dados do paciente, respostas em negrito, "SOP" no detalhe, "-" nos vazios, fototipo assinalado |
| Rota do painel | documento `SIGNING` da versão `2026-12` com `has_anamnesis`, `answers` e `alertas` (vazio quando só "hormonal", que não é alerta) |
| Paciente com termo `2026-11` assinado | passa a ser pendente na versão `2026-12`: assina o compilado inteiro, como previsto |
| Assinatura real do compilado | **Feita pelo André em 06/11** no checkin-dev (agendamento `d979abf9`), com pagamento no fim |

**Bug pré-existente encontrado, fora do 038:** `get_active_appointments_by_phone` filtra `appointment_date >= CURRENT_DATE` em UTC. Depois das 21h (horário de Brasília) um agendamento do mesmo dia some do iPad ("Não encontramos seu agendamento"). Vale um PRD curto.

## Prod (06/11/2026)

Migrations aplicadas e conferidas (check com FILLING/REVOKED, índice `uq_patient_consents_em_andamento`, colunas `answers`/`revoked_*`). Modelo compilado criado na conta de produção pela API (`38ac3c38-8c30-457f-97fa-fee35403baf3`), `/prod/TCLE_VERSION = 2026-12`, scheduler (stack `UPDATE_COMPLETE`, Lambda com a versão e o modelo novos, bootstrap com o catálogo) e checkin-prod (bundle com a ficha) publicados. Pendente: primeira assinatura real do compilado em prod.

## Teste real do André e melhorias (06/11/2026)

O André percorreu o fluxo inteiro no checkin-dev (termo + ficha assinados de
verdade no documento compilado, pagamento). Quatro melhorias pedidas e
aplicadas no mesmo dia (commit `56fdc9f`):

| Pedido | O que mudou |
|---|---|
| Nada pré-preenchido na ficha, nem "Não" | O iPad abre as 4 telas em branco; o backend deixou de mandar `anamnesisPrefill`. Cada tela só avança com as obrigatórias |
| Cada etapa no topo da página | `window.scrollTo(0,0)` a cada mudança de etapa ou de tela |
| Espera depois de assinar | Faixa "Assinatura recebida! Aguarde..." após o `signed` do widget e polling a cada 1,5 s (o backend espera o PDF da ClickSign, 20 a 30 s) |
| Conferência do agendamento depois do termo | Ordem nova: escolher o agendamento → dados → ficha → assinar → conferir áreas, preço e horário (grava o check-in) → pagamento. `consentRequired` vem da lista de agendamentos |

Conferido por E2E headless com paciente fictício (`5511970000038`, agendamento `8f06a0e9`): termo antes da conferência, `scrollY=0` e zero rádios marcados em cada tela, widget aberto com o PDF de 8 páginas.

## Roteiro E2E (continuação)

1. No iPad (ou celular) em `checkin-dev`, número do paciente de teste → confirma o agendamento de 06/11 → dados → 4 telas → widget → token no WhatsApp + manuscrita.
2. Conferir: logs `[ClicksignWebhook]` (`document_closed`/`auto_close` → SIGNED), PDF no bucket `clinic-scheduler-infra-dev-documentos` com as respostas, aba "Termo e anamnese" com "Ver respostas" e alertas, popover com alertas.
3. Painel → "Pedir nova assinatura" → `REVOKED`; o próximo check-in pede tudo de novo e o prefill vem vazio.
4. "Recomeçar" no meio da tela 3 → novo check-in abre a tela 1 já respondida (`anamnesisPrefill`).
5. Mudar uma resposta depois de abrir o widget → envelope antigo cancelado (`EXPIRED`), novo criado.

## Casos curl

```bash
# catálogo
curl -s -H "x-api-key: $BOOKING_KEY" "$API/public/clinics/$CLINIC/bootstrap" | jq '.anamnesis.screens | map(.questions | length)'

# tela 1 (token = o de "Meus agendamentos")
curl -s -X POST -H "x-api-key: $BOOKING_KEY" -H "Content-Type: application/json" \
  "$API/public/clinics/$CLINIC/checkin/appointments/$APPT/anamnesis" \
  -d '{"phone":"5511999990000","token":"'$TOKEN'","screen":1,"answers":{"queixa_principal":"Virilha","gestante":false,"amamentando":false,"hormonal":true,"hormonal_quais":"SOP","doenca_pele":false,"autoimune":false,"imunossupressao":false,"epilepsia":false,"cancer":false,"diabetes":false,"alergia":false}}'
# → 200 {"anamnesis":{"screen":1,"answered":[...],"complete":false}} | 400 {"message":"Responda esta pergunta.","field":"gestante"}

# iniciar o envelope sem a ficha completa
# → 400 "Responda a ficha de anamnese antes de assinar."

# painel: respostas e alertas (prontuario.ler)
curl -s -H "x-api-key: $KEY" "$API/clinics/$CLINIC/consents/patients/$PATIENT" | jq '.consents[0] | {status, has_anamnesis, alertas}'

# pedir nova assinatura (agenda.escrever)
curl -s -X POST -H "x-api-key: $KEY" "$API/clinics/$CLINIC/consents/$CONSENT/renew"
# → 200 {"consent":{"status":"REVOKED",...}} | 404 se não estiver SIGNED/PAPER
```

## Testes automatizados

- scheduler: `test_anamnese.py` (catálogo x gerador do `.docx` x catálogo do painel, validação, variáveis, alertas), `test_consentimento.py::TestAnamnese`, `test_checkin.py` (rota), `test_consent_router.py` (renew).
- checkin: `CheckinPage.test.tsx` (4 casos da ficha).
- frontend: `TermoDoAgendamento.test.tsx`, `TermoDeConsentimento.test.tsx`, `TermoPendenteBadge.test.tsx`.
