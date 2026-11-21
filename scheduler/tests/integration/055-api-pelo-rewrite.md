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
- Casos 1, 2, 4 a 8 e 10: (preenchidos abaixo após o push e o deploy dev).

**Prod:** pendente (merge + deploy, com o André).
