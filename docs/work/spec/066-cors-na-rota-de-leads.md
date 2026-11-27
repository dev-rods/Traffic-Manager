# Spec - 066 CORS de volta em `POST /leads` e guarda das rotas chamadas de fora da Vercel

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/066-cors-na-rota-de-leads.md`

---

## 1. Resumo

Só scheduler. `CreateLead` volta a declarar `cors: true` (o Serverless recria
o `OPTIONS /leads` mock) e todas as respostas da rota levam
`Access-Control-Allow-Origin: *`. O teste "nenhuma rota com cors" do PRD 055
vira uma lista nomeada de rotas chamadas de fora da Vercel, conferida nos dois
sentidos lendo o YAML. Deploy dev e prod; conferência só por `curl` (D2).

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/tests/unit/test_lead_create_cors.py` | toda resposta do handler (201, 400, 401, 500) traz `Access-Control-Allow-Origin: *` |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `scheduler/sls/functions/lead/interface.yml` | `cors: true` no `http` de `CreateLead`, com comentário |
| `scheduler/src/functions/lead/create.py` | `handler` atual vira `_handler`; novo `handler` acrescenta o cabeçalho a qualquer resposta |
| `scheduler/tests/unit/test_limite_de_recursos.py` | `TestSemCors` vira `TestCorsSoOndeChamamDeFora` com `CHAMADAS_DE_FORA_DA_VERCEL`; nota no `LIMITE_DE_FUNCOES` |
| `scheduler/src/utils/http.py` | comentário de `http_response` cita a exceção (sem mudar comportamento) |
| `docs/work/prd/055-api-pelo-rewrite-da-vercel-sem-cors.md` | nota da exceção desde 26/11 |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação

1. Teste do cabeçalho e guarda nova (falham).
2. `interface.yml` e `create.py` (passam).
3. `pytest` completo.
4. Deploy dev; `curl` OPTIONS e POST inválido em dev.
5. Deploy prod; mesmo `curl` em prod; medir o stack.
6. PR e TASKS_LOG.

---

## 6. Detalhes por arquivo

### `sls/functions/lead/interface.yml`

```yaml
  events:
    - http:
        path: leads
        method: post
        # PRD 066: a LP da Essencia (draclaradourado.com.br, Lovable
        # estatico) grava do navegador, de outra origem, com x-api-key: o
        # browser faz preflight. Unica excecao ao PRD 055. Sai quando a LP
        # gravar pelo servidor (como a da Nobre).
        cors: true
```

O `cors: true` do Serverless libera `X-Api-Key` e `Content-Type` nos
`Allow-Headers` por padrão, e `Allow-Origin: *`.

### `src/functions/lead/create.py`

- `def handler` atual renomeado para `_handler`.
- Novo:
  ```python
  # PRD 066: chamada de outra origem (LP da Essencia). Sem o cabecalho na
  # resposta o POST grava, mas o fetch do navegador recebe erro de CORS ao
  # ler e a LP loga falha de um lead salvo. Vale para TODA resposta, inclusive
  # o 401 que sai de require_intake_api_key.
  CORS = {"Access-Control-Allow-Origin": "*"}

  def handler(event, context):
      resposta = _handler(event, context)
      resposta.setdefault("headers", {}).update(CORS)
      return resposta
  ```
- `serverless.yml`/`interface.yml` continuam apontando para `handler`.

### `tests/unit/test_limite_de_recursos.py`

- `import yaml` (PyYAML já instalado); o `interface.yml` usa `${...}` em
  strings, o `safe_load` aceita.
- Constante na classe:
  ```python
  CHAMADAS_DE_FORA_DA_VERCEL = {
      "sls/functions/lead/interface.yml": {
          "CreateLead": "LP da Essencia (draclaradourado.com.br, Lovable estatico) "
                        "grava do browser; sai quando gravar pelo servidor (PRD 066)",
      },
  }
  ```
- Helper que percorre `sls/functions/*/interface.yml` e devolve
  `{(arquivo, funcao): [cors de cada evento http]}`.
- `test_rota_chamada_de_fora_tem_cors`: para cada função listada, existe e
  todo `http` dela tem `cors` verdadeiro.
- `test_nenhuma_outra_rota_tem_cors`: função fora da lista com qualquer
  `cors` falha, com a mensagem que manda registrar na lista.
- Nota em `LIMITE_DE_FUNCOES`: "26/11/2026 (PRD 066): +1 OPTIONS
  (`/leads`), medido depois do deploy."

### `tests/unit/test_lead_create_cors.py`

- Monkeypatch de `require_intake_api_key`, `PostgresService` e
  `LeadService` no módulo; casos: sem chave (401), corpo vazio (400),
  campos faltando (400), sucesso (201), exceção no upsert (500). Em todos,
  `resp["headers"]["Access-Control-Allow-Origin"] == "*"`.

---

## 7. Verificação

- `curl -X OPTIONS .../{stage}/leads -H "Origin: https://draclaradourado.com.br" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type,x-api-key"` responde 200 com os três `Access-Control-*`.
- `curl -X POST .../{stage}/leads -H "Origin: ..." -d '{}'` responde 401 com `Access-Control-Allow-Origin: *` (sem chave, nada é gravado).
- `aws cloudformation list-stack-resources` conta 419 em prod.
- Sem lead de teste (D2). O primeiro lead orgânico com `origin=https://draclaradourado.com.br` fecha o critério.

---

## 8. Convenções

- Deploys dev e prod nunca em paralelo; conferir a layer do dev antes.
- `pytest` completo antes do commit.
