# Spec - 051 Registro de sessão: áreas com o nome certo e nenhum registro incompleto

> Gerada em 19/11/2026 a partir de `prd/051-registro-de-sessao-areas-certas-e-sem-registro-incompleto.md`. Decisões da §4 confirmadas pelo André em 19/11.
> Fluxo: código → PR → deploy dev → roteiro → prod com o André.

---

## 1. O que muda, em três frases

A montagem das aplicações a partir do agendamento passa a existir só no backend (`aplicacoes_do_agendamento`), exposta por um `GET` novo que a tela chama ao escolher a sessão; o caminho paralelo do navegador (`escolheSessao` + `nomeDoProtocolo`) é apagado, e com ele a troca do nome comercial pelo nome do protocolo. `valida_aplicacoes` passa a exigir método e todos os campos do método, e recusa registro sem aplicação; a tela calcula as mesmas pendências antes de mandar e destaca campo por campo. A investigação da Costeleta vira a primeira tarefa, com consulta registrada no roteiro.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/protocolo_laser.py` | **novos** `nome_da_area(chave)` e `ROTULO_DO_CAMPO` |
| `scheduler/src/services/historico_de_sessao.py` | `aplicacoes_do_agendamento` devolve `protocol_area_name`; `valida_aplicacoes` exige método e campos; **nova** `exige_aplicacoes` |
| `scheduler/src/functions/patient_record/session_applications.py` | **novo** handler `GET clinics/{clinicId}/appointments/{appointmentId}/session-applications` |
| `scheduler/sls/functions/patient_record/interface.yml` | rota nova |
| `scheduler/src/functions/patient_record/create.py` | `applications` obrigatório no corpo; fallback `aplicacoes_do_agendamento` sai; vazio = 400 |
| `scheduler/src/functions/patient_record/update.py` | `applications: []` = 400 |
| `scheduler/tests/unit/test_historico_de_sessao.py` | `TestValidacao` reescrito para a regra nova |
| `scheduler/tests/unit/test_session_applications.py` | **novo** |
| `frontend/src/types/index.ts` | `AplicacaoDeSessao.protocol_area_name?`; `AplicacoesDoAgendamento` |
| `frontend/src/services/sessionRecords.service.ts` | `aplicacoesDoAgendamento(clinicId, appointmentId)` |
| `frontend/src/hooks/useSessionRecords.ts` | `sessionRecordKeys.aplicacoes(...)`; `useAplicacoesDoAgendamento()` (fetch imperativo) |
| `frontend/src/lib/protocolo.ts` | `ROTULO_DO_CAMPO` já existe; nada |
| `frontend/src/lib/aplicacoes.ts` (+test) | **novas** `pendenciasDoRegistro`, `Pendencia`, `chaveDaPendencia` |
| `frontend/src/lib/prontuario.ts` | `paraPayload` descarta `protocol_area_name` |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` (+test) | `escolheSessao` chama o backend; `submete` valida e destaca; remove `nomeDoProtocolo`/`vazia` |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx` (+test) | prop `pendencias`; subtítulo do protocolo; select de método com `aria-invalid` |
| `frontend/src/pages/documentos/components/ParametrosDoMetodo.tsx` (+test) | prop `pendentes: Set<string>`; input com `aria-invalid` e borda vermelha |
| `scheduler/tests/integration/051-registro-de-sessao.md` | **novo** roteiro |

Sem migration.

---

## 3. Backend

### 3.1 `protocolo_laser.py`

```python
ROTULO_DO_CAMPO = {"fluence_j": "Fluência (J)", "energy_kj": "Energia (kJ)",
                   "stacks": "Stacks", "passes": "Passadas"}

def nome_da_area(chave: Optional[str]) -> Optional[str]:
    """O nome do protocolo para a chave: a primeira linha de PROTOCOLO com ela.
    É subtítulo, nunca substitui o nome comercial (PRD 051)."""
    for linha in PROTOCOLO:
        if linha[2] == chave:
            return linha[3]
    return None
