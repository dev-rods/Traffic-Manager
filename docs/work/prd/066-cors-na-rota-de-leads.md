# PRD - 066 CORS de volta em `POST /leads` e guarda das rotas chamadas de fora da Vercel

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Devolver o preflight de CORS a uma única rota, `POST /leads`, para a landing
page da Essência voltar a gravar leads, e trocar o teste de guarda do PRD 055
("nenhuma rota com cors") por um que diga quais rotas são chamadas de fora da
Vercel e exija CORS exatamente nelas, nem mais nem menos.

---

## 2. Contexto

**Perda real (Essência, 21/11 a 26/11/2026).** A landing page
`draclaradourado.com.br/depilacao` (Lovable, estático) grava o lead do
navegador da pessoa direto no API Gateway de prod, com `x-api-key` no
cabeçalho e corpo JSON. Isso é requisição de outra origem com cabeçalho
customizado: o navegador faz o preflight `OPTIONS` antes do `POST`.

O PRD 055 (prod em 21/11) tirou `cors: true` das 97 rotas, porque painel,
site e checkin passaram a chegar pelo rewrite da Vercel no próprio domínio.
A LP não roda na Vercel e ninguém a varreu. Desde então o `OPTIONS /leads`
responde 403 `MissingAuthenticationToken`, o navegador barra o `POST` antes de
sair e o `try/catch` da LP engole o erro. Nada chega à Lambda, nada aparece
em log.

Medido (só leitura, prod):

| | 10 a 20/11 | 21/11 a 26/11 |
|---|---|---|
| Leads `landing-page` da Essência | 34 (31 com gclid) | 0 |
| Leads `landing-page` da Nobre | 7 | 15 |
| Leads `whatsapp` da Essência | 65 | 43 |

A Nobre não caiu porque a LP dela (TanStack Start na Cloudflare) grava pelo
servidor: as chamadas chegam sem origem, sem preflight. A última chamada à
Lambda `CreateLead` com origem no domínio da Essência foi 20/11 às 11:21.

A LP também manda cada lead por `sendBeacon` para uma planilha do Google
(texto simples, sem preflight), então a planilha continuou recebendo; a
conversão do Google Ads dispara pelo GTM no navegador. Por isso o Google
mostra conversões e o painel não mostra leads.

**Decisão do André (26/11):** devolver o CORS nesta rota agora, porque é uma
linha e um deploy. Fazer a LP da Essência gravar pelo servidor, como a Nobre,
fica como PRD próprio (fecha também a dívida da chave de intake exposta no
bundle). Quando esse PRD entrar, o `cors: true` sai de novo e a lista de
exceções volta a ficar vazia.

---

## 3. Escopo

### Dentro do escopo

**A. Hotfix da rota**

- `scheduler/sls/functions/lead/interface.yml`: `cors: true` de volta só em
  `CreateLead` (`POST /leads`), com comentário dizendo quem chama de fora e
  que sai quando a LP gravar pelo servidor. Serverless recria o método
  `OPTIONS /leads` (mock) com `Access-Control-Allow-Origin: *`,
  `Allow-Headers` incluindo `X-Api-Key` e `Allow-Methods: OPTIONS,POST`.
- `scheduler/src/functions/lead/create.py`: as respostas desta rota voltam a
  carregar `Access-Control-Allow-Origin: *` (o `http_response` perdeu o
  cabeçalho no 055 de propósito; aqui passa por `headers=`). Sem isso o
  `POST` sai, a Lambda grava, mas o `fetch` da LP recebe erro de CORS na
  leitura da resposta e loga falha para um lead que foi salvo. Só o 201 e os
  4xx desta rota; `http_response` continua sem CORS por padrão.
- Deploy do scheduler em dev e depois em prod. O `CloudFormation` recria o
  `OPTIONS` sem `create-deployment` extra (o 055 precisou dele para REMOVER
  métodos; adicionar propaga no deploy).
- Conferência em prod, como o navegador faz: `OPTIONS /leads` com `Origin`
  e `Access-Control-Request-Headers: content-type,x-api-key` responde 200
  com os três `Access-Control-*`, e `POST` com corpo inválido responde 400
  com `Access-Control-Allow-Origin`. Sem lead de teste (D2): o primeiro lead
  orgânico da LP, com `origin=https://draclaradourado.com.br` no log da
  Lambda, fecha o critério.

**B. Guarda: rotas chamadas de fora da Vercel**

- `scheduler/tests/unit/test_limite_de_recursos.py`: `TestSemCors` vira
  `TestCorsSoOndeChamamDeFora`, com a lista explícita, por arquivo e rota:
  ```python
  # Quem fala com o API Gateway de OUTRA origem, sem passar pelo rewrite da
  # Vercel. Toda entrada aqui custa um OPTIONS no stack e precisa dizer quem e.
  CHAMADAS_DE_FORA_DA_VERCEL = {
      "sls/functions/lead/interface.yml": {
          "CreateLead": "LP da Essencia (draclaradourado.com.br, Lovable estatico) grava do browser; sai quando gravar pelo servidor",
      },
  }
  ```
