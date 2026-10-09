# PRD — 021 Domínio customizado do booking-site

> Gerado na fase **Research**, documentado retroativamente após a implementação
> (ver `## Status`). Use como referência de arquitetura e decisões, não como
> input vivo para uma Spec ainda não escrita.

---

## 1. Objetivo

Permitir que cada clínica use o **próprio domínio** (ex:
`agendar.suaempresa.com.br`) na página pública de agendamento, em vez do
endereço padrão `booking-site-neon.vercel.app/<clinic_id>`.

---

## 2. Contexto

O `booking-site` é um projeto Vercel único, multi-tenant por `clinic_id` no
path. Até aqui, toda clínica compartilhava o mesmo domínio — aceitável para
validar o produto, mas ruim pra quem quer divulgar o link de agendamento com a
própria marca.

O Rodrigo pediu, explicitamente: **"minha ideia é ter uma forma clara de
colocar isso em um novo domínio qualquer"**, e depois confirmou o escopo: o
domínio novo hospeda o booking-site inteiro (não é um domínio por clínica
fixo de antemão — qualquer clínica pode trazer o seu), e a configuração deve
ser **dinâmica, pelo painel**, não uma tarefa manual que eu faço toda vez que
uma clínica pede.

---

## 3. Escopo

### Dentro do escopo

- Campo de domínio customizado na página "Site de Agendamento" do painel.
- Registro automático do domínio no projeto Vercel do `booking-site`, via API
  da Vercel, disparado pelo próprio `PUT /clinics/{clinicId}`.
- Instruções de DNS (CNAME ou A, conforme subdomínio ou domínio raiz) e status
  de verificação ("Verificado" / "Pendente") exibidos no painel, lidos ao vivo
  da Vercel — nunca cacheados no banco, porque a verificação de DNS muda do
  lado de lá.
- `booking-site` detecta, pelo hostname, quando está servindo um domínio
  próprio (fora de `*.vercel.app`/`localhost`) e resolve a clínica dona dele
  sem precisar do `clinic_id` na URL.

### Fora do escopo

- **Registro do domínio em si.** A compra/registro do domínio é do dono da
  clínica, em qualquer provedor — o sistema só consome um domínio já
  existente.
- **Múltiplos domínios por clínica.** Uma clínica, um domínio customizado.
- **Subpaths por clínica dentro do domínio próprio** (ex:
  `suaempresa.com/agendamento`) — o domínio aponta direto pra raiz do
  booking-site daquela clínica.

---

## 4. Decisão de arquitetura: zero recurso novo no CloudFormation

Em 07/10/2026 a stack de produção do `scheduler` estava em **496 de 500**
recursos (ver `prd/013-limite-do-cloudformation.md`) — qualquer Lambda nova
quebraria o deploy. Isso decidiu o desenho:

- **Nenhuma Lambda nova.** A chamada à API da Vercel (registrar/remover
  domínio) acontece **dentro** do handler `UpdateClinic` já existente, quando
  o campo `custom_domain` muda no corpo do `PUT`. `GetClinic` ganhou a mesma
  lógica para consultar o status ao vivo.
- **Uma rota pública nova, no Lambda público que já existe.** `public_booking`
  já é uma Lambda única com roteamento interno (`router.py`), criada
  justamente para não estourar o limite — `GET /public/resolve-domain` entrou
  ali como mais uma entrada do dicionário de rotas, custando só
  `ApiGateway::Resource` + `Method` + `OPTIONS` (3 recursos), não uma função
  inteira (que custaria ~6-7).

Resultado: a feature inteira coube em **+3 recursos** de CloudFormation.

### Achado no caminho: a stack de `dev` estava divergente do Git

Ao tentar aplicar essa mudança em `dev`, o deploy falhou com
`AWS::EarlyValidation::ResourceExistenceCheck`. Investigando: alguém havia
retirado os 78 `AWS::Logs::LogGroup` da stack de `dev` diretamente na AWS, a
partir de uma versão do `serverless.yml` que **nunca foi commitada** — o
Git ainda declarava os log groups, e o deploy tentava recriá-los colidindo com
os que já existiam de verdade (retidos, não apagados).

Resolvido **sem perda de histórico**: os 78 log groups foram reimportados pra
stack via `aws cloudformation create-change-set --change-set-type IMPORT`
(`DeletionPolicy: Retain` nos 78, changeset só de `Import`, nada mais tocado).
Essa divergência acabou se formalizando pouco depois no PR #104
(`infra/log-groups-padrao-remove`), que trouxe a remoção dos log groups para o
`serverless.yml` versionado — ver `prd/013-limite-do-cloudformation.md`.

### Achado no caminho: deployment do API Gateway não capturava a rota nova

