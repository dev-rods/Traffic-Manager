# PRD - 055 API pelo rewrite da Vercel: fim do CORS e dos 76 OPTIONS no stack

> Gerado na fase **Research** em 21/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Devolver 76 recursos ao stack `clinic-scheduler-infra-prod` (494 -> ~418 de
500) sem mudar URL, contrato ou arquitetura das Lambdas, para que o limite do
CloudFormation deixe de aparecer em cada PRD enquanto a decisão estrutural
(segundo service ou consolidação por domínio) é tomada com calma.

O caminho: os três apps de browser (painel, site público, checkin) passam a
chamar a API pelo **mesmo domínio em que são servidos**, via `rewrites` da
Vercel para o API Gateway. Sem origem cruzada não há preflight; sem preflight,
o `cors: true` de cada rota, que gera um método `OPTIONS` por recurso, pode
sair do `serverless.yml`.

---

## 2. Contexto

### 2.1 O stack, medido em 21/11/2026

```
aws cloudformation list-stack-resources --stack-name clinic-scheduler-infra-prod
```

| Bloco | Recursos |
|---|---|
| `ApiGateway::Method` | 174, dos quais **76 são `OPTIONS`** do `cors: true` |
| `ApiGateway::Resource` (segmentos de caminho) | 103 |
| `Lambda::Function` | 86 |
| `Lambda::Permission` | 86 |
| `IAM::Role` | 25 (1 compartilhada + 24 próprias por DynamoDB ou invoke) |
| Infra fixa (rules, tabelas, buckets, layer, RestApi, Deployment) | 20 |
| **Total** | **494 de 500** |

Mais da metade do stack é API Gateway. Cada endpoint novo custa 5 recursos
(função, permission, resource, método, `OPTIONS`). O PRD 053 já teve de entrar
como `POST appointments?simular=true` por falta de espaço para uma rota.
Histórico das limpezas anteriores em `prd/013-limite-do-cloudformation.md`
(roles compartilhadas, `versionFunctions: false`, log groups fora do stack).
O 013 descartou mexer no CORS por exigir "Gateway Responses e um proxy único";
este PRD escolhe outro caminho, que não toca no API Gateway: tirar a origem
cruzada do browser.

### 2.2 Quem chama a API de um browser

Levantado em código e na API da Vercel (team `rodrigocardosodevrods-2504s-projects`):

| App (pasta) | Projeto Vercel | Domínios | API hoje | Auth |
|---|---|---|---|---|
| Painel (`frontend/`) | `traffic-manager` | `traffic-manager-eight.vercel.app` + previews por branch | `VITE_API_BASE_URL` (production -> prod; preview/development -> dev) | `x-api-key` com a sessão do login (`api.ts`) |
| Site público (`booking-site/`) | `booking-site` | `booking-site-neon.vercel.app`, `agendar.nobrelaser.com.br`, `agendar.draclaradourado.com.br` + previews | idem | `x-api-key` = `VITE_BOOKING_API_KEY` (chave pública restrita a `public/*`) |
| Checkin (`checkin/`) | `checkin-prod` | `checkin-prod.vercel.app`, `documentos.nobrelaser.com.br`, `documentos.draclaradourado.com.br` | `VITE_API_BASE_URL` -> prod | idem |
| Checkin dev | `checkin-dev` | `checkin-dev-ten.vercel.app` | `VITE_API_BASE_URL` -> dev (no env "production" do projeto) | idem |

Os três `vercel.json` hoje têm só o rewrite de SPA (`/(.*)` -> `/`).

**O que NÃO passa pelo API Gateway com CORS e não muda:** o upload de logo do
painel (`ImageUploadField`) faz `PUT` direto numa URL pré-assinada do S3; o
CORS ali é do bucket. Os webhooks (z-api, Asaas, ClickSign) são servidor a
servidor, sem preflight. A landing page da Nobre (Lovable) não chama o
scheduler.

### 2.3 O que o `cors: true` faz hoje

Para cada rota com `cors: true` (97 declarações em `sls/functions/*/interface.yml`,
76 recursos de caminho distintos), o Serverless cria um método `OPTIONS` de
integração MOCK que responde ao preflight. As respostas das Lambdas também
carregam `Access-Control-Allow-*` fixos em `src/utils/http.py::http_response`.
Com same-origin, nada disso é lido pelo browser.

---

## 3. Escopo

### Dentro do escopo
- `vercel.json` dos três apps: rewrite `/api/(.*)` para o API Gateway do stage
  certo, mantendo o rewrite de SPA para o resto.
- Os três apps passam a usar `/api` como base. `VITE_API_BASE_URL` deixa de
  apontar para o API Gateway.
- Desenvolvimento local (`npm run dev`): `server.proxy` do Vite em `/api`
  apontando para o API Gateway de dev, para o fluxo local seguir igual.
