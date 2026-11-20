# Spec - 052 Registro de sessão: Grandes lábios, compostas desmembradas e Energia pré-preenchida no HR

> Gerada em 19/11/2026 a partir de `prd/052-registro-de-sessao-grandes-labios-compostas-e-hr.md`. Decisões da §4 confirmadas pelo André em 19/11 (a 5 alterada: HR pré-preenche sem trava). Pré-requisito: PRD 051 em prod (layer 158, 19/11).
> Fluxo: código → PR → migration dev + seeds → deploy dev → roteiro → prod com o André.

---

## 1. O que muda, em três frases

Três renomes no protocolo (`regiao_perianal` → "Perianal"; `interno_virilha` → "Grandes lábios" nas três linhas; área padrão da tela → "Grandes lábios") e duas chaves a mais no mapa (Virilha Cavada e Virilha Completa ganham `interno_virilha`; a composta passa a três). A montagem do backend, que desde o 051 é a única, passa a dar **nome por parte** quando a área comercial tem mais de uma chave, guardando a origem em `source_area_name` (coluna nova). Na tela, escolher HR pré-preenche Energia = 1 sempre, editável.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/protocolo_laser.py` | nomes "Perianal" e "Grandes lábios"; `MAPA_DE_AREAS` da virilha; `ENERGIA_DO_HR` |
| `scheduler/src/services/historico_de_sessao.py` | `aplicacoes_do_agendamento`: nome por parte + `source_area_name`; `valida_aplicacoes` passa `source_area_name` |
| `scheduler/src/scripts/setup_database.py` | migration `source_area_name VARCHAR(160)` + `CREATE TABLE`; seeds já propagam |
| `scheduler/src/functions/patient_record/_comum.py` | `grava_aplicacoes` insere `source_area_name` |
| `scheduler/src/functions/patient_record/create.py` | `_do_corpo` lê `sourceAreaName` |
| `scheduler/tests/unit/test_mapa_de_areas.py`, `test_protocolo_laser.py`, `test_historico_de_sessao.py`, `test_session_applications.py` | ajustes e casos novos |
| `scheduler/tests/unit/test_prontuario_nao_toca_o_comercial.py` | **novo** (guarda) |
| `frontend/src/types/index.ts` | `AplicacaoDeSessao.source_area_name?`; `AplicacaoPayload.sourceAreaName` |
| `frontend/src/lib/protocolo.ts` (+test) | `AREAS_PADRAO` → Grandes lábios; `ENERGIA_DO_HR`; **nova** `parametrosIniciais` |
| `frontend/src/lib/aplicacoes.ts` | `adicionaMetodo` usa `parametrosIniciais`; `BlocoDeArea.source_area_name` |
| `frontend/src/lib/prontuario.ts` | `paraPayload` manda `sourceAreaName` |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx` (+test) | `trocaMetodo`/`adiciona` usam `parametrosIniciais`; subtítulo "de: {origem}" |
| `frontend/src/pages/documentos/components/HistoricoDeSessao.tsx` | mostra a origem no histórico |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.test.tsx` | dublê do backend com nome por parte |
| `scheduler/tests/integration/052-registro-de-sessao-evolucao.md` | **novo** roteiro |

---

## 3. Backend

### 3.1 `protocolo_laser.py`

- Linhas 114/130: `"Interno da virilha (lábios)"` → `"Grandes lábios"`. Linhas 150/164/190/200: `"Interno da virilha (reforço)"` → `"Grandes lábios"`. Linhas 149/163: `"Região perianal"` → `"Perianal"`. Ajustar o comentário do módulo (L22) e o do anexo do PRD 012 se citar o nome.
- `ENERGIA_DO_HR = 1.0`; `_hr` passa a usar a constante no lugar do literal.
- `MAPA_DE_AREAS`:
  ```python
  "Virilha Cavada": ("virilha_cavada", "interno_virilha"),
  "Virilha Completa": ("virilha_completa", "interno_virilha"),
  "Virilha Completa + ânus": ("virilha_completa", "interno_virilha", "regiao_perianal"),
  ```
  "Virilha Simples" e "1/2 Virilha" inalteradas (decisão 6).

### 3.2 `historico_de_sessao.aplicacoes_do_agendamento`

Agrupar as linhas do SQL por `area_id` antes de emitir (a consulta já vem ordenada por `created_at, display_order`):

```python
por_area = {}  # area_id -> [linhas], preservando a ordem de chegada
...
for area_id, linhas in por_area.items():
    desmembrada = len([l for l in linhas if l.get("protocol_area_key")]) > 1
    for linha in linhas:
        chave = linha.get("protocol_area_key")
        nome_comercial = linha["area_name"]
        nome_do_protocolo = nome_da_area(chave)
        saida.append({
            ...,
            # Parte de uma composta leva o nome do protocolo e guarda a origem
            # (PRD 052). Área de uma chave só mantém o comercial (PRD 051).
            "area_name": nome_do_protocolo if (desmembrada and nome_do_protocolo) else nome_comercial,
            "source_area_name": nome_comercial if desmembrada else None,
            "protocol_area_name": nome_do_protocolo,
            ...
        })
