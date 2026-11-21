# 055 - API pelo rewrite da Vercel, sem CORS

Painel, site e checkin chamam `/api/...` no próprio domínio. A Vercel reescreve
para o API Gateway do stage escolhido pelo host (`vercel.json` de cada app):
previews (`*-git-*`, `*-<team>.vercel.app`), `checkin-dev-ten` e
`booking-site-dev` vão para **dev**; o resto (produção e domínios das clínicas)
vai para **prod**. Em `npm run dev` o proxy do Vite faz o mesmo. O backend não
tem mais `cors: true` nem `Access-Control-*`.

Ordem segura: fronts primeiro (os dois caminhos funcionam enquanto o backend
ainda tem `OPTIONS`), backend por último.

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
KEY_DEV=$(get /dev/SCHEDULER_API_KEY); KEY_PROD=$(get /prod/SCHEDULER_API_KEY)
# previews: API da Vercel com /prod/VERCEL_API_TOKEN (GET /v6/deployments?projectId=...)
```

Dev e prod têm conjuntos diferentes de clínicas: dev 3, prod 4 (Nobre,
Essência, Premium, Rods). É por isso que `GET /api/clinics` prova o stage.

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | `GET https://<preview de cada app>/api/clinics` com a chave de dev | 200, 3 clínicas (dev) |
| 2 | `GET https://checkin-dev-ten.vercel.app/api/clinics`, `https://booking-site-dev.vercel.app/api/clinics` | 3 clínicas (dev) |
| 3 | `GET https://traffic-manager-eight.vercel.app/api/clinics`, `booking-site-neon`, `checkin-prod`, `agendar.*`, `documentos.*` com a chave de prod | 4 clínicas (prod); só depois do merge |
| 4 | `GET <host>/api/rota-inexistente` | JSON do API Gateway (403/404), não o `index.html` |
| 5 | `GET <host>/login`, `/<clinicId>` | `index.html` do SPA |
| 6 | 20x `GET clinics/{c}/dashboard` direto e via rewrite | p50/p95 registrados |
| 7 | `GET clinics/{c}/appointments` sem filtro via rewrite | mesmo `total` do direto |
| 8 | `list-stack-resources` antes/depois do deploy sem CORS | dev e prod medidos; prod esperado 494 -> 418 |
| 9 | Browser: login no painel, agenda, cancelar; site: datas; checkin: abrir link | sem erro de rede no console |
| 10 | `curl -X OPTIONS <api-gateway>/clinics` depois do deploy | sem método (403/404 do gateway): é o esperado |
| 11 | `npm run dev` de um app: `GET localhost:<porta>/api/clinics` | 3 clínicas (dev) pelo proxy do Vite |

## Resultado

**Dev, 21/11/2026:**

- 11 → painel em `localhost:5199`: `/api/clinics` 200 com 3 clínicas; `/login`
  serve o SPA; `/api/rota-inexistente` devolve o 403 JSON do gateway.
- Build, lint e vitest dos três apps verdes (692 / 110 / 37); pytest 2436.
- 1 → os previews da Vercel têm proteção SSO (302 para `vercel.com/sso-api`)
  e não dão para smoke por curl. O rewrite foi provado pelo host público de
  dev do checkin (caso 2), que usa o mesmo `vercel.json`.
- 2 → `checkin-dev-ten.vercel.app/api/clinics`: 200 com as 3 clínicas de dev
  (deploy manual do `checkin/` no projeto `checkin-dev`, receita da 048).
  `booking-site-dev.vercel.app` existe fora dos 4 projetos listados e aponta
  para dev; ganhou regra própria no `vercel.json` do site.
- 4 → `/api/rota-inexistente` devolve o 403 JSON do gateway. 5 → SPA intacto.
- 6 → 30 amostras, p50/p95 em ms: dashboard direto 233/464, via rewrite
  317/490; `/clinics` direto 197/422, via rewrite 217/434. Acréscimo de 20 a
  85 ms no p50.
- 7 → `appointments` sem filtro: mesmo `total` (50) direto e via rewrite,
  77 KB inteiros.
- 8 → stack de dev **494 -> 418**, `OPTIONS` no stack 76 -> 0. Deploy dev
  layer 204.
- 10 → logo após o deploy, `OPTIONS /clinics` ainda respondia 200 com os
  cabeçalhos do MOCK: o CloudFormation tira o snapshot do
  `ApiGateway::Deployment` ANTES de apagar os métodos removidos, então o stage
  seguia servindo os OPTIONS antigos. `aws apigateway create-deployment
  --rest-api-id tuvr5sfhz3 --stage-name dev` renovou o snapshot e todas as
  rotas passaram a 403 `MissingAuthenticationToken`. **Em prod, repetir esse
  comando depois do `serverless deploy`** (ou aceitar que os OPTIONS mortos
  respondam até o próximo deploy; não fazem mal).
- Preview do site falhou na primeira tentativa por escape inválido
  (`\.` em vez de `\\.`) na regra acrescentada à mão; corrigido, READY.
- Guarda: `test_nenhuma_rota_com_cors`. `LIMITE_DE_FUNCOES` continua 86 até
  medir prod sem CORS.

**Prod, 21/11/2026** (autorizado pelo André):

- Merge do PR #236: painel e site subiram pela Vercel (commit `c300062`
  READY nos dois); `checkin-prod` por deploy manual (token do SSM), READY.
- 3 → com o backend de prod ainda com `OPTIONS`, `GET /api/clinics` devolveu
  as 4 clínicas em `traffic-manager-eight`, `booking-site-neon`,
  `agendar.nobrelaser.com.br`, `agendar.draclaradourado.com.br`,
  `checkin-prod` e `documentos.draclaradourado.com.br`.
  `documentos.nobrelaser.com.br` não resolve (CNAME nunca criado pela Nobre,
  pendência da 048; nada a ver com este PRD). Bundle do painel sem
  `execute-api`.
- `serverless deploy --stage prod`: layer 162. `create-deployment` do stage
  (`brxhkt`). Stack **494 -> 418**, `OPTIONS` no stack 0.
- Depois do deploy: os mesmos hosts seguem devolvendo as 4 clínicas; relatório
  da Essência via rewrite igual ao direto (115 agendamentos, 13 faltas); GET
  direto sem nenhum `Access-Control-*`; `OPTIONS` direto passou a 403 após a
  propagação (as primeiras respostas alternaram 200/403 pelos edges do
  CloudFront).
- `VITE_API_BASE_URL` apagada nos 4 projetos da Vercel (6 variáveis); sobrou
  só `VITE_BOOKING_API_KEY` onde cabe.
- `LIMITE_DE_FUNCOES` 86 -> 104: 82 recursos livres a ~4 por função nova,
  com folga de ~10.
- Smoke no browser (caso 9): pelo André.
