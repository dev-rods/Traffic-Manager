# PRD — 013 Limite de recursos do CloudFormation

> Gerado na fase **Research**. Parte já aplicada; o resto é decisão do André.

---

## 1. Objetivo

Tirar a stack de produção do scheduler de perto do limite de **500 recursos** do
CloudFormation, e deixar o problema documentado com número em vez de impressão.

---

## 2. O estado, medido

`clinic-scheduler-infra-prod`, em 19/09/2026, logo após o deploy do prontuário:

```
497 de 500   (folga: 3)
```

Três de folga significa que **a próxima Lambda com endpoint não sobe**: cada uma
custa 6 ou 7 recursos (função, role, permission, log group, api resource, método
e o OPTIONS do `cors: true`). O deploy falha com
`Number of resources, 5XX, is greater than maximum allowed, 500` e o
CloudFormation faz rollback — ninguém fica no ar pela metade, mas a descoberta
acontece no meio do deploy. Já aconteceu em 05/09/2026.

Composição:

| Recursos | Tipo | Observação |
|---:|---|---|
| 125 | `ApiGateway::Method` | 74 métodos reais + ~51 `OPTIONS` do CORS |
| 75 | `IAM::Role` | uma por função |
| 74 | `Lambda::Function` | |
| 74 | `Lambda::Permission` | uma por função, para o API Gateway invocar |
| 74 | `Logs::LogGroup` | criado pelo serverless para gerir retenção |
| 62 | `ApiGateway::Resource` | os nós de caminho da API |
| 13 | resto | DynamoDB, EventBridge, S3, layer, RestApi |

---

## 3. O que foi aplicado

### As 57 roles idênticas → role compartilhada

Eram **75 roles para 74 funções**, e 57 concediam exatamente a mesma coisa: logs
mais `ssm:GetParameter`.

**O `ssm` era permissão morta.** Os segredos são resolvidos no *deploy* pelo
`${ssm:/...}` do `serverless.yml` e chegam como variável de ambiente; uma busca
por `boto3.client("ssm")` em `src/` não devolve nada. Nenhuma Lambda lê SSM em
runtime.

Sobravam os logs — que a role compartilhada do provider (`IamRoleLambdaExecution`)
já concede. Ou seja: 57 cópias de uma política que **não comprava isolamento
nenhum**, cada uma custando um recurso.

As **17 que tocam DynamoDB ou invocam outra Lambda mantêm role própria**, e aí a
separação significa alguma coisa.

O `ssm:GetParameter` morto saiu também dessas 17. Não economiza recurso (a role
continua existindo), mas é permissão que ninguém usa.

Como cada função foi classificada: partindo do handler, andando pelos imports
dentro de `src/` e procurando `boto3.<serviço>`. Não pela role — pelo código.

**Resultado: 497 → 440. Folga de 3 para 60.**

---

## 4. O que NÃO foi aplicado, e por quê

### Os 74 log groups — **o maior ganho restante, e o mais delicado**

O serverless cria um `AWS::Logs::LogGroup` por função para poder gerir retenção.
Tirá-los da stack devolveria **74 recursos** (440 → 366).

**O problema:** remover o recurso do template faz o CloudFormation **apagar o log
group**, e com ele todo o histórico de logs de produção. Isso é impacto prático,
não cosmético — é o que se lê quando alguma coisa quebra.

Existe um caminho seguro, em dois deploys:

1. Marcar os log groups com `DeletionPolicy: Retain` (via `resources.extensions`
   no `serverless.yml`) e fazer deploy. O template ainda os declara.
2. Fazer as funções pararem de declarar log group. O CloudFormation os remove da
   stack **sem apagar** o recurso real; a Lambda continua escrevendo no mesmo
   log group, que passa a existir fora da stack.

O que se perde: a retenção deixa de ser gerida pelo template. Hoje ela não está
configurada (`logRetentionInDays` não aparece em lugar nenhum), então na prática
não se perde nada — mas passa a ser configuração manual no console.

