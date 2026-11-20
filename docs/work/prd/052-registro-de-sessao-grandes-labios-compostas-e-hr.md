# PRD - 052 Registro de sessão: Grandes lábios, compostas desmembradas e Energia fixa no HR (evolução)

> Gerado na fase **Research**. Use como input para a fase Spec. Decisões da §4 confirmadas pelo André em 19/11/2026 (a 5 alterada: sem trava).
> Par do PRD 051 (bugs do mesmo fluxo). Depende dele: a montagem das áreas tem de estar num lugar só antes de mudar a regra de montagem.
> Fora dos dois PRDs, por decisão do André em 19/11: alterar áreas e recalcular descontos durante o atendimento.

---

## 1. Objetivo

Fazer o registro técnico refletir o que de fato se aplica na sala, sem tocar nas áreas e valores comerciais do agendamento:

1. **Compostas desmembradas** no registro: "Virilha Completa + ânus" vira "Virilha completa" e "Perianal", cada uma com método e parâmetros próprios.
2. **"Interno da virilha" passa a se chamar "Grandes lábios"**, mesma chave e mesmos parâmetros.
3. **Virilha cavada ou completa agendada traz "Grandes lábios" automaticamente** como segunda área do registro, logo abaixo da virilha, configurável à parte.
4. **HR pré-preenche Energia (kJ) = 1 sempre** ao ser escolhido; o campo continua editável (decisão do André em 19/11: sem trava).

---

## 2. Contexto (o que o código faz hoje)

- **Compostas já viram duas aplicações.** `MAPA_DE_AREAS` tem `"Virilha Completa + ânus": ("virilha_completa", "regiao_perianal")` e as duas pontas (`aplicacoes_do_agendamento` e `escolheSessao`) expandem pela tabela `area_protocol_map`. O que falta é só o nome: a segunda metade aparece como "Região perianal" (nome do protocolo) e o pedido é "Perianal". Com o PRD 051, o nome comercial da composta volta a ser mostrado, então o desmembramento precisa de um nome próprio por parte: é o `protocol_area_name` de cada chave.
- **"Interno da virilha"** existe em três lugares: `protocol_area_name` da chave `interno_virilha` ("Interno da virilha (lábios)" no SHR e "(reforço)" no Stacking e HR), `AREAS_PADRAO` do front (`'Interno de Virilha'`, PRD 030) e o comentário do anexo do PRD 012. A chave fica; o nome muda.
- **Virilha cavada/completa** mapeiam hoje para uma chave só. Acrescentar `interno_virilha` como segunda chave dessas áreas no `MAPA_DE_AREAS` faz as duas pontas gerarem a segunda linha, na ordem do `display_order`. "Virilha Completa + ânus" passa a três chaves: virilha, lábios, perianal.
- **HR:** `METODOS["HR"]` pede fluência e energia; o protocolo grava energia 1.0 em toda linha HR (`_hr`), mas o campo é editável e o backend aceita qualquer número positivo.
- **Seed do mapa** (`_seed_do_mapa`) é `ON CONFLICT DO NOTHING`: linhas novas entram ao rodar o setup; linhas antigas não saem. O `protocol_area_name` muda pelo seed do protocolo (`ON CONFLICT DO UPDATE`).

---

## 3. Escopo

### Dentro do escopo

**A. Nomes do protocolo**
- `regiao_perianal`: `protocol_area_name` → "Perianal".
- `interno_virilha`: todas as linhas (SHR, Stacking, HR) → "Grandes lábios". `AREAS_PADRAO` do front → `{ nome: 'Grandes lábios', protocol_area_key: 'interno_virilha' }`.
- Registros antigos não mudam (`area_name` é snapshot, por desenho do PRD 012).

**B. Desmembramento com nome por parte**
- Quando a área do agendamento tem **mais de uma chave** no mapa, cada aplicação recebe como `area_name` o `protocol_area_name` da chave ("Virilha completa", "Grandes lábios", "Perianal") e guarda o nome comercial de origem em campo novo `source_area_name` para o histórico mostrar "de: Virilha Completa + ânus".
- Quando a área tem **uma chave**, vale a regra do PRD 051: nome comercial, protocolo como subtítulo.
- A regra mora em `aplicacoes_do_agendamento` (uma função só, depois do 051). A tela só exibe.

**C. Grandes lábios automático**
- `MAPA_DE_AREAS`: `"Virilha Cavada": ("virilha_cavada", "interno_virilha")`, `"Virilha Completa": ("virilha_completa", "interno_virilha")`, `"Virilha Completa + ânus": ("virilha_completa", "interno_virilha", "regiao_perianal")`. "Virilha Simples" e "1/2 Virilha" não mudam.
- Ordem: `display_order` garante virilha → lábios → perianal, um bloco abaixo do outro.
- "Grandes lábios" tem três métodos no protocolo, então entra **sem método escolhido** (regra "um só, já escolhe" do PRD 012) e o PRD 051 obriga a escolher ou remover antes de salvar. A profissional que não aplicou nos lábios remove a linha.
- Seed do mapa em dev e prod (linhas novas); teste `test_mapa_de_areas` atualizado (a virilha deixa de ser "uma chave").

**D. HR com Energia pré-preenchida**
- Frontend: ao escolher HR (`trocaMetodo`), Energia recebe 1 **sempre**, inclusive sem tipo de pele ou sem sugestão para a área; o campo continua editável e entra na validação do 051 como qualquer outro (vazio bloqueia).
- Constante `ENERGIA_DO_HR = 1` em `lib/protocolo.ts`, espelho de `protocolo_laser._hr` (que já grava 1.0 em toda linha HR). Backend não força nem valida o valor além de "maior que zero".

