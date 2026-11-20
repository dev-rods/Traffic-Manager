# PRD - 051 Registro de sessão: áreas com o nome certo e nenhum registro incompleto (bugs)

> Gerado na fase **Research**. Use como input para a fase Spec. Decisões da §4 confirmadas pelo André em 19/11/2026.
> Par do PRD 052 (evolução do mesmo fluxo). Este é o de **correção**: sobe primeiro, em dev e depois prod.
> Fora dos dois PRDs, por decisão do André em 19/11: alterar áreas e recalcular descontos durante o atendimento.

---

## 1. Objetivo

Corrigir dois defeitos do fluxo "Registrar sessão" (prontuário técnico do laser):

1. **Áreas importadas com o nome errado ou ausentes.** "Perna Completa" aparece como "Meia perna", "Braço Completo" como "Meio braço", e áreas agendadas (relato: Costeleta) não entram no registro.
2. **Registros em branco ou parciais salvam.** Hoje nenhum parâmetro é obrigatório: uma área sem método, ou com Fluência preenchida e Energia vazia, grava e vira "sem parâmetro registrado" no histórico.

---

## 2. Contexto (o que o código faz hoje)

### 2.1 Dois caminhos montam as áreas, e divergem

- **Backend** `historico_de_sessao.aplicacoes_do_agendamento` (L67-112): lê `appointment_service_areas` com `LEFT JOIN area_protocol_map`, uma aplicação por chave do protocolo, e **mantém o nome comercial** (`asa.area_name`). Só roda quando o corpo do `POST session-records` vem sem `applications`, o que a tela nunca faz.
- **Frontend** `RegistroDeSessaoModal.escolheSessao` (L111-150): faz a mesma expansão no navegador, mas **troca o nome comercial pelo nome da primeira linha do protocolo com aquela chave** (`nomeDoProtocolo(chave) ?? nome`).

É essa troca que produz o relato. O mapa (`protocolo_laser.MAPA_DE_AREAS`) liga de propósito "Perna Completa" e "Pernas Completas" a `meia_perna`, e "Braço Completo" a `meio_braco`, porque o PDF do protocolo só tem parâmetros para a metade e a área inteira herda (teste `test_mapa_de_areas`: "área inteira herda a metade"). O mapa está certo para **parâmetros**; errado é a tela renomear a área tratada. O registro gravado em `patient_session_applications.area_name` passa a dizer "Meia perna" numa sessão que depilou a perna inteira.

### 2.2 Costeleta e outras áreas que somem

Não reproduzido ainda (fica como primeira tarefa da implementação). O caminho do front tem três pontos onde uma área agendada pode cair fora ou entrar vazia:

- `sessao.areas` é um `string_agg(asa.area_name, ', ')` (`patient_record/list.py` L77-92) que a tela separa por vírgula. Nome de área com vírgula quebra em dois.
- `areas.find((a) => a.name === nome)` casa com o catálogo da clínica (`useClinicAreas`) por igualdade exata. Área inativa ou renomeada não casa, e cai em `vazia(...)` sem chave.
- `protocolo.area_map` (`GET laser-protocol`) só traz ligações de áreas **ativas** da clínica. A Costeleta tem dois métodos (Stacking e HR), então entra com método em branco; se a área estiver inativa no catálogo da Essência ou grafada diferente ("Costeletas"), entra sem chave e sem sugestão. Se ainda assim sumir da tela, o defeito é outro e a reprodução vai mostrar.

O seed do mapa (`setup_database._seed_do_mapa`) casa por nome exato e só roda no setup: área criada ou renomeada no painel depois disso fica sem mapa até o próximo setup.

### 2.3 Validação

`historico_de_sessao.valida_aplicacoes` (L115-162) exige só `area_name`. Método é opcional; sem método, todos os números viram NULL. Campos vazios do método escolhido viram NULL sem erro. A tela (`RegistroDeSessaoModal.submete`) só exige a data. Resultado: o registro de uma sessão inteira pode ir para o banco sem nenhum parâmetro, e o histórico mostra "sem parâmetro registrado".