- Remover `cors: true` de todas as rotas e os cabeçalhos `Access-Control-*` de
  `http_response` (fonte única: sem CORS em lugar nenhum, para um cliente
  esquecido falhar na hora, e não só em preflight).
- Guarda em teste: nenhum `cors: true` nos `interface.yml`; `LIMITE_DE_FUNCOES`
  remedido e atualizado com a conta nova (~4 recursos por função).
- Roteiro `tests/integration/055-api-pelo-rewrite.md` (dev e prod) e medição
  do stack antes e depois.

### Fora do escopo
- Dividir o stack (segundo service) ou consolidar Lambdas por domínio. Este PRD
  compra tempo para essa decisão, não a substitui.
- HTTP API v2, Gateway Responses, mudança de URL do API Gateway.
- Mexer na autenticação (`x-api-key`, sessão STAFF, chave pública do site).
- Postman e `curl` do roteiro continuam batendo direto no API Gateway; não
  dependem de CORS.

---

## 4. Desenho

### 4.1 Rewrite por host (sem código novo na Vercel)

`vercel.json` é estático e não lê variável de ambiente, mas um mesmo projeto
serve produção e previews com o mesmo arquivo. A escolha do stage vai pelo
host, com `has` nas regras:

```json
{
  "rewrites": [
    { "source": "/api/(.*)",
      "has": [{ "type": "host", "value": "(.*-git-.*|.*-[a-z0-9]{9}-.*)\\.vercel\\.app" }],
      "destination": "https://<api-dev>.execute-api.us-east-1.amazonaws.com/dev/$1" },
    { "source": "/api/(.*)",
      "destination": "https://ycomrg2zy7.execute-api.us-east-1.amazonaws.com/prod/$1" },
    { "source": "/((?!api/).*)", "destination": "/" }
  ]
}
```

- Previews da Vercel (`<projeto>-git-<branch>-<team>` e `<projeto>-<hash>-<team>`)
  caem em dev; produção e domínios próprios das clínicas (`agendar.*`,
  `documentos.*`) caem em prod. Um domínio novo de clínica não exige mudança.
- `checkin-dev` é um projeto separado cujo "production" aponta para dev: ganha
  uma regra a mais pelo host `checkin-dev-ten.vercel.app`. Os ids dos
  API Gateways de dev e prod ficam escritos no `vercel.json`; não são segredo
  (já estão no bundle dos três apps hoje).
- O rewrite de SPA passa a excluir `/api/`, senão engole a chamada.

**Alternativa considerada:** Edge Middleware (`@vercel/edge`) lendo
`process.env.API_BASE_URL` e reescrevendo para URL externa. Mantém o padrão de
env var por ambiente e dispensa a regra por host, mas acrescenta uma invocação
de edge por chamada (cobrada acima da cota) e código de infraestrutura em três
repositórios de front. Fica como plano B se a regra por host se mostrar frágil
em dev.

### 4.2 Ordem de implantação

A ordem importa porque **remover o `OPTIONS` antes de um app estar no rewrite
derruba esse app inteiro**. Cada passo é reversível sozinho.

1. **Dev, tudo.** `vercel.json` + base `/api` nos três apps; preview da Vercel
   (que aponta para dev) exercita o rewrite; checkin-dev idem. Deploy do
   scheduler em dev **sem** `cors: true`. Smoke dos três apps contra dev.
2. **Prod, apps primeiro, um por vez.** Merge dos três apps (a Vercel sobe
   sozinha). Enquanto o backend de prod ainda tem `OPTIONS`, os dois caminhos
   funcionam: é a janela segura. Smoke de cada app em prod pelo André.
3. **Prod, backend por último.** `serverless deploy --stage prod` sem
   `cors: true`. Medir o stack. Só aqui os 76 recursos saem.

Rollback de cada passo: recolocar `cors: true` e redeploy (~12 min), ou
reverter o `vercel.json` (deploy da Vercel, ~2 min). Nenhum dado é tocado.

### 4.3 O que conferir em dev antes de prod

- Latência: medir `GET clinics/{c}/dashboard` direto e via rewrite, 20
  chamadas cada; esperado acréscimo de dezenas de ms.
- Corpo grande: o maior `POST` JSON do painel (registro de sessão com HR) e a
  resposta mais pesada (`GET appointments` sem filtro de data, 1043 itens em prod) passam
  pelo rewrite inteiros. Rewrites externos da Vercel são proxy no edge e não
  têm o limite de 4,5 MB das Serverless Functions; conferir na prática.
- Erros do API Gateway (403 de chave errada, 404 de rota) chegam ao app como
  JSON e o `api.ts` trata igual.
