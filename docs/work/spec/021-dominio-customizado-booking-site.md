# Spec — 021 Domínio customizado do booking-site

> Gerado após a implementação (PR #105), a partir de
> `docs/work/prd/021-dominio-customizado-booking-site.md`. Documenta o que foi
> feito, não um plano futuro.

---

## 1. A forma da mudança

Três peças que não se conhecem diretamente, ligadas só pelo dado
`clinics.custom_domain`:

```
Painel (CustomDomainField)
  → PUT /clinics/{clinicId} {custom_domain}
      → VercelDomainService.add_domain/remove_domain   (API da Vercel)
      → grava custom_domain no Postgres

booking-site (boot)
  → hostname é *.vercel.app/localhost?
      sim → clinicId vem do path, igual sempre foi
      não → GET /public/resolve-domain?host=...  → clinicId
```

Nenhuma das duas metades sabe da outra em tempo de execução — o booking-site
nunca chama a Vercel, e o `UpdateClinic` nunca resolve hostname. O único
contrato compartilhado é a coluna no banco.

---

## 2. Arquivos criados

### 2.1 `scheduler/src/services/vercel_domain_service.py`

Wrapper fino sobre a API da Vercel (`api.vercel.com`), sem SDK:

- `add_domain(domain)` — `POST /v10/projects/{id}/domains`. Trata
  `domain_already_in_use` como sucesso quando o dono já é este projeto
  (idempotente: salvar o mesmo domínio duas vezes não deve falhar).
- `remove_domain(domain)` — `DELETE /v9/projects/{id}/domains/{domain}`. 404
  também é sucesso (já não está lá).
- `get_domain_status(domain)` — devolve `{registered, verified, dns_records}`
  pronto pro painel renderizar, sem expor o formato da API da Vercel. Quando
  verificado, infere o registro recomendado (apex → `A` `76.76.21.21`;
  subdomínio → `CNAME` `cname.vercel-dns.com`); quando pendente, repassa o
  desafio de verificação que a própria Vercel exige.
- `configured` — `False` sem `VERCEL_API_TOKEN`. Todo chamador trata isso como
  "integração desligada", nunca como erro.

### 2.2 `scheduler/src/functions/public_booking/resolve_domain.py`

`GET /public/resolve-domain?host=...` → `{clinicId}` ou 404. Normaliza porta
(`host:porta` → `host`, porque o browser manda porta em dev). Registrado em
`router.py` e `public_booking/interface.yml` — mesmo Lambda, mesma API key
pública (`require_booking_intake_api_key`) das demais rotas.

### 2.3 `booking-site/src/utils/domain.ts`

`isDefaultDomain(hostname)` — `localhost`, `127.0.0.1` ou `*.vercel.app`.
Decide, uma vez, no boot (`router.tsx`), qual árvore de rotas montar.

### 2.4 `booking-site/src/store/clinicIdContext.ts` + `hooks/useClinicId.ts`

`{ clinicId, basePath }`. `basePath` é `/${clinicId}` no domínio padrão e `''`
no domínio próprio — todo link interno usa `basePath || '/'` em vez de
`/${clinicId}` hardcoded, e funciona nos dois mundos sem `if`.

### 2.5 `booking-site/src/layouts/BookingChrome.tsx`

Header (logo ou "Agende online"), favicon dinâmico e o modal "Meus
agendamentos" — o que `BookingLayout` fazia sozinho antes, agora compartilhado
pelos dois layouts (ver 2.6).

### 2.6 `booking-site/src/layouts/CustomDomainLayout.tsx`

Resolve `clinicId` por `resolveDomain(window.location.hostname)` (React
Query, `staleTime: Infinity` — não muda durante a sessão). Estados de
carregamento e erro ("Este endereço não está associado a nenhum salão")
cobertos antes de montar `BookingChrome`.

---

## 3. Arquivos modificados

### 3.1 `scheduler/src/functions/clinic/update.py`

- `custom_domain` entra em `ALLOWED_FIELDS`.
- Antes do `UPDATE`, lê o `custom_domain` **antigo** (precisa dele pra saber o
  que remover da Vercel se a clínica trocar ou limpar o domínio).
- `_sync_vercel_domain(previous, new)`: chama `remove_domain`/`add_domain`
  conforme o que mudou. Roda **depois** do `UPDATE` no Postgres — o dado da
  clínica nunca fica refém da Vercel. Falha vira `domainWarning` na resposta,
  não erro 500.

### 3.2 `scheduler/src/functions/clinic/get.py`

Quando `clinic.custom_domain` existe e `VercelDomainService.configured`,
anexa `custom_domain_status` com o resultado de `get_domain_status` — sempre
ao vivo, nunca persistido, porque a verificação de DNS muda do lado da Vercel.

### 3.3 `scheduler/serverless.yml`

```yaml
VERCEL_API_TOKEN: ${ssm:/${self:custom.stage}/VERCEL_API_TOKEN, ''}
VERCEL_TEAM_ID: team_ZLFt6HlpGbYXZsEloIbOVq96
BOOKING_SITE_VERCEL_PROJECT_ID: prj_0TsMiEsoApAlYoVMN0YboJs5hmAf
```

Time e projeto são fixos (um projeto Vercel só, pros dois stages) e não são
segredo — só o token vai pro SSM, com fallback vazio pra não quebrar o deploy
antes de ele existir.

### 3.4 `scheduler/src/scripts/setup_database.py`

```sql
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS custom_domain VARCHAR(255);
CREATE UNIQUE INDEX IF NOT EXISTS uq_clinics_custom_domain
  ON scheduler.clinics(custom_domain) WHERE custom_domain IS NOT NULL;
```

Índice parcial: duas clínicas sem domínio não colidem (NULL é distinto de
NULL no índice), só colidem se tentarem o **mesmo** domínio — que é a
constraint que importa.

### 3.5 `booking-site/src/router.tsx`

```ts
export const router = isDefaultDomain(window.location.hostname)
  ? createBrowserRouter([{ path: '/:clinicId', element: <BookingLayout />, children }, { path: '*', element: <NotFound /> }])
  : createBrowserRouter([{ path: '/', element: <CustomDomainLayout />, children }])
```

As duas árvores nunca coexistem — decidido uma vez, no boot, pelo host que o
navegador mandou. Evita a colisão de rotas que existiria tentando casar
`/:clinicId` (dinâmico) com `/` + filhos (estático) na mesma árvore.

### 3.6 `booking-site/src/pages/Home.tsx` e `Booking.tsx`

Todo `useParams<{clinicId}>()` e todo `/${clinicId}` literal viram
`useClinicId()` e `${basePath}`/`basePath || '/'`. Comportamento idêntico no
domínio padrão; no domínio próprio, os links internos não carregam mais o
`clinic_id` na URL.

### 3.7 `frontend/src/pages/site-agendamento/SiteAgendamentoPage.tsx` +
`frontend/src/components/ui/CustomDomainField.tsx`

Campo de texto + "Salvar" + tabela de registros de DNS pendentes + badge
Verificado/Pendente + "Verificar novamente" (refetch do `GetClinic`).

---

## 4. Ordem de implementação (como foi feito)

1. Backend: `vercel_domain_service.py`, migration, `UpdateClinic`/`GetClinic`,
   rota `resolve_domain` — testado por 16 testes unitários novos antes de
   qualquer deploy.
2. Deploy em `dev` → bloqueado pela divergência de log groups (PRD §4) →
   reconciliado via `IMPORT` change set → deploy real.
3. Smoke test via `curl` direto nos dois ambientes (salvar domínio, resolver
   hostname, status de verificação).
4. Frontend do painel (`CustomDomainField`) e deploy.
5. Token real da Vercel fornecido pelo Rodrigo → SSM `/dev/` e `/prod/` →
   re-deploy pra ativar a integração de verdade (até então rodava em modo
   degradado, só gravando no banco).
6. Deploy em produção, testado com domínio real de uma clínica
   (`agendar.draclaradourado.com.br` → `clinicaessenciaestetica-9668a4`).

---

## 5. Convenções respeitadas

- Zero Lambda nova — reaproveita `UpdateClinic`, `GetClinic`, `public_booking`.
- Secrets por SSM (`/${stage}/VERCEL_API_TOKEN`), nunca hardcoded.
- Migration idempotente, `CREATE TABLE` e `ALTER TABLE` em sincronia.
- `clinic_id` kebab-case inalterado; nada nesta feature cria `clinic_id` novo.
