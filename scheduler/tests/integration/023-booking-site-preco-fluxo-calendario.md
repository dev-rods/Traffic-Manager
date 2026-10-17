# Testes de integração — 023 Booking-site: preço certo, fluxo enxuto e calendário do mês

PRD: `docs/work/prd/023-booking-site-preco-fluxo-calendario.md` ·
Spec: `docs/work/spec/023-booking-site-preco-fluxo-calendario.md`

Rotas públicas da Lambda `PublicBooking`. Autenticação pela chave do
booking-site (`x-api-key`, a mesma de `VITE_BOOKING_API_KEY`), nunca copiada
para este arquivo.

## Preparação

```bash
source booking-site/.env   # traz VITE_API_BASE_URL e VITE_BOOKING_API_KEY (valores nunca neste arquivo)
BASE="$VITE_API_BASE_URL"; KEY="$VITE_BOOKING_API_KEY"   # use o .env de dev
C="<clinic-id de dev>"
SVC="<uuid de um serviço com áreas>"; A1="<uuid área>"; A2="<uuid área>"; A3="<uuid área>"
```

Os ids saem de `GET /public/clinics/$C/bootstrap` (`services`, `serviceAreas`).
Para exercitar combo, escolha duas áreas cujo combo exista no cadastro (nome
com `+` cujos dois lados são outras áreas vendidas; ver `combos.py`).

Mocks para `serverless invoke local`: `tests/mocks/public_booking/*.json`
(ids são placeholders com formato de UUID; troque pelos da clínica de dev).

```bash
serverless invoke local -s dev -f PublicBooking -p tests/mocks/public_booking/quote_sem_telefone.json --aws-profile traffic-manager
```

---

## 1. Cotação — `POST /public/clinics/{clinicId}/quote`

| # | Caso | Requisição | Esperado |
|---|------|------------|----------|
| 1.1 | Uma área, sem telefone | `{"serviceIds":[SVC],"serviceAreaPairs":[{SVC,A1}]}` | 200; `discountPct` 0 (ou faixa, se a clínica tiver faixa de 1 área); `finalPriceCents` = `originalPriceCents` |
| 1.2 | Áreas da faixa 2, sem telefone | 2+ pares (≥ `tier_2_min_areas`) | 200; `discountReason` `tier_2`; `finalPriceCents` = original × (100 − pct) / 100, truncado |
| 1.3 | Primeira sessão | 1 par + `phone` de número sem agendamento confirmado | 200; `discountPct` da primeira sessão (se for o maior desconto aplicável) e `finalPriceCents` com ele; `discountReason` null (com telefone o motivo nunca vem) |
| 1.4 | Personalizado | `phone` de paciente com `custom_discount_pct` | 200; `discountPct` = o personalizado; `discountReason` null |
| 1.5 | Combo | as duas partes de um combo | 200; `combos[0].to` = nome do combo; `areaCount` 1; preço = preço do combo |
| 1.6 | Paridade com o bot | mesmo carrinho e telefone no WhatsApp (`calculate_discount`) | mesmos `discount_pct` e `discounted_price_cents`; o `discount_reason` do bot é o que a criação grava (a cotação com telefone não o devolve) |
| 1.7 | Telefone inválido | `"phone":"123"` | 400 `Telefone inválido` |
| 1.8 | Serviço de outra clínica | `serviceIds` de outra clínica | 400 `Serviço não encontrado nesta clínica` |
| 1.9 | Área de serviço fora do carrinho / inativa / repetida | pares assim | 400 |
| 1.10 | Clínica inexistente | `clinicId` inválido | 404 |
| 1.11 | Sem chave | sem `x-api-key` | 401 |

```bash
curl -s -X POST "$BASE/public/clinics/$C/quote" \
  -H "x-api-key: $KEY" -H 'content-type: application/json' \
  -d "{\"serviceIds\":[\"$SVC\"],\"serviceAreaPairs\":[{\"serviceId\":\"$SVC\",\"areaId\":\"$A1\"},{\"serviceId\":\"$SVC\",\"areaId\":\"$A2\"}]}"
```

## 2. Disponibilidade — `GET /public/clinics/{clinicId}/availability`