```

(Conferir os índices da tupla em `_shr/_stack/_hr`: `(pele, metodo, chave, nome, ...)`.)

### 3.2 `historico_de_sessao.py`

**`aplicacoes_do_agendamento`**: cada item ganha `"protocol_area_name": nome_da_area(chave)`. `area_name` continua `asa.area_name` (comercial). Nada mais muda.

**`valida_aplicacoes`** (substitui o miolo):

```python
metodo = ap.get("method") or None
if not metodo:
    raise RegistroInvalido(f"{nome}: escolha o método.")
campos = campos_do_metodo(metodo)
if not campos:
    raise RegistroInvalido(f"Método desconhecido: {metodo!r}")
valores = {}
for campo in CAMPOS_NUMERICOS:
    bruto = _num(ap.get(campo))
    if campo in campos:
        if bruto is None:
            raise RegistroInvalido(f"{nome}: informe {ROTULO_DO_CAMPO[campo]}.")
        if bruto <= 0:
            raise RegistroInvalido(f"{nome}: {ROTULO_DO_CAMPO[campo]} precisa ser maior que zero.")
    elif bruto is not None:
        logger.info(...)  # descarte, como hoje
        bruto = None
    valores[campo] = bruto
```

`protocol_area_name` **não** é gravado (não há coluna): a função o ignora.

**Nova**:

```python
def exige_aplicacoes(aplicacoes: List[Dict]) -> List[Dict]:
    if not aplicacoes:
        raise RegistroInvalido("Informe ao menos uma área aplicada.")
    return aplicacoes
```

### 3.3 `session_applications.py` (novo)

```python
def handler(event, context):
    identidade, erro = require_acesso(event, "prontuario.ler")
    clinic_id, appointment_id = extract_path_param(...)
    db = PostgresService()
    linhas = db.execute_query(
        "SELECT patient_id FROM scheduler.appointments WHERE id = %s::uuid AND clinic_id = %s",
        (appointment_id, clinic_id))
    if not linhas: return 404 "Agendamento nao encontrado"
    pele = tipo_de_pele(db, str(linhas[0]["patient_id"])) if linhas[0].get("patient_id") else None
    return 200 para_o_staff(identidade, {"status": "SUCCESS",
        "applications": [serializa(a) for a in aplicacoes_do_agendamento(db, appointment_id, pele)]})
```

Não confere status (cancelado/falta): isso continua no `POST`, que é quem grava. `interface.yml`: função `SessionApplications`, `path: clinics/{clinicId}/appointments/{appointmentId}/session-applications`, `method: get`, mesmo bloco de cors/authorizer dos vizinhos.

### 3.4 `create.py`

- Troca o bloco `if "applications" in body / elif appointment_id / else` por:
  ```python
  if "applications" not in body:
      return http_response(400, {"status": "ERROR", "message": "Informe applications: as áreas aplicadas e seus parâmetros"})
  aplicacoes = exige_aplicacoes(valida_aplicacoes(_do_corpo(body["applications"])))
  ```
- `aplicacoes_do_agendamento` sai do import. `pele` continua lida para `skin_type_snapshot`.

### 3.5 `update.py`

```python
if "applications" in body:
    grava_aplicacoes(db, record_id, exige_aplicacoes(valida_aplicacoes(_do_corpo(body["applications"]))))