---

## 3. Escopo

### Dentro do escopo

**A. Nome da área e fonte única da montagem**
- A área tratada no registro guarda o **nome comercial do agendamento** ("Perna Completa"); o protocolo de referência aparece ao lado, como subtítulo ("parâmetros de Meia perna"), não no lugar do nome.
- A montagem das aplicações a partir do agendamento passa a ter **um lugar só**: o backend. Endpoint novo `GET clinics/{clinicId}/appointments/{appointmentId}/session-applications` devolve o que `aplicacoes_do_agendamento` já monta (nome comercial, chave, método quando único, sugestão pela pele). A tela chama esse endpoint ao escolher a sessão e apaga `escolheSessao`/`nomeDoProtocolo`.
- O backend passa a ler as áreas pelo `area_id` do `appointment_service_areas` (já faz), então grafia e vírgula deixam de importar.
- Mapa: conferir em prod, por consulta, toda área ativa das duas clínicas sem linha em `area_protocol_map`; para as que faltarem por grafia, acrescentar a grafia ao `MAPA_DE_AREAS` e rodar o seed. Registrar o resultado no roteiro.

**B. Nenhum registro incompleto**
- Backend (`valida_aplicacoes`): toda aplicação exige `method`; e exige **todos** os campos do método (`METODOS[method]`: SHR e HR → fluência e energia; Stacking → fluência, stacks, passadas). Registro sem nenhuma aplicação é 400. Mensagem nomeia a área e o campo: `"Costeleta: informe Energia (kJ)"`.
- Frontend: ao salvar, cada campo pendente fica destacado (borda e texto em vermelho, `aria-invalid`), com a lista dos pendentes acima do botão, e o pedido não sai. Enquanto se edita, nada bloqueia (mesma lição do PRD 050: a obrigação é do submit).
- Quem não aplicou numa área a remove ("Remover"), em vez de deixá-la em branco.
- `update.py` passa pela mesma validação quando o corpo traz `applications`.
- Registros antigos incompletos continuam legíveis; só não se grava mais um novo (nem edição que deixe pendente).

### Fora do escopo
- Desmembrar compostas, "Grandes lábios", auto-inclusão de lábios na virilha e Energia fixa do HR: **PRD 052**.
- Alterar áreas do agendamento e recalcular desconto durante o atendimento: decisão do André, fora.
- Faixas numéricas (teto de fluência, stacks 2-5 no backend): não pedido.
- Editar o protocolo pelo painel.

---

## 4. Decisões (confirmadas pelo André em 19/11/2026)

