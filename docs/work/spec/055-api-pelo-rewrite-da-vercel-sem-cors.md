# Spec - 055 API pelo rewrite da Vercel: fim do CORS e dos 76 OPTIONS no stack

> Gerado na fase **Spec** em 21/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/055-api-pelo-rewrite-da-vercel-sem-cors.md`
- **Decisões (PRD §7):** roteamento por host no `vercel.json`; cabeçalhos CORS
  do backend removidos; prefixo `/api`; prod em sequência, sem janela.

---

## 1. Resumo

Os três apps de browser (`frontend/`, `booking-site/`, `checkin/`) passam a
chamar a API em `/api/...` no próprio domínio. A Vercel reescreve `/api/(.*)`
para o API Gateway do stage certo, escolhido pelo host (previews e
`checkin-dev` em dev; produção e domínios das clínicas em prod). Em
desenvolvimento local o Vite faz o mesmo papel com `server.proxy`. Sem origem
cruzada não há preflight, então o `cors: true` sai das 97 rotas do scheduler e
os cabeçalhos `Access-Control-*` saem de `http_response` e do `AttendantPanel`.
Um teste prende as duas coisas: nenhum `cors: true` e `LIMITE_DE_FUNCOES`
remedido. Nada de dado, URL pública ou autenticação muda.

Endpoints (já existentes, não mudam):

| Stage | API Gateway |
|---|---|
| dev | `https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev` |
| prod | `https://ycomrg2zy7.execute-api.us-east-1.amazonaws.com/prod` |

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/tests/integration/055-api-pelo-rewrite.md` | Roteiro: hosts dos 4 projetos x stage esperado, latência direto x rewrite, corpo grande, medição do stack antes/depois, ordem dev -> apps prod -> backend prod |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `frontend/vercel.json`, `booking-site/vercel.json`, `checkin/vercel.json` | rewrites `/api/(.*)` por host (§6.1); SPA passa a excluir `/api/` |
| `frontend/vite.config.ts`, `booking-site/vite.config.ts`, `checkin/vite.config.ts` | `server.proxy['/api']` (§6.2) |
| `frontend/src/services/api.ts`, `booking-site/src/services/api.ts`, `checkin/src/services/api.ts` | `baseURL: '/api'`; sai a leitura de `VITE_API_BASE_URL` |
| `frontend/src/vite-env.d.ts`, `booking-site/src/vite-env.d.ts`, `checkin/src/vite-env.d.ts` | `VITE_API_BASE_URL` sai; `VITE_API_PROXY_TARGET?: string` entra |
| `frontend/.env`, `frontend/.env.example`, `booking-site/.env.example` | `VITE_API_BASE_URL` sai; `VITE_API_PROXY_TARGET` entra com o endpoint de dev e comentário |
| `frontend/CLAUDE.md` (l. 249), `booking-site/CLAUDE.md` (l. 66), `booking-site/docs/visao-geral.md` (l. 267), `checkin/CLAUDE.md` (l. 99) | descrever `/api` + rewrite + proxy local |
| `scheduler/tests/integration/023-*.md`, `024-*.md`, `026-*.md` | `BASE="$VITE_API_BASE_URL"` vira `BASE="$VITE_API_PROXY_TARGET"` |
| `scheduler/sls/functions/*/interface.yml` (29 arquivos, 97 ocorrências) | remover a linha `cors: true` |
| `scheduler/src/utils/http.py` | `http_response` sem `Access-Control-*` |
| `scheduler/src/functions/attendant/panel.py` | tirar `Access-Control-Allow-Origin` (o HTML é servido pelo próprio API Gateway e chama caminhos relativos) |
| `scheduler/tests/unit/test_limite_de_recursos.py` | `LIMITE_DE_FUNCOES` remedido após o deploy; comentário com a conta nova; teste `test_nenhuma_rota_com_cors` |
| Vercel (dashboard/API, operação) | apagar `VITE_API_BASE_URL` dos 4 projetos **depois** do passo 3 em prod |

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação

Uma branch `feat/055-api-pelo-rewrite`, um PR. A ordem abaixo é de
implantação, porque o perigo é tirar o `OPTIONS` antes de um app estar no
rewrite.

1. **Front, os três apps** (vercel.json, vite.config, api.ts, env, docs).
   Build, lint e vitest de cada um. `npm run dev` de cada um contra dev pelo
   proxy, uma chamada real.
2. **Backend** (interface.yml sem cors, http.py, panel.py, teste). pytest.
3. **Push do PR.** A Vercel gera preview dos três apps (preview -> dev pelo
   host). Smoke dos três previews contra dev, com o backend de dev ainda com
   `OPTIONS` (os dois caminhos funcionam).
4. **Deploy dev sem CORS.** `serverless deploy --stage dev`. Repetir o smoke
   dos três previews e do `checkin-dev`. Medir o stack de dev. Aqui termina o
   escopo autorizado ("até estar tudo pronto em dev").
5. **Prod (com o André):** merge do PR (a Vercel sobe os três apps; backend de
   prod ainda com `OPTIONS`); smoke dos 4 projetos em prod; `serverless
   deploy --stage prod`; medir o stack; apagar `VITE_API_BASE_URL` na Vercel;
   ajustar `LIMITE_DE_FUNCOES` se a medição divergir.

---

## 6. Detalhes por arquivo

### 6.1 `vercel.json` (os três, idênticos salvo a regra do `checkin-dev`)

```json
{
  "rewrites": [
    {
      "source": "/api/(.*)",
      "has": [{ "type": "host", "value": "(.*-git-.*|.*-rodrigocardosodevrods-2504s-projects)\\.vercel\\.app" }],
      "destination": "https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev/$1"
    },
    {
      "source": "/api/(.*)",
      "destination": "https://ycomrg2zy7.execute-api.us-east-1.amazonaws.com/prod/$1"
    },
    { "source": "/((?!api/).*)", "destination": "/" }
  ]
}
```

- Previews da Vercel têm host `<projeto>-git-<branch>-<team>.vercel.app` ou
  `<projeto>-<hash>-<team>.vercel.app`; o team é
  `rodrigocardosodevrods-2504s-projects`. Produção dos quatro projetos
  (`traffic-manager-eight`, `booking-site-neon`, `checkin-prod`,
  `checkin-dev-ten`) não casa com nenhum dos dois padrões.
- `checkin/vercel.json` ganha, antes da regra de prod, uma regra com
  `has host value "checkin-dev-ten\\.vercel\\.app"` apontando para dev.
- Os ids dos API Gateways não são segredo: já vão no bundle dos três apps hoje.
- A regra de SPA exclui `/api/` para não engolir a chamada antes do rewrite
  externo. Os rewrites são avaliados em ordem.
- `has` com `value` é regex na Vercel; a barra invertida dupla é a do JSON.

### 6.2 `vite.config.ts` (os três)

```ts
import { defineConfig, loadEnv } from 'vite'
// ...
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Em produção a Vercel reescreve /api para o API Gateway (vercel.json).
  // Localmente o Vite faz o mesmo papel; o alvo é o stage de dev salvo
  // VITE_API_PROXY_TARGET dizer outro.
  const alvo = new URL(env.VITE_API_PROXY_TARGET || 'https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev')
  return {
    plugins: [...],
    resolve: {...},
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: alvo.origin,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, alvo.pathname.replace(/\/$/, '')),
        },
      },
    },
  }
})
```

`/api/clinics/x` vira `https://tuvr5sfhz3.../dev/clinics/x`. Portas: 5173,
5174, 5175 como hoje.

### 6.3 `src/services/api.ts` (os três)

- `baseURL: '/api'`. Comentário de uma linha: em produção a Vercel reescreve
  para o API Gateway; em `npm run dev` é o proxy do Vite; por isso não há CORS
  nem preflight.
- Resto do arquivo (interceptors, `ApiError`, `x-api-key`) intocado.

### 6.4 `vite-env.d.ts` e `.env*`

- `VITE_API_BASE_URL` sai de `ImportMetaEnv`. Entra
  `readonly VITE_API_PROXY_TARGET?: string` (só o Vite lê, no `vite.config`).
- `frontend/.env`: fica só `VITE_APP_NAME`; `.env.example` dos apps ganha
  `VITE_API_PROXY_TARGET=https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev`
  com comentário "só para npm run dev; em produção o rewrite da Vercel decide".
- `booking-site/.env.example` mantém `VITE_BOOKING_API_KEY`.

### 6.5 `sls/functions/*/interface.yml`

- Remover toda linha `cors: true` (97). Script: para cada arquivo, apagar
  linhas que casem `^\s*cors: true\s*$`. Conferir que o número de eventos
  `http:` não muda (99).

### 6.6 `scheduler/src/utils/http.py`

```python
def http_response(status_code, body, headers=None):
    # Sem Access-Control-*: desde o PRD 055 nenhum browser fala com o API
    # Gateway de outra origem - painel, site e checkin chegam por rewrite da
    # Vercel no proprio dominio. Um cliente novo de outra origem deve passar
    # pelo mesmo rewrite, nao ganhar CORS aqui.
    default_headers = {'Content-Type': 'application/json'}