- Dois testes, lendo o YAML (não regex): (1) toda função nessa lista tem
  `cors: true` em todos os seus `http`; (2) nenhuma função fora da lista tem
  `cors`. A mensagem de falha nos dois sentidos aponta para a lista: "rota
  chamada de fora sem CORS: o browser barra no preflight e o erro e
  silencioso (PRD 066)" e "cors em rota que chega pela Vercel: custa um
  OPTIONS no stack; se alguem de fora chama, registre em
  CHAMADAS_DE_FORA_DA_VERCEL (PRD 055)".
- Comentário em `LIMITE_DE_FUNCOES` ganha a linha: 26/11, +1 OPTIONS
  (`/leads`), prod 419 de 500 depois de medir.

### Fora do escopo

- Recuperar os leads de 21/11 a 26/11 da planilha do Google para
  `scheduler.leads` (proposta 2 do diagnóstico): decisão do André sobre
  disparar ou não a abertura de conversa com dias de atraso; PRD ou tarefa
  própria.
- LP da Essência gravar pelo servidor (como a Nobre) e tirar a chave de
  intake do bundle: PRD próprio.
- Restringir `Access-Control-Allow-Origin` ao domínio da LP: a rota já é
  protegida pela chave de intake e `*` era o comportamento até 20/11; apertar
  a origem entra no PRD da LP, quando a chave sair do navegador.
- Qualquer outra rota: `POST /public/...` do site chega pelo rewrite; o
  webhook do z-api, da ClickSign e do Asaas são servidor a servidor.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/sls/functions/lead/interface.yml` | modificar | `cors: true` em `CreateLead`, com comentário |
| `scheduler/src/functions/lead/create.py` | modificar | `Access-Control-Allow-Origin: *` nas respostas da rota |
| `scheduler/tests/unit/test_limite_de_recursos.py` | modificar | `CHAMADAS_DE_FORA_DA_VERCEL`; testes nos dois sentidos lendo YAML; nota no limite |
| `scheduler/tests/unit/test_lead_create.py` (ou o teste existente da rota) | modificar | respostas 201 e 4xx trazem o cabeçalho |
| `docs/work/prd/055-api-pelo-rewrite-da-vercel-sem-cors.md` | modificar | nota: exceção `/leads` desde 26/11 (PRD 066) |

---

## 5. Dependências e riscos

- **Stack:** +1 recurso (método OPTIONS). Prod e dev medidos em 418 de 500 em
  21/11; medir de novo após o deploy e anotar no teste.
- **Dev:** o `/dev/leads` do API Gateway de dev também ganha o OPTIONS; nada
  aponta para ele hoje (a LP aponta para prod desde o PRD 033). Testar em dev
  só com `curl` (OPTIONS + POST com corpo inválido, 400), sem criar lead.
- **Regressão do 055:** nenhuma. O rewrite da Vercel continua para painel,
  site e checkin; só a LP passa a ter os dois caminhos possíveis.
- **Ordem com outros deploys:** scheduler dev e prod nunca em paralelo;
  conferir que ninguém está deployando dev de outra branch.

---

## 6. Critérios de aceite

- [ ] `OPTIONS /leads` em prod responde 200 com `Access-Control-Allow-Origin`,
      `-Headers` (com `x-api-key`) e `-Methods`.
- [ ] `POST /leads` em prod responde com `Access-Control-Allow-Origin: *`
      no 201 e no 400/401.
- [ ] Primeiro lead orgânico da LP depois do deploy aparece em
      `scheduler.leads` com `source = landing-page`, e a Lambda loga
      `origin=https://draclaradourado.com.br` (conferido a posteriori).
- [ ] Nenhuma outra rota declara `cors`; o teste falha se alguém adicionar
      `cors` fora da lista ou tirar da rota listada.
- [ ] `pytest` verde; `LIMITE_DE_FUNCOES` com a nota da medição.

---

## 7. Referências

- Diagnóstico de 26/11/2026 (esta sessão): logs da `CreateLead`, bundle da
  LP, `curl` do preflight.
- PRD 055 (`prd/055-api-pelo-rewrite-da-vercel-sem-cors.md`), PRD 033
  (LP aponta para prod), memória `project_landing_page_leads`.
- `scheduler/src/utils/http.py` (`http_response` sem CORS desde o 055;
  `require_intake_api_key`).

---

## Decisões (fechadas em 26/11/2026)

- Hotfix na rota agora; LP pelo servidor em PRD próprio (André, 26/11).
- D1: `Access-Control-Allow-Origin: *`, como antes de 20/11. CORS governa o
  navegador, não o abuso por script; a proteção real é tirar a chave do
  bundle, no PRD da LP pelo servidor (André, 26/11).
- D2: conferência em prod só pelo `curl` do preflight e do POST com corpo
  inválido; nenhum lead de teste. O primeiro lead orgânico da LP fecha o
  critério de aceite (André, 26/11).

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/066-cors-na-rota-de-leads.md`
- [x] Implementado em: 2026-11-26 (dev layer 229, prod layer 182; preflight 200 nos dois; stack prod 430/500; propagação da borda ~1 min após o deploy)
- [x] Registrado em `TASKS_LOG.md`