```

### 3.6 Costeleta (investigação, primeira tarefa)

Consultas em prod, só leitura, registradas no roteiro:

```sql
-- áreas ativas sem mapa, por clínica
SELECT a.clinic_id, a.name FROM scheduler.areas a
LEFT JOIN scheduler.area_protocol_map m ON m.area_id = a.id
WHERE a.active AND m.id IS NULL ORDER BY 1, 2;
-- a Costeleta nas duas tabelas
SELECT a.id, a.clinic_id, a.name, a.active, m.protocol_area_key
FROM scheduler.areas a LEFT JOIN scheduler.area_protocol_map m ON m.area_id = a.id
WHERE a.name ILIKE '%costel%';
```

Se faltar grafia, acrescentar ao `MAPA_DE_AREAS` e rodar o seed (`setup_database.py`, idempotente) em dev e prod. Se a área estiver inativa, é dado da clínica (reativar pelo painel), não código. Com o caminho único pelo backend, área sem mapa continua entrando (com nome e sem sugestão), então "sumir" deixa de ser possível por grafia.

---

## 4. Frontend

### 4.1 Tipos e service

```ts
export interface AplicacaoDeSessao { ...; /** Subtítulo: nome do protocolo de referência. Não vai ao payload. */ protocol_area_name?: string | null }
export interface AplicacoesDoAgendamento { applications: AplicacaoDeSessao[] }
```

`sessionRecords.service.ts`:
```ts
aplicacoesDoAgendamento(clinicId: string, appointmentId: string) {
  return api.get<AplicacoesDoAgendamento>(`/clinics/${clinicId}/appointments/${appointmentId}/session-applications`).then((r) => r.data.applications)
}
```

`useSessionRecords.ts`: `sessionRecordKeys.aplicacoes = (clinicId, appointmentId) => [...all, 'aplicacoes', clinicId, appointmentId]` e

```ts
/** Fetch imperativo: é chamado de um evento (escolher a sessão), não de render. */
export function useAplicacoesDoAgendamento() {
  const { clinicId } = useAuth(); const qc = useQueryClient()
  return (appointmentId: string) => qc.fetchQuery({
    queryKey: sessionRecordKeys.aplicacoes(clinicId!, appointmentId),
    queryFn: () => sessionRecordsService.aplicacoesDoAgendamento(clinicId!, appointmentId),
    staleTime: 60_000,
  })
}
```

`lib/prontuario.ts` `paraPayload`: não copia `protocol_area_name` (listar campos explicitamente, como já faz).

### 4.2 `lib/aplicacoes.ts`: pendências

```ts
export interface Pendencia { indice: number; area_name: string; campo: 'method' | string; mensagem: string }
export const chaveDaPendencia = (p: Pick<Pendencia, 'indice' | 'campo'>) => `${p.indice}|${p.campo}`