```

Resultado para "Virilha Completa + ânus": `Virilha completa` (SHR) → `Grandes lábios` (sem método, três no protocolo) → `Perianal` (Stacking), todos com `source_area_name = "Virilha Completa + ânus"`. Para "Virilha Cavada": `Virilha cavada` (SHR) e `Grandes lábios`, ambos com origem "Virilha Cavada". Para "Perna Completa": `Perna Completa`, origem `None`, subtítulo "Meia perna" (como no 051).

Observação: o subtítulo do 051 (`protocol_area_name !== area_name`) deixa de aparecer nas partes desmembradas, porque o nome já é o do protocolo; aparece "de: {origem}" no lugar (§4.3).

### 3.3 `valida_aplicacoes`

Passa adiante `"source_area_name": (ap.get("source_area_name") or "").strip()[:160] or None`.

### 3.4 `_comum.grava_aplicacoes` e `create._do_corpo`

- INSERT ganha a coluna `source_area_name` e o parâmetro `ap.get("source_area_name")`.
- `_do_corpo`: `"source_area_name": a.get("sourceAreaName")`.
- `serializa`/`SELECT *` já devolvem a coluna nova.

### 3.5 `setup_database.py`

- `CREATE TABLE scheduler.patient_session_applications`: `source_area_name VARCHAR(160),` logo após `area_name`, com comentário "PRD 052: área comercial de origem quando esta linha é parte de uma composta".
- `MIGRATIONS`: `"ALTER TABLE scheduler.patient_session_applications ADD COLUMN IF NOT EXISTS source_area_name VARCHAR(160)"`.
- Seeds: `_seed_do_protocolo` (`ON CONFLICT DO UPDATE`) renomeia; `_seed_do_mapa` (`ON CONFLICT DO NOTHING`) acrescenta as linhas novas da virilha. Nada a mudar no código dos seeds.

### 3.6 Guarda: `test_prontuario_nao_toca_o_comercial.py` (novo)

Varre `src/functions/patient_record/*.py` e `src/services/historico_de_sessao.py`: nenhum `UPDATE`/`INSERT`/`DELETE` em `scheduler.appointments` ou `scheduler.appointment_service_areas` (regex sobre o fonte, case-insensitive). Prova positiva: o mesmo regex encontra escrita em `appointment_service.py`.

---

## 4. Frontend

### 4.1 Tipos e payload

- `AplicacaoDeSessao.source_area_name?: string | null`.
- `AplicacaoPayload.sourceAreaName: string | null`; `paraPayload` copia `a.source_area_name ?? null`.
- `BlocoDeArea.source_area_name: string | null` (do primeiro item do bloco).

### 4.2 `lib/protocolo.ts`

- `AREAS_PADRAO = [{ nome: 'Grandes lábios', protocol_area_key: 'interno_virilha' }]`; comentário atualizado.
- `export const ENERGIA_DO_HR = 1`.
- **Nova**, a única porta para "o que a linha começa com" ao escolher um método:
  ```ts
  /** Sugestão do protocolo e, no HR, Energia = 1 sempre (PRD 052): mesmo sem pele ou sem linha para a área. Editável. */
  export function parametrosIniciais(parametros, chave, metodo, skinType): Pick<AplicacaoDeSessao, 'fluence_j' | 'energy_kj' | 'stacks' | 'passes'> {
    const s = sugestao(parametros, chave, metodo, skinType)
    return {
      fluence_j: s?.fluence_j ?? null,
      energy_kj: metodo === 'HR' ? (s?.energy_kj ?? ENERGIA_DO_HR) : (s?.energy_kj ?? null),
      stacks: s?.stacks ?? null,
      passes: s?.passes ?? null,
    }
  }
  ```
- Usada em `AplicacoesField.trocaMetodo`, `AplicacoesField.adiciona` e `lib/aplicacoes.adicionaMetodo` (as três hoje repetem o `s?.x ?? null`).

### 4.3 `AplicacoesField.tsx`

- Cabeçalho do bloco: se `bloco.source_area_name && bloco.source_area_name !== bloco.area_name` → `<span className="text-xs text-gray-400">de: {source_area_name}</span>`; senão vale o subtítulo do 051.
- `aria-label` do Remover: `Remover ${area_name}` (as partes agora têm nomes distintos; o sufixo do 051 segue só para quem tem subtítulo de protocolo).
- `adiciona` (área manual) grava `source_area_name: null`.

### 4.4 `HistoricoDeSessao.tsx`

No `<dt>`: `{bloco.area_name}` e, quando há origem diferente, `<span className="ml-1 text-xs text-gray-400">(de {bloco.source_area_name})</span>`.

### 4.5 Modal

Sem mudança de lógica; o dublê do teste passa a montar nome por parte com origem.

---

## 5. Testes

### Backend
- `test_mapa_de_areas.py`: `test_virilha_completa_mais_anus_abre_em_duas` → três chaves na ordem; novo `test_virilha_cavada_e_completa_trazem_grandes_labios`; `Virilha Simples` e `1/2 Virilha` continuam com uma.
- `test_protocolo_laser.py`: nomes "Grandes lábios" (3 linhas) e "Perianal" (2); `ENERGIA_DO_HR` usada por toda linha HR; totais de linhas inalterados.
- `test_historico_de_sessao.py`: composta → três aplicações com nomes por parte e `source_area_name`; Virilha Cavada → duas; Perna Completa → origem `None` e nome comercial; `valida_aplicacoes` passa `source_area_name`.
- `test_session_applications.py`: o caso da composta passa a esperar `Virilha completa`/`Grandes lábios`/`Perianal` com origem.
- `test_prontuario_nao_toca_o_comercial.py` (novo).

### Frontend
- `protocolo.test.ts`: `parametrosIniciais` no HR sem pele → `energy_kj: 1`; com linha → o da linha; SHR sem pele → `null`; `AREAS_PADRAO` é Grandes lábios.
- `AplicacoesField.test.tsx`: escolher HR preenche Energia 1 mesmo sem sugestão, e o campo aceita apagar/editar; "Grandes lábios" na busca, "Interno de Virilha" não; bloco com origem mostra "de: ...".
- `RegistroDeSessaoModal.test.tsx`: dublê com nome por parte; composta mostra três blocos com "de: Virilha Completa + ânus".
- `aplicacoes.test.ts`: `adicionaMetodo` em HR traz Energia 1.

---

## 6. Ordem

1. `protocolo_laser.py` (nomes, mapa, constante) + testes do protocolo e do mapa.
2. `historico_de_sessao.py`, `_comum.py`, `create._do_corpo`, `setup_database.py` + testes + guarda. `pytest tests/unit`.
3. Front: tipos, `protocolo.ts`, `aplicacoes.ts`, `prontuario.ts`, `AplicacoesField`, `HistoricoDeSessao` + testes. `vitest`, `build`, `lint`.
4. Dev: `setup_database.py` com `/dev/SUPABASE_DB_*` (migration + seeds), `serverless deploy --stage dev`, roteiro.
5. Prod com o André: `setup_database.py` com `/prod/SUPABASE_DB_*` (renomeia as 5 linhas do protocolo e cria 3 ligações do mapa por clínica que tenha as áreas), deploy.

---

## 7. Roteiro (dev) - esqueleto

| # | Chamada | Esperado |
|---|---|---|
| 1 | SQL: `SELECT protocol_area_key, protocol_area_name FROM scheduler.laser_protocol_parameters WHERE protocol_area_key IN ('interno_virilha','regiao_perianal')` | "Grandes lábios" ×3, "Perianal" ×2 |
| 2 | SQL: ligações de `Virilha Cavada`, `Virilha Completa`, `Virilha Completa + ânus` em `area_protocol_map` | 2, 2 e 3 chaves, `interno_virilha` com `display_order` entre a virilha e o perianal |
| 3 | `GET session-applications` de agendamento com Virilha Completa + ânus e Perna Completa | `Virilha completa` (SHR), `Grandes lábios` (null), `Perianal` (Stacking), todos com `source_area_name`; `Perna Completa` sem origem |
| 4 | `GET` de agendamento com Virilha Cavada | 2 aplicações, origem "Virilha Cavada" |
| 5 | `GET` de agendamento com Virilha Simples | 1 aplicação |
| 6 | `POST session-records` com `sourceAreaName` | 201; coluna gravada; `GET` lista devolve |
| 7 | `GET appointments/{A}` antes e depois do POST | áreas, preços e desconto iguais |
| 8 | Painel: HR em qualquer área → Energia 1 preenchida e editável; apagar e Salvar → pendência do 051; "+ Adicionar área" → "Grandes lábios" aparece | ok |