**E. Comercial intocado**
- `appointment_service_areas`, preços e descontos do agendamento não mudam. Teste de guarda: o fluxo de registro não escreve em `appointments` nem em `appointment_service_areas` (varredura de SQL nos módulos do prontuário).

### Fora do escopo
- Cadastrar "Grandes lábios" como área vendável no catálogo (não é vendida à parte; continua área padrão do registro).
- Alterar áreas e descontos durante o atendimento (decisão do André).
- Mudar parâmetros do protocolo além dos nomes.
- Backfill de registros antigos.

---

## 4. Decisões (confirmadas pelo André em 19/11/2026)

| # | Decisão | Alternativa descartada |
|---|---|---|
| 1 | Desmembramento pelo `MAPA_DE_AREAS` + `area_protocol_map` (mecanismo existente) | Tabela nova de "áreas técnicas derivadas": é o mesmo conceito com outro nome |
| 2 | Nome por parte só quando a área tem mais de uma chave; uma chave mantém o comercial (051) | Sempre o nome do protocolo: recria o bug "Meia perna" |
| 3 | `source_area_name` novo para rastrear a origem comercial da parte | Não guardar: o histórico perde "isto veio de Virilha Completa + ânus" |
| 4 | Grandes lábios entra sem método (três métodos no protocolo) | Pré-escolher SHR: decidir conduta pela profissional, contra o PRD 012 |
| 5 | HR pré-preenche Energia = 1 na tela, editável, sem trava e sem forçar no backend (**decisão do André, 19/11**) | Forçar 1.0 no backend e travar o campo: proposta original, derrubada |
| 6 | Virilha Simples e 1/2 Virilha ficam sem lábios automáticos | Incluir: o pedido cita só cavada e completa |

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/protocolo_laser.py` | modificar | nomes "Perianal" e "Grandes lábios"; `MAPA_DE_AREAS` da virilha |
| `scheduler/src/services/historico_de_sessao.py` | modificar | nome por parte + `source_area_name` em `aplicacoes_do_agendamento` |
| `scheduler/src/scripts/setup_database.py` | modificar | `patient_session_applications.source_area_name VARCHAR(160)` (migration + CREATE TABLE); seed já propaga nomes e linhas novas |
| `scheduler/src/functions/patient_record/_comum.py` | modificar | grava/serializa `source_area_name` |
| `scheduler/tests/unit/test_mapa_de_areas.py`, `test_protocolo_laser.py`, `test_historico_de_sessao.py` | modificar | virilha com duas/três chaves; nomes; `source_area_name` |
| `scheduler/tests/unit/test_prontuario_nao_toca_o_comercial.py` | criar | guarda: módulos do prontuário não escrevem em `appointments`/`appointment_service_areas` |
| `frontend/src/lib/protocolo.ts` (+test) | modificar | `AREAS_PADRAO` → Grandes lábios; `ENERGIA_DO_HR` |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx` (`trocaMetodo`) (+test) | modificar | HR pré-preenche Energia = 1 sempre, editável |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx` (+test) | modificar | subtítulo "de: {source_area_name}" nas partes desmembradas |
| `frontend/src/lib/prontuario.ts` | modificar | resumo do histórico mostra a origem |
| `frontend/src/types/index.ts` | modificar | `source_area_name` |
| `scheduler/tests/integration/052-registro-de-sessao-evolucao.md` | criar | roteiro |

---

## 6. Dependências e riscos

- **Depende do PRD 051** (montagem num lugar só). Implementar depois, na mesma sequência dev → prod.
- Migration pequena (`source_area_name`), idempotente; seeds do protocolo e do mapa rodam no mesmo setup, em dev e prod.
- **Risco de ruído**: toda virilha cavada/completa passa a trazer uma linha a mais que a profissional precisa resolver (método ou remover). É o pedido; o roteiro confere que remover é um clique.
- Registros antigos com "Interno da virilha (lábios)" no `area_name` ficam assim; o histórico continua legível.

---

## 7. Critérios de aceite

- [ ] Agendamento "Virilha Completa + ânus" → registro com três blocos, nesta ordem: "Virilha completa" (SHR, sugerido), "Grandes lábios" (sem método), "Perianal" (Stacking, sugerido); cada um com "de: Virilha Completa + ânus".
- [ ] Agendamento "Virilha Cavada" → dois blocos: "Virilha Cavada" (nome comercial, subtítulo do protocolo) e "Grandes lábios".
- [ ] "Virilha Simples" → um bloco.
- [ ] "+ Adicionar área" oferece "Grandes lábios"; "Interno de Virilha" não aparece mais.
- [ ] Escolher HR → Energia mostra 1 (mesmo sem pele ou sem sugestão), editável; apagar e salvar bloqueia pela regra do 051; `POST` com `energy_kj: 3` grava 3.
- [ ] `laser_protocol_parameters` em dev e prod: `interno_virilha` → "Grandes lábios" nas três linhas; `regiao_perianal` → "Perianal".
- [ ] Agendamento de origem inalterado (áreas, `original_price_cents`, `final_price_cents`, `discount_pct`) após salvar o registro: conferido por `GET appointments` antes e depois.
- [ ] `pytest tests/unit`, `vitest`, `build`, `lint` verdes; roteiro em dev registrado.

---

## 8. Referências

- `scheduler/src/services/protocolo_laser.py`, `historico_de_sessao.py`, `setup_database._seed_do_mapa`
- `docs/work/prd/012-anexo-mapa-areas-protocolo.md` (unificação de "lábios" e "reforço" em `interno_virilha`)
- PRD 030 (Interno de Virilha como área padrão), PRD 051 (bugs; pré-requisito)

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/052-registro-de-sessao-grandes-labios-compostas-e-hr.md` (19/11/2026)
- [ ] Implementado em dev: (data)
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
