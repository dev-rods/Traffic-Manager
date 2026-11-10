# 047 Termo e anamnese em papel, registrados pelo paciente - Integration

A recepção registra "assinado em papel" pela pasta do paciente, pela linha da
lista ou em lote, e a lista mostra e filtra quem está sem termo vigente. O
servidor só ganhou `consent_status` e o filtro na listagem de pacientes; a
rota de papel é a do PRD 036.

| Peça | Onde | O que faz |
|---|---|---|
| `GET clinics/{id}/patients?consent=missing\|ok` | `src/functions/patient/list.py` | `consent_status` por item (`SIGNED`/`PAPER`/`SIGNING`/`null`), `consent_enabled` no envelope, filtro |
| `POST clinics/{id}/consents/patients/{pid}/paper` | `src/functions/consent/router.py` | o de sempre; **201** gravou, **200** já tinha vigente (devolve o que havia) |
| `RegistrarPapelModal` | `frontend/src/components/` | o modal, compartilhado por agenda, pasta e linha |
| `BatchPapelModal` | `frontend/src/pages/pacientes/components/` | lote com uma data; Registrado / Já tinha / Erro por pessoa |
| `SeloSemTermo`, filtro "Termo e anamnese" | lista de pacientes | só com `consent_enabled` |

## Pré-requisitos

Os mesmos de `036-termo-de-consentimento.md`: `TCLE_VERSION` configurada no
stage (sem ela a lista não mostra selo nem filtro e a pasta não oferece o
botão). `API_KEY` do `.env`. Escrita em **prod** só com autorização explícita.

## 1. Listagem

```bash
curl -s -H "x-api-key: $API_KEY" "$URL/clinics/$C/patients?per_page=3" | python -m json.tool | grep -E "consent_status|consent_enabled"
curl -s -H "x-api-key: $API_KEY" "$URL/clinics/$C/patients?consent=missing&per_page=50" | python -c "import json,sys; d=json.load(sys.stdin); print(d['total'], {i['consent_status'] for i in d['items']})"
curl -s -H "x-api-key: $API_KEY" "$URL/clinics/$C/patients?consent=ok&per_page=50" | python -c "import json,sys; d=json.load(sys.stdin); print(d['total'], {i['consent_status'] for i in d['items']})"
```

Esperado: `consent_enabled: true`; `missing` só traz `None`/`SIGNING`; `ok` só
`SIGNED`/`PAPER`; `missing` + `ok` = total sem filtro. Anotar o tempo da
chamada sem filtro na maior base (Essência) e comparar com antes do deploy.

## 2. Papel pela rota (201 x 200)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  "$URL/clinics/$C/consents/patients/$PID/paper" -d '{"signedAt":"2026-11-01"}'   # 201
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  "$URL/clinics/$C/consents/patients/$PID/paper" -d '{"signedAt":"2026-11-02"}'   # 200, nada gravado
```

Depois, `?consent=ok` traz `$PID` com `PAPER`.

## 3. Painel (foi assim em dev, 10/11/2026)

| Passo | Onde | Esperado |
|---|---|---|
| 1 | Pacientes, clínica com termo | selo "Sem termo" ao lado do nome de quem falta; nada em quem está em dia; filtro "Termo e anamnese" na linha do desktop e no drawer do celular (conta no número do botão "Filtros") |
| 2 | linha de quem falta, ícone da caneta "Assinado em papel" | modal com a data (hoje, máximo hoje); Registrar → toast "Termo em papel registrado", selo e ícone somem sem recarregar |
| 3 | pasta do paciente (Documentos → Termo e anamnese), sem vigente | botão "Assinado em papel" ao lado de "Versão vigente" (ou no estado vazio); depois do registro aparece a linha EM PAPEL e o botão some |
| 4 | pasta com vigente (SIGNED/PAPER) | sem o botão |
| 5 | selecionar 3 pessoas (1 já em dia) → barra → "Assinado em papel" | aviso "A mesma data vale para todas…"; "Registrar 3"; resultado: 2 Registrado, 1 Já tinha; ao fechar, seleção limpa e aviso "2 termos em papel registrados." |
| 6 | agenda da pessoa registrada | o `DOCS` some; check-in do iPad pula termo e ficha |
| 7 | agenda, popover de quem falta → "Assinado em papel" | igual a antes (mesmo modal) |
| 8 | usuário STAFF sem `agenda.escrever` | botão aparece; ao registrar, toast de erro com a mensagem do 403 |

## Casos negativos

- Clínica sem `TCLE_VERSION`: lista sem selo, sem filtro, sem ação na linha e
  sem botão na barra; pasta sem botão; `?consent=missing` é ignorado.
- Data futura: o `max` do campo impede; a rota responde 400 se forçado.
- Versão do termo trocada: o papel antigo deixa de ser vigente e a pessoa volta
  a aparecer como "Sem termo" - igual ao digital.