```

### 6.7 `scheduler/src/functions/attendant/panel.py`

- Remover `"Access-Control-Allow-Origin": "*"`. Antes, conferir que o
  `fetch` do `PANEL_HTML` usa caminho relativo ao próprio API Gateway (se usar
  URL absoluta de outro host, parar e registrar: é um cliente fora do mapa do
  PRD §2.2).

### 6.8 `scheduler/tests/unit/test_limite_de_recursos.py`

- Novo `TestSemCors.test_nenhuma_rota_com_cors`: varre
  `sls/functions/*/interface.yml`, falha se achar `cors:`; docstring explica
  que cada `cors: true` custa um `OPTIONS` no stack e que o browser chega por
  rewrite (PRD 055).
- `LIMITE_DE_FUNCOES`: só mudar depois de MEDIR o stack de prod sem CORS
  (passo 5). Em dev (passo 4) registrar a medição no roteiro e deixar o
  comentário preparado. Conta esperada: 494 - 76 = 418 com 86 funções; ~4
  recursos por função nova (função, permission, resource, método); limite
  novo na casa de 100, a confirmar pela medição.

### 6.9 Roteiro `055-api-pelo-rewrite.md`

Casos:

| # | O quê | Esperado |
|---|---|---|
| 1 | `GET https://<preview>/api/clinics` nos previews dos 3 apps | 200 com as clínicas de **dev** |
| 2 | `GET https://checkin-dev-ten.vercel.app/api/clinics` | clínicas de dev |
| 3 | `GET https://traffic-manager-eight.vercel.app/api/clinics`, `booking-site-neon`, `checkin-prod`, `agendar.*`, `documentos.*` | clínicas de **prod** (só após o merge) |
| 4 | `GET /api/qualquer-rota-inexistente` | JSON do API Gateway, não o `index.html` do SPA |
| 5 | Página do SPA (`/login`, `/agendar/...`) | continua servindo o `index.html` |
| 6 | Latência: 20x `GET dashboard` direto e via rewrite | registrar p50 e p95 |
| 7 | Corpo: `GET clinics/{c}/appointments` sem filtro via rewrite | inteiro, mesmo `total` do direto |
| 8 | Stack: `list-stack-resources` antes e depois do deploy sem CORS | dev e prod; esperado -76 em prod |
| 9 | Smoke no browser: login no painel, agenda, cancelar; site: datas; checkin: abrir link | sem erro de rede no console |

Sem CORS no backend, `curl -X OPTIONS` em qualquer rota deve dar 403/404 do API
Gateway (não há mais método), e isso é o esperado.

---

## 7. Testes

- Front: `npm run build && npm run lint && npm run test` nos três apps.
- Backend: `pytest tests/unit -q`; o novo teste falha se um `cors: true`
  voltar por cópia e cola de interface.
- Dev: roteiro casos 1, 2, 4, 5, 6, 7, 8 (dev), 9 nos previews.

## 8. Riscos tratados aqui

- **Cliente esquecido:** grep por `execute-api` e `VITE_API_BASE_URL` no
  monorepo antes do passo 4 (feito no PRD: só os 3 apps e roteiros/Postman,
  que batem direto e não dependem de CORS).
- **Preview em prod:** a regra de host é a primeira; teste 1 confere pelo
  conteúdo (clínicas de dev x prod são conjuntos diferentes).
- **Rollback:** recolocar `cors: true` (git revert dos interface.yml) e
  redeploy; ou reverter `vercel.json`. Nenhum dado tocado.