| # | Decisão | Alternativa descartada |
|---|---|---|
| 1 | Nome comercial no registro, protocolo como subtítulo | Criar linhas "Perna completa"/"Braço completo" no protocolo com os parâmetros da metade: duplica dado e mente sobre a origem (PDF só tem a metade) |
| 2 | Montagem só no backend, por endpoint novo | Corrigir o `escolheSessao` e manter os dois caminhos: foi a divergência que gerou este bug |
| 3 | Método obrigatório por área | Permitir área sem método como "não aplicado": é o que deixa o registro parcial passar; remover a área é explícito |
| 4 | Validação dura no backend + destaque no front | Só no front: o Postman e qualquer outro cliente continuariam gravando em branco |

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/historico_de_sessao.py` | modificar | `valida_aplicacoes` exige método e campos do método; mensagem com área e campo; `aplicacoes_do_agendamento` ganha `protocol_area_name` na saída |
| `scheduler/src/functions/patient_record/session_applications.py` | criar | `GET .../appointments/{id}/session-applications` (`prontuario.ler`), 404 se o agendamento não é da clínica |
| `scheduler/sls/functions/patient_record/interface.yml` | modificar | rota nova |
| `scheduler/src/functions/patient_record/create.py`, `update.py` | modificar | 400 quando `applications` vazio; `update` valida |
| `scheduler/src/services/protocolo_laser.py` | modificar | grafias que faltarem no `MAPA_DE_AREAS` (após conferência em prod) |
| `scheduler/tests/unit/test_historico_de_sessao.py` | modificar | `TestValidacao`: sem método → 400; campo faltando → 400 com área e campo; registro vazio → 400 |
| `scheduler/tests/unit/test_session_applications.py` | criar | endpoint: nome comercial preservado, composta vira duas, 404 fora da clínica |
| `frontend/src/services/sessionRecords.service.ts`, `hooks/useSessionRecords.ts` | modificar | `aplicacoesDoAgendamento(appointmentId)` |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` (+test) | modificar | `escolheSessao` chama o endpoint; `submete` valida e destaca; remove `nomeDoProtocolo` |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx`, `ParametrosDoMetodo.tsx` (+tests) | modificar | subtítulo com o protocolo; `pendentes` destacados |
| `frontend/src/lib/aplicacoes.ts` (+test) | modificar | `pendenciasDoRegistro(aplicacoes): Pendencia[]` (fonte única da regra no front, espelho de `METODOS`) |
| `frontend/src/types/index.ts` | modificar | `AplicacaoDeSessao.protocol_area_name?` |
| `scheduler/tests/integration/051-registro-de-sessao.md` | criar | roteiro curl e smoke do painel |

---

## 6. Dependências e riscos

- Sem migration. O seed do mapa pode precisar rodar em prod se faltar grafia (idempotente, `ON CONFLICT DO NOTHING`).
- **Risco de bloquear a recepção**: a validação dura recusa o que hoje passa. A tela precisa deixar claro o que falta e oferecer "Remover" para a área não aplicada. Testar com uma sessão real em dev antes de prod.
- **Risco do endpoint novo**: rota nova no API Gateway demora a propagar (lição do PRD 039). Conferir em dev por curl antes do smoke no painel.
- Registros antigos com `area_name` do protocolo ("Meia perna") ficam como estão; não há backfill (não dá para saber se a sessão foi da perna inteira).

---

## 7. Critérios de aceite

- [ ] Agendamento com "Perna Completa" e "Braço Completo" → registro mostra e grava "Perna Completa" e "Braço Completo", com subtítulo "parâmetros de Meia perna" / "Meio braço" e a sugestão da metade.
- [ ] Agendamento com Costeleta → a área entra no registro (reprodução feita e causa registrada no roteiro).
- [ ] Toda área ativa das duas clínicas em prod tem linha em `area_protocol_map` (consulta no roteiro).
- [ ] `POST session-records` com `applications: []` → 400. Aplicação sem `method` → 400 "{área}: escolha o método". SHR com energia vazia → 400 "{área}: informe Energia (kJ)". Stacking sem passadas → 400.
- [ ] `PUT session-records/{id}` com aplicação incompleta → 400.
- [ ] Painel: Salvar com campo vazio destaca o campo, lista as pendências e não chama a API; preencher ou "Remover" a área libera.
- [ ] Composta "Virilha Completa + ânus" continua virando duas aplicações (teste existente segue verde).
- [ ] `pytest tests/unit`, `vitest`, `build`, `lint` verdes; roteiro em dev registrado.

---

## 8. Referências

- `scheduler/src/services/protocolo_laser.py` (`MAPA_DE_AREAS`, `METODOS`), `historico_de_sessao.py`
- `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx`, `AplicacoesField.tsx`, `ParametrosDoMetodo.tsx`
- PRD 012 (+ anexo do mapa), PRD 030 (vários métodos por área), PRD 042 (registrar pela agenda)
- PRD 052 (evolução do mesmo fluxo)

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/051-registro-de-sessao-areas-certas-e-sem-registro-incompleto.md` (19/11/2026)
- [x] Implementado em dev: 19/11/2026 (PR #218, layer 200; roteiro curl verde; Costeleta investigada em prod: mapa ok, perda era do caminho antigo da tela)
- [x] Implementado em prod: 19/11/2026 (deploy layer 158; painel pela Vercel no merge do #218; smoke de leitura do endpoint novo com a sessão real de 19/11: 8 aplicações, Costeleta incluída)
- [x] Registrado em `TASKS_LOG.md`