- `window.location.hostname` do booking-site continua decidindo domínio padrão
  x próprio; o rewrite não muda o host visto pelo app.

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `frontend/vercel.json`, `booking-site/vercel.json`, `checkin/vercel.json` | modificar | rewrite `/api/(.*)` por host + SPA excluindo `/api/` |
| `frontend/vite.config.ts`, `booking-site/vite.config.ts`, `checkin/vite.config.ts` | modificar | `server.proxy['/api']` -> API Gateway de dev (`VITE_API_PROXY_TARGET`, default dev) |
| `frontend/src/services/api.ts`, `booking-site/src/services/api.ts`, `checkin/src/services/api.ts` | modificar | `baseURL: '/api'` |
| `*/.env`, `*/.env.example`, `*/src/vite-env.d.ts` | modificar | `VITE_API_BASE_URL` sai; `VITE_API_PROXY_TARGET` entra (só local) |
| Vercel (dashboard/API) | operar | remover `VITE_API_BASE_URL` dos 4 projetos depois do corte |
| `scheduler/sls/functions/*/interface.yml` (29 pastas, 97 ocorrências) | modificar | remover `cors: true` |
| `scheduler/src/utils/http.py` | modificar | tirar `Access-Control-*` de `http_response` |
| `scheduler/tests/unit/test_limite_de_recursos.py` | modificar | `LIMITE_DE_FUNCOES` remedido; teste novo: nenhum `cors: true` |
| `scheduler/tests/integration/055-api-pelo-rewrite.md` | criar | roteiro dev/prod com medição do stack |
| `frontend/CLAUDE.md`, `scheduler/README` (se citar CORS) | modificar | como a API é alcançada |

---

## 6. Dependências e riscos

- **Dependências:** acesso à Vercel pelo `/prod/VERCEL_API_TOKEN` (o André não
  é membro do time) para apagar `VITE_API_BASE_URL` e ler o estado dos
  deploys; ids dos API Gateways de dev e prod.
- **Risco 1, cliente esquecido.** Um app de browser fora da tabela 2.2 para de
  funcionar no passo 3. Mitigação: o passo 3 é o último e isolado; grep por
  `execute-api` em todos os repositórios antes; `http_response` sem CORS faz o
  cliente falhar de forma explícita.
- **Risco 2, Vercel no caminho da API.** Indisponibilidade da Vercel passa a
  derrubar também as chamadas do painel, não só a tela. Hoje a tela já cai, e o
  painel sem tela não chama nada; na prática o acoplamento quase não cresce.
- **Risco 3, regra por host errada.** Preview caindo em prod, ou domínio de
  clínica caindo em dev. Mitigação: testes do roteiro batem cada host dos 4
  projetos e conferem o stage pela resposta (`GET clinics` lista clínicas
  diferentes em dev e prod).
- **Risco 4, custo.** Bandwidth e edge requests da Vercel passam a contar as
  chamadas de API. Volume atual é de duas clínicas; medir no primeiro mês.
- **Não há migration, não há dado tocado, não há mudança de URL pública.**

---

## 7. Decisões (André, 21/11/2026)

1. **Roteamento dev/prod:** regra por host no `vercel.json`. Edge Middleware
   descartado (custo por chamada e código de infra em três fronts). Risco
   aceito: um preview fora do padrão de host cairia em prod; o roteiro bate
   cada host dos 4 projetos.
2. **Cabeçalhos CORS do `http.py`:** remover junto. Sem `OPTIONS` eles já não
   fazem nada; manter seria código que parece configurar CORS e não configura.
3. **Prefixo:** `/api`. Nenhum dos três apps tem rota de página começando por
   `/api`.
4. **Janela do passo 3 em prod:** em sequência com os demais, sem esperar
   horário. O smoke dos quatro projetos em prod no passo 2 é o que prova que
   ninguém chama o API Gateway direto; se algo cair, rollback de ~12 min.

---

## 8. Critérios de aceite

- [ ] Os três apps funcionam em produção chamando `/api/...` no próprio
  domínio; previews da Vercel e `checkin-dev` chegam ao stage dev.
- [ ] `npm run dev` dos três apps fala com dev pelo proxy do Vite.
- [ ] Nenhum `cors: true` nos `interface.yml`; nenhum `OPTIONS` no stack;
  `http_response` sem `Access-Control-*`.
- [ ] Stack de prod medido em ~418 de 500 após o passo 3; `LIMITE_DE_FUNCOES`
  atualizado com a conta nova e o comentário da medição.
- [ ] `VITE_API_BASE_URL` apagada dos 4 projetos da Vercel e dos `.env`.
- [ ] Roteiro 055 com os hosts testados, latência medida e o número do stack
  antes e depois.
- [ ] pytest, vitest, build e lint dos três apps verdes.

---

## 9. Referências

- `docs/work/prd/013-limite-do-cloudformation.md` (limpezas anteriores)
- `docs/work/prd/053-popup-da-agenda-confirmacao-e-politica-de-desconto.md`
  (cotação sem rota própria por falta de espaço)
- `scheduler/tests/unit/test_limite_de_recursos.py`
- Vercel: rewrites com `has` por host; Build Output e Edge Middleware (plano B)

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada: `spec/055-api-pelo-rewrite-da-vercel-sem-cors.md`
- [ ] Implementado em dev: (data)
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