**Decisão do André.** É seguro se feito nos dois passos, e é o único movimento
que dá espaço de verdade para os próximos anos.

### `serverless-plugin-split-stacks`

Stacks aninhadas: cada uma conta como **1 recurso** na raiz. É a solução padrão
para este limite e resolveria de vez.

**O problema:** mover recursos existentes para stacks aninhadas não é uma
migração — é delete + create. Métodos de API Gateway seriam recriados, e um
deploy que falhe no meio deixa a API em estado parcial. Numa stack que já atende
clínicas em produção, isso é o tipo de risco que se corre com hora marcada e
alguém olhando, não num sábado à noite.

**Recomendação:** só se a limpeza dos log groups não bastar.

### Remover Lambdas sem uso — **medido, e não vale**

20 das 74 funções tiveram **zero invocações em 90 dias**. Parecia 120 recursos
de graça. Olhando uma a uma, não é:

```
CreateClinic      CreateService     CreateFaq        CreateTemplate
CreateProfessional CreateDiscountRules UpdateService  UpdateTemplate
DeleteArea        DeleteServiceArea  GetArea          ListFaq ...
```

São endpoints de **configuração**: a clínica só os chama quando mexe no catálogo,
nos serviços ou nos templates. Zero em 90 dias quer dizer que ninguém mexeu — não
que estão mortos. Removê-los quebraria o painel no dia em que alguém for usar.

Duas exceções que merecem nota, e nenhuma é defeito:

- **`ReminderProcessor`**: zero invocações porque está **desabilitado de
  propósito** (`enabled: false` no `interface.yml`). Não é bug.
- **`SessionRecordHistory`, `LaserProtocol`**: acabaram de nascer.

### Os ~51 `OPTIONS` do CORS

O painel roda no navegador e manda `x-api-key`, o que dispara preflight em toda
chamada. Cada recurso de API precisa do seu `OPTIONS`. Reduzir exigiria trocar o
CORS por Gateway Responses e um proxy único — refatoração grande num ponto onde
errar quebra o painel inteiro.

---

## 5. Onde isso deixa a stack

| Passo | Recursos | Folga | Estado |
|---|---:|---:|---|
| Antes | 497 | 3 | — |
| **Role compartilhada** | **440** | **60** | **aplicado** |
| Log groups fora da stack | 366 | 134 | proposto |
| Split stacks | ~100 | ~400 | último recurso |

60 de folga dão cerca de **8 features novas** com endpoint. Não é definitivo, mas
tira o assunto do caminho por um bom tempo.

---

## 6. O que impede a volta

`tests/unit/test_roles_sem_desperdicio.py` falha se alguém declarar uma role que
só concede logs e/ou `ssm:GetParameter`.

Isso importa porque o defeito volta por **cópia e cola**: o jeito de escrever uma
função nova é copiar a vizinha, e a vizinha tinha o bloco. O teste falha no
momento em que o desperdício entra, e não seis meses depois num deploy que não
sobe.

---

## 7. Verificação

- **dev**: deploy completo, 440 recursos, 18 roles. 18 endpoints exercitados, 18
  responderam 200 — incluindo os dois que mantêm role própria (`ListLeads`,
  `BotMetrics`).
- **Logs de dev**: busca por `AccessDenied`, `not authorized`,
  `UnauthorizedOperation` nas funções migradas — **nenhuma ocorrência**.
- De passagem: o banco de **dev** estava sem várias migrations (faltavam
  `duration_rules`, `patients.cpf`, `appointments.is_first_visit` e as tabelas do
  prontuário). Rodado o `setup_database.py` lá, 126 statements, zero erros.
- Órfão preexistente, não relacionado: o stack de dev tenta apagar um
  `ClinicAssetsBucket` que não existe no código e falha porque o bucket não está
  vazio. Só dev, e de antes desta task.

---

## Status

- [x] Role compartilhada aplicada
- [ ] Log groups fora da stack — decisão do André
- [ ] Split stacks — só se necessário