/** Espelho de `valida_aplicacoes`: mesma ordem, mesmas mensagens. Lista vazia -> uma pendência geral (indice -1). */
export function pendenciasDoRegistro(aplicacoes: readonly AplicacaoDeSessao[]): Pendencia[] {
  if (aplicacoes.length === 0) return [{ indice: -1, area_name: '', campo: 'method', mensagem: 'Informe ao menos uma área aplicada.' }]
  const out: Pendencia[] = []
  aplicacoes.forEach((a, i) => {
    if (!a.method) { out.push({ indice: i, area_name: a.area_name, campo: 'method', mensagem: `${a.area_name}: escolha o método.` }); return }
    for (const campo of CAMPOS_POR_METODO[a.method]) {
      const v = a[campo as keyof AplicacaoDeSessao] as number | null
      if (v === null || v === undefined) out.push({ indice: i, area_name: a.area_name, campo, mensagem: `${a.area_name}: informe ${ROTULO_DO_CAMPO[campo]}.` })
      else if (v <= 0) out.push({ ..., mensagem: `${a.area_name}: ${ROTULO_DO_CAMPO[campo]} precisa ser maior que zero.` })
    }
  })
  return out
}
```

Os índices são da lista **normalizada** (`normaliza(aplicacoes)`), que é a que a tela indexa.

### 4.3 `RegistroDeSessaoModal.tsx`

- Remove `nomeDoProtocolo`, `vazia`, os imports `metodosDaArea`, `sugestao`, e a prop `areas` deixa de ser usada para casar nomes (continua indo ao `AplicacoesField` para "+ Adicionar área").
- Estado novo: `const [montando, setMontando] = useState(false)`, `const [tentouSalvar, setTentouSalvar] = useState(false)`.
- `escolheSessao`:
  ```ts
  const buscaAplicacoes = useAplicacoesDoAgendamento()
  const escolheSessao = async (id: string | null) => {
    setAppointmentId(id)
    const sessao = sessaoPorId(id)
    if (!sessao) return
    setSessionDate(sessao.appointment_date)
    setMontando(true)
    try { setAplicacoes(await buscaAplicacoes(id!)) }
    catch { setErro('Não foi possível carregar as áreas do agendamento. Adicione-as manualmente.'); setAplicacoes([]) }
    finally { setMontando(false) }
  }
  ```
  A pré-seleção (`if (!preselecionada && padrao)`) deixa de esperar `protocolo`: só precisa de `padrao`. Chamar `void escolheSessao(padrao.id)`.
- `pendencias = tentouSalvar ? pendenciasDoRegistro(normaliza(aplicacoes)) : []` (derivado, recalcula a cada edição depois da primeira tentativa).
- `submete`: depois da data,
  ```ts
  const faltam = pendenciasDoRegistro(normaliza(aplicacoes))
  if (faltam.length) { setTentouSalvar(true); setErro(faltam.length === 1 ? faltam[0].mensagem : `Faltam ${faltam.length} campos. Preencha os destacados ou remova a área que não foi aplicada.`); return }
  ```
- `AplicacoesField` recebe `pendencias={pendencias}` e `disabled={salvando || montando}`; enquanto `montando`, um texto "Carregando áreas do agendamento…" no lugar da lista vazia.

### 4.4 `AplicacoesField.tsx`

- Prop nova `pendencias: Pendencia[]`; `const pendentes = new Set(pendencias.map(chaveDaPendencia))`.
- Cabeçalho do bloco: abaixo do `area_name`, quando `bloco.linhas[0].protocol_area_name && protocol_area_name !== area_name`: `<span className="text-xs text-gray-400">parâmetros de {protocol_area_name}</span>`. Sem chave: mantém "sem parâmetro sugerido".
- Select de método: `aria-invalid={pendentes.has(chaveDaPendencia({indice, campo: 'method'}))}` e classe `border-red-400 ring-2 ring-red-500/20` quando inválido.
- `ParametrosDoMetodo` recebe `pendentes` filtrado para a linha: `new Set(pendencias.filter(p => p.indice === indice).map(p => p.campo))`.
- `adiciona(nome, areaId, chave)`: `protocol_area_name: parametros.find(p => p.protocol_area_key === chave)?.protocol_area_name ?? null`. Nome comercial preservado (já era).

### 4.5 `ParametrosDoMetodo.tsx`

Prop `pendentes?: Set<string>`. No input: `aria-invalid={pendentes?.has(campo)}` e, quando inválido, `className={CAMPO_NUMERICO + ' border-red-400 ring-2 ring-red-500/20'}`. Abaixo do grupo, quando há pendente, `<span className="text-[11px] text-red-500">obrigatório</span>`.

### 4.6 Textos

- Erro geral (um): a própria mensagem da pendência.
- Erro geral (vários): "Faltam N campos. Preencha os destacados ou remova a área que não foi aplicada."
- Mensagens do backend chegam pelo `erro` como hoje (mesmo texto, por construção).

---

## 5. Testes

### Backend
- `test_historico_de_sessao.py`:
  - `TestONascimentoDoRegistro`: cada caso confere `protocol_area_name` ("Meia perna" para `meia_perna`, `None` sem mapa); **novo** `test_perna_completa_mantem_o_nome_comercial`.
  - `TestValidacao`: `test_aplicacao_sem_metodo_e_valida` → vira `test_aplicacao_sem_metodo_e_recusada` ("Axilas: escolha o método."); **novos** `test_shr_sem_energia_e_recusado` ("Axilas: informe Energia (kJ)."), `test_stacking_sem_passadas_e_recusado`, `test_campo_fora_do_metodo_continua_descartado`, `test_zero_cita_a_area_e_o_campo`; `test_lista_vazia` → `exige_aplicacoes([])` levanta; `test_agendamento_sem_area` segue (a montagem pode devolver vazio; quem recusa é `exige_aplicacoes`).
  - Guarda: `grep` do fonte de `create.py` não contém `aplicacoes_do_agendamento` (o fallback não volta).
- `test_session_applications.py` (novo): 404 fora da clínica; 200 com `protocol_area_name` e nome comercial; composta vira duas; `tipo_de_pele` chamado com o `patient_id` do agendamento.
- `create.py`/`update.py`: corpo sem `applications` → 400; `applications: []` → 400 (teste de handler nos moldes de `test_tolerancia_de_sobreposicao._chama`).

### Frontend
- `aplicacoes.test.ts`: `pendenciasDoRegistro` nos cinco caminhos (vazio, sem método, SHR sem energia, Stacking sem passadas, valor zero, tudo certo → `[]`); índices da lista normalizada.
- `RegistroDeSessaoModal.test.tsx`: mock de `sessionRecordsService.aplicacoesDoAgendamento`; escolher a sessão mostra "Perna Completa" com subtítulo "parâmetros de Meia perna"; salvar com Energia vazia não chama `mutateAsync`, mostra a mensagem e marca `aria-invalid`; preencher libera; falha do GET mostra o aviso e deixa adicionar manualmente. Os testes atuais de composta ("vira duas") passam a vir do mock.
- `AplicacoesField.test.tsx`: subtítulo aparece só quando difere do nome; select inválido com pendência.
- `ParametrosDoMetodo.test.tsx`: input pendente com `aria-invalid`.

---

## 6. Ordem

1. `protocolo_laser.nome_da_area`/`ROTULO_DO_CAMPO`; `historico_de_sessao` (montagem + validação + `exige_aplicacoes`); testes.
2. Handler novo + `interface.yml`; `create.py`/`update.py`; testes de handler. `pytest tests/unit`.
3. Front: tipos, service, hook, `pendenciasDoRegistro` + teste.
4. `ParametrosDoMetodo`, `AplicacoesField`, modal; testes. `vitest`, `build`, `lint`.
5. Deploy dev; curl do endpoint novo (rota nova demora a propagar: conferir antes do smoke); consultas da Costeleta em prod (leitura); roteiro no painel apontando para dev com um agendamento de "Perna Completa" + "Costeleta".
6. Prod só com o André.

---

## 7. Roteiro (dev) - esqueleto

| # | Chamada | Esperado |
|---|---|---|
| 1 | `GET .../appointments/{A}/session-applications` (A com Perna Completa, Costeleta, Virilha Completa + ânus) | 200; 4 aplicações: "Perna Completa"/`meia_perna`/"Meia perna"/SHR com sugestão; "Costeleta"/`costeleta`/método null; "Virilha Completa + ânus" ×2 (`virilha_completa` SHR, `regiao_perianal` Stacking) |
| 2 | mesmo GET com id de outra clínica | 404 |
| 3 | `POST session-records` sem `applications` | 400 |
| 4 | `POST` com `applications: []` | 400 "ao menos uma área" |
| 5 | `POST` com Costeleta sem método | 400 "Costeleta: escolha o método." |
| 6 | `POST` com SHR e `energy_kj` vazio | 400 "...: informe Energia (kJ)." |
| 7 | `POST` completo | 201; `area_name` = "Perna Completa" |
| 8 | `PUT` com `applications: []` | 400 |
| 9 | Painel: escolher a sessão → blocos com subtítulo; Salvar com campo vazio → destaque + mensagem; "Remover" na Costeleta → salva | ok |