Em dev **e** em prod, logo após o deploy, `GET /public/resolve-domain`
devolvia `403 MissingAuthenticationTokenException` — erro de API Gateway, não
da Lambda. O recurso e o método existiam na API (`aws apigateway
get-resources` confirmava), mas o snapshot do deployment ativo da stage não os
incluía: um deployment novo foi criado pelo CloudFormation na mesma
atualização em que o recurso nasceu, e por uma corrida conhecida entre os dois
tipos de recurso, o snapshot ficou incompleto. Corrigido forçando um
`aws apigateway create-deployment` manual pra cada stage — reflete o estado
atual da API sem precisar de outro deploy do zero.

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/vercel_domain_service.py` | criar | Fala com a API da Vercel: `add_domain`, `remove_domain`, `get_domain_status` |
| `scheduler/src/functions/clinic/update.py` | modificar | `custom_domain` em `ALLOWED_FIELDS`; `_sync_vercel_domain` chama o service quando o campo muda |
| `scheduler/src/functions/clinic/get.py` | modificar | Anexa `custom_domain_status` (verificado + registros de DNS) quando a clínica tem domínio |
| `scheduler/src/functions/public_booking/resolve_domain.py` | criar | `GET /public/resolve-domain?host=...` → `clinic_id` |
| `scheduler/src/functions/public_booking/router.py` | modificar | Registra a rota nova no dicionário de rotas |
| `scheduler/sls/functions/public_booking/interface.yml` | modificar | Evento HTTP da rota nova |
| `scheduler/serverless.yml` | modificar | `VERCEL_API_TOKEN` (SSM), `VERCEL_TEAM_ID`, `BOOKING_SITE_VERCEL_PROJECT_ID` |
| `scheduler/src/scripts/setup_database.py` | modificar | `scheduler.clinics.custom_domain` + índice único parcial |
| `booking-site/src/utils/domain.ts` | criar | `isDefaultDomain(hostname)` |
| `booking-site/src/store/clinicIdContext.ts` | criar | Contexto `{ clinicId, basePath }` — `basePath` vazio em domínio próprio |
| `booking-site/src/hooks/useClinicId.ts` | criar | Hook do contexto acima, substitui `useParams` direto |
| `booking-site/src/layouts/BookingChrome.tsx` | criar | Header, favicon dinâmico e modal "Meus agendamentos" — compartilhado pelos dois layouts |
| `booking-site/src/layouts/BookingLayout.tsx` | modificar | `clinicId` por path (domínio padrão), delega pro `BookingChrome` |
| `booking-site/src/layouts/CustomDomainLayout.tsx` | criar | Resolve `clinicId` pelo hostname via `resolve-domain`, delega pro `BookingChrome` |
| `booking-site/src/router.tsx` | modificar | Duas árvores de rota, escolhidas uma vez no boot pelo hostname |
| `frontend/src/components/ui/CustomDomainField.tsx` | criar | Campo de domínio + status + instruções de DNS, na página "Site de Agendamento" |
| `frontend/src/types/index.ts` | modificar | `Clinic.custom_domain`, `CustomDomainStatus` |

---

## 6. Dependências e riscos

**Dependências**

- Token de API da Vercel (`VERCEL_API_TOKEN`), gerado manualmente pelo
  Rodrigo na própria conta Vercel — não existe forma de emitir isso
  programaticamente a partir da sessão autenticada do CLI sem reaproveitar o
  token pessoal do usuário, o que não é apropriado para um segredo de
  automação de longa duração.
- Projeto Vercel do `booking-site` já existente (`prj_0TsMiEsoApAlYoVMN0YboJs5hmAf`).

**Riscos**

- **A integração com a Vercel é "best effort".** Se `VERCEL_API_TOKEN` não
  estiver configurado (ou a chamada falhar), o domínio ainda é salvo no banco
  — o painel mostra um aviso (`domainWarning`), mas não bloqueia a escrita.
  Decisão deliberada: o dado da clínica não pode ficar refém de uma API
  externa.
- **Orçamento do CloudFormation continua apertado.** Mesmo com a limpeza dos
  log groups (PR #104) abrindo bastante folga, cada rota pública nova deveria
  seguir entrando no Lambda `public_booking` já existente, não em uma função
  própria.

---

## 7. Critérios de aceite

- [x] Painel: campo de domínio customizado, com instruções de DNS e status
      verificado/pendente
- [x] `PUT /clinics/{clinicId}` registra/remove o domínio na Vercel quando
      `custom_domain` muda
- [x] `GET /clinics/{clinicId}` traz o status de verificação ao vivo
- [x] `GET /public/resolve-domain` traduz hostname → `clinic_id`
- [x] booking-site funciona nos dois domínios (padrão e customizado) sem
      duplicar lógica de página
- [x] Zero Lambda nova no CloudFormation
- [x] Testado em produção com domínio real (`agendar.draclaradourado.com.br`)

---

## 8. Referências

- `prd/013-limite-do-cloudformation.md` — orçamento de recursos e a remoção
  dos log groups
- `prd/009-site-agendamento-publico.md` — o booking-site original
- PR #105 — implementação
- PR #112, #113, #114 — correções encontradas testando esta feature ao vivo
  (ver `TASKS_LOG.md`)

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/021-dominio-customizado-booking-site.md`
- [x] Implementado em: 07/10/2026 (PR #105)
- [x] Registrado em `TASKS_LOG.md`