| # | Caso | Requisição | Esperado |
|---|------|------------|----------|
| 2.1 | Carrinho novo | `dates=<hoje..fim do mês>&serviceIds=SVC&serviceAreaPairs=SVC:A1` | 200; `days` para cada data; `window.start` = hoje, `window.end` = último dia do mês, `window.nextOpensOn` = dia 1º seguinte |
| 2.2 | Duração igual à da criação | carrinho com soma fora do passo (ex.: 17 min com passo 5) | horários gerados com a duração arredondada (15), a mesma que a criação grava |
| 2.3 | Data fora do mês | incluir uma data do mês seguinte | essa data `CLOSED`, sem consultar agenda |
| 2.4 | Data passada | incluir ontem | `CLOSED` |
| 2.5 | Hoje | incluir hoje | nenhum horário anterior a agora (fuso da clínica) |
| 2.6 | Legado | `dates=...&totalDuration=30` (sem `serviceIds`) | 200 com a duração informada; log `totalDuration legado` no CloudWatch |
| 2.7 | Sem carrinho nem duração | só `dates` | 400 |
| 2.8 | Data mal formada | `dates=21/10/2026` | 400 |
| 2.9 | Mais de 31 datas | 32 datas | 400 |

```bash
curl -s "$BASE/public/clinics/$C/availability?dates=2026-10-20,2026-10-21&serviceIds=$SVC&serviceAreaPairs=$SVC:$A1" \
  -H "x-api-key: $KEY"
```

## 3. Criação — `POST /public/clinics/{clinicId}/appointments`

| # | Caso | Esperado |
|---|------|----------|
| 3.1 | Carrinho com combo + faixa | 201; `appointment.discount_pct`/`discount_reason`/`final_price_cents` iguais aos da cotação 1.x com o mesmo telefone; `total_duration_minutes` igual à usada em 2.1 |
| 3.2 | Sem `professionalId` | 201; `professional_id` preenchido pelo backend |
| 3.3 | Com `professionalId` (front antigo) | 201; respeita o enviado se for profissional ativo da clínica; de outra clínica, inativo ou mal formado é ignorado (backend atribui) e logado |
| 3.4 | Data do mês seguinte | 400 `Esta data não está disponível para agendamento online.` |
| 3.5 | Hoje, horário que já passou | 400, mesma mensagem |
| 3.6 | Horário já ocupado | 409; log `[PublicBooking][create] 409 ... dur=` no CloudWatch |
| 3.7 | `time` inválido (`25:00`), `date` inválida, telefone inválido, nome vazio | 400 |
| 3.8 | WhatsApp de confirmação | duas mensagens: `BOOKED` com `~R$ de~ → R$ por (x% off - motivo)` quando há desconto, depois as orientações pré-sessão da clínica |

Em dev, só números do allowlist recebem WhatsApp.

## 4. Booking-site (preview de dev)

| # | Caso | Esperado |
|---|------|----------|
| 4.1 | Catálogo | Serviço sem duração; só "a partir de R$ x" com ícone visível no celular |
| 4.2 | Áreas | Só preço por área; total "Escolha as áreas para ver o valor" até escolher |
| 4.3 | Clínica com 2+ profissionais | Nenhuma etapa de profissional |
| 4.4 | Agenda | Só dias com horário, até o fim do mês; lotado/fechado não aparecem |
| 4.5 | Fim de mês sem vaga | "Não há mais horários disponíveis em {mês}" + "A agenda de {próximo} abre em 01/MM" + botão de WhatsApp |
| 4.6 | Resumo | Total; ao digitar o celular de paciente nova aparece "Desconto (x%)", sem motivo, e "Valor final" antes de confirmar |
| 4.7 | Fuso do navegador × clínica | navegador num dia diferente do da clínica (ex.: virada do mês) | o site refaz a busca com `window.start`..`window.end` da resposta e mostra os dias da clínica |
| 4.7 | 409 | Volta para a agenda com aviso, grade atualizada |
| 4.8 | Sucesso | Data, hora, valor final e telefone formatado `(11) 9xxxx-xxxx` |
| 4.9 | Layout | 375×812 e 1280×800 sem corte, alvos de toque ≥ 44px |
