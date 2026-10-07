# PRD — 012 Documentos do paciente: histórico por sessão

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Criar uma área de **Documentos** por paciente no painel, e nela o primeiro
documento: o **histórico por sessão** — o registro do que a profissional fez em
cada atendimento.

Uma linha por sessão, com as áreas aplicadas e o parâmetro usado em cada uma,
mais observações. Fácil de abrir (um clique na lista de pacientes) e fácil de
preencher (as áreas já vêm do agendamento daquele dia).

A pergunta que este documento precisa responder em um clique é: *"que parâmetro
eu usei na virilha da Maria da última vez?"*

E preencher tem de ser quase automático: escolhido o **método**, os parâmetros
iniciais vêm do protocolo da clínica, já ajustados ao **tipo de pele** da
paciente. A profissional confirma ou corrige, em vez de consultar um PDF e
digitar do zero.

---

## 2. Contexto

### O que existe hoje

Nada equivalente. `scheduler.patients` guarda cadastro (nome, telefone, CPF,
nascimento, e-mail, desconto), e `scheduler.appointments` guarda o que foi
**marcado** — data, áreas, preço, duração. Não há nenhum lugar para registrar o
que foi **feito**: a profissional sai da sala e o parâmetro do laser vive na
memória dela ou num caderno.

O que já ajuda: `appointment_service_areas` guarda as áreas de cada agendamento
com o **nome da área congelado** no momento (`area_name`). É desse dado que o
pré-preenchimento vem, e é o mesmo padrão de snapshot que este PRD adota.

### A área de Documentos como pasta, não como tela única

O pedido do André fala em "aba de documentos do paciente", com o prontuário
sendo **o primeiro** tipo. Termo de consentimento assinado (com gov.br) foi
adiado — fora do escopo desta task, e por boas razões: depende de habilitação
junto a terceiro, tem questão jurídica própria (Lei 14.063/2020 separa
assinatura simples, avançada e qualificada) e não pode segurar o histórico.

Mas a **estrutura de navegação** já nasce de pasta: `/pacientes/:id/documentos`
com uma lista de tipos de documento, sendo que hoje só um existe. Assim o
segundo documento entra sem redesenhar a navegação.

### Os três métodos, e por que o parâmetro não pode ser texto livre

Lidos os dois PDFs da clínica (`Documentos Laser/`, 19/09/2026). Eles definem
**três métodos, cada um com um formato de parâmetro diferente**:

| Método | Parâmetros | Movimento |
|---|---|---|
| SHR | Fluência (J) + Energia (kJ) | contínuo, levemente rápido |
| SHR Stacking | Fluência (J) + Stacks (●) + Passadas | pontual ou arraste lento |
| HR | Fluência (J) + Energia (kJ, fixa em 1,0) | pontual, sem sobreposição |

E **dois conjuntos de valores por tipo de pele**: brancas/claras (fototipos I–III)
e morena/negra (IV–VI). A mesma área muda: axilas no SHR são 7 J na pele branca
e 5 J na negra.

Isto derruba a ideia de `parameter` como campo de texto único: o formato depende
do método. As colunas passam a ser `method` + os campos numéricos do método.

As unidades ficam **exatamente como os PDFs escrevem** - `Fluência (J)` e
`Energia (kJ)`. É o rótulo que a profissional lê no material dela, e o prontuário
não pode inventar uma unidade que o protocolo não usa.

### Os nomes das áreas do protocolo NÃO são os do catálogo

O catálogo tem 36 áreas; os protocolos usam outra nomenclatura, e as listas nem
sequer cobrem o mesmo conjunto:

- `1/2 Braço` no catálogo é `Meio braço` no protocolo; `Glúteo` é `Glúteos`;
  `Orelhas` é `Orelha externa`; `Perianal/ânus` é `Região perianal`.
- **Oito áreas do catálogo não têm protocolo nenhum:** `1/2 Coxa`, `1/2 Glúteo`,
  `1/2 Virilha`, `Braço Completo`, `Perna Completa`, `Pernas Completas`,
  `Glabela`, `Nariz`.
- **Quatro áreas do protocolo não são vendidas:** `Interno da virilha (lábios)`,
  `Interno da virilha (reforço)`, `Joelho`, `Cotovelo`.

**A ligação tem de ser tabela explícita, revisada por quem aplica.** Casar por
aproximação de nome é exatamente o defeito de 16/09/2026, em que `Virilha Comp. +
ânus` ficou inalcançável e a paciente respondeu cinco vezes à mesma pergunta. Lá
o erro custou uma conversa constrangedora; aqui custaria **sugerir a fluência de
outra área** num equipamento que queima pele.

Onde não houver ligação, a tela diz *"sem parâmetro sugerido"* e a profissional
digita. Nunca chuta.

### Os avisos de segurança que os PDFs trazem

Dois são categóricos e entram na tela:

> "Nunca utilize o método HR [em pele bronzeada], independentemente do fototipo."
> "Não utilize o método HR no fototipo VI."

Daí a marca de **pele bronzeada por sessão**: é estado que vai e volta, não
atributo de cadastro, e é o que explica no histórico por que a fluência daquele
dia foi mais baixa.

O binário Branca/Negra **não expressa fototipo VI**, onde o HR é proibido, nem o
V, onde o documento manda evitar. A tela mostra o aviso do documento ao escolher
HR em pele negra; **bloquear é decisão clínica**, não do software, e fica com
quem aplica.

### O problema de autoria, declarado e não resolvido

Levantado com o André em 17/09/2026, e a decisão dele foi **seguir sem resolver
agora**.

O login do painel devolve a `SCHEDULER_API_KEY` compartilhada
(`auth/login.py:110`), e `require_api_key` valida só a chave. Nenhuma requisição
carrega quem é o usuário. Consequências que este PRD assume conscientemente:

- **A autoria é declarada, não provada.** A profissional é escolhida num
  dropdown (`scheduler.professionals`), e o backend grava o que a tela mandar.
  Serve para a clínica saber quem atendeu; não serve como prova.
- **O isolamento entre clínicas continua fraco.** Qualquer usuário logado tem a
  mesma chave e pode ler outra clínica trocando o `clinicId`. Isso **já é
  verdade hoje** para agenda e cadastro; com histórico de sessão passa a valer
  para dado de saúde, que a LGPD trata como **dado sensível** (art. 11).

O que este PRD faz a respeito: deixa a porta pronta. A coluna
`created_by_user_id` nasce nullable ao lado do `professional_id`, para quando a
autenticação por usuário chegar ela ser preenchida sem migration de retrabalho.

### Decisões do André (17/09/2026)

| Pergunta | Decisão |
|---|---|
| Como guardar "Aplicações (Padrão de Áreas - Parâmetro)" | **Uma linha por área**, pré-preenchida do agendamento do dia, mas **totalmente editável**: dá para adicionar área, remover e alterar o parâmetro |
| Corrigir uma linha já salva | **Edita normalmente, e o estado anterior fica guardado** numa trilha de auditoria consultável |
| Termo de consentimento / gov.br | **Fora do escopo** por enquanto |
| Autenticação por profissional | Reconhecida como necessária, **não é foco agora** |

Decisões acrescentadas depois da leitura dos protocolos (19/09/2026):

| Pergunta | Decisão |
|---|---|
| Tipo de pele da paciente | **Branca ou Negra**, no cadastro, marcado **só pela profissional**. O bot nunca toca |
| Área composta do catálogo (`Virilha Completa + ânus`) | **Abre em duas linhas** no registro, porque no protocolo são duas áreas com métodos diferentes |
| Tabela de parâmetros dos protocolos | **Uma só, igual para todas as clínicas** |
| Pele bronzeada | **Marca por sessão**, não no cadastro: é estado que vai e volta |
| Navegação | Documentos abre **direto no histórico**, com seletor de documento no topo |
| Atalho pela Agenda | **Incluído**: `Registrar sessão` no popover do agendamento |
| Escolha do método (19/09, pós-deploy) | **Os três, sempre, em qualquer área.** O protocolo sugere o inicial; não restringe. Nem o HR em pele bronzeada é bloqueado |

---

## 3. Escopo

### Dentro do escopo

- Botão **Documentos** por paciente na lista de pacientes.
- Página `/pacientes/:patientId/documentos` abrindo **direto no histórico**, com
  seletor de documento no topo (hoje um item). A pasta existe na estrutura sem
  cobrar um clique que não decide nada.
- Atalho **Registrar sessão** no popover do agendamento, na Agenda: é de onde a
  profissional sai depois de atender, e é o caminho do caso comum.
- **Tipo de pele** (Branca / Negra) no cadastro do paciente, marcado apenas no
  painel. Nenhuma tool do bot lê ou escreve este campo.
- **Tabela de referência dos protocolos**, semeada dos dois PDFs: 3 métodos x 2
  tipos de pele x áreas, com os campos de cada método.
- **Mapa explícito** entre área do catálogo e área do protocolo, incluindo área
  composta que abre em duas (`Virilha Completa + ânus`).
- Ao escolher o método numa aplicação, os parâmetros **vêm preenchidos** do
  protocolo conforme o tipo de pele da paciente - e continuam editáveis.
- Marca de **pele bronzeada** na sessão, com o aviso do documento.
- **Histórico por sessão**: registros do paciente em ordem cronológica
  decrescente, cada um com data, profissional, aplicações (área + parâmetro) e
  observações.
- Criar registro **a partir de um agendamento** do paciente (traz data e áreas
  prontas) ou **do zero** (sessão feita fora do sistema).
- Editar registro, com o estado anterior preservado e consultável.
- Remover registro (soft delete, também registrado na trilha).
- Filtro de agendamentos por paciente na listagem (`patientId`), que o
  pré-preenchimento precisa e hoje não existe.

### Fora do escopo

- **Termo de consentimento e assinatura gov.br.** Projeto separado.
- **Autenticação por usuário / perfis.** Pré-requisito reconhecido, adiado por
  decisão do André. A autoria fica declarada.
- **Exportar PDF do histórico.** Provável próximo passo, mas não pedido.
- **O bot.** Não lê nem escreve histórico de sessão em hipótese alguma.
- **Fototipo I–VI detalhado.** O André pediu binário Branca/Negra. O fototipo
  aparece nos PDFs e fica registrado aqui como limitação conhecida, não como
  campo.
- **Bloquear método por regra clínica.** A tela avisa; quem decide é quem aplica.
- **Foto por sessão.** Comum em estética e muda o desenho (storage, LGPD). Não
  foi pedido.
- **Editar os protocolos pelo painel.** A tabela é semeada por migration. Quando
  a clínica quiser mudar sem deploy, vira task própria.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | 3 tabelas novas + índices, migrations idempotentes |
| `scheduler/src/services/historico_de_sessao.py` | **criar** | Regras do registro: montar a partir do agendamento, validar, gravar a trilha |
| `scheduler/src/functions/patient_record/create.py` | **criar** | `POST /clinics/{clinicId}/patients/{patientId}/session-records` |
| `scheduler/src/functions/patient_record/list.py` | **criar** | `GET` dos registros do paciente, com aplicações |
| `scheduler/src/functions/patient_record/update.py` | **criar** | `PUT` de um registro |
| `scheduler/src/functions/patient_record/delete.py` | **criar** | `DELETE` (soft), registrado na trilha |
| `scheduler/src/functions/patient_record/history.py` | **criar** | `GET` da trilha de auditoria de um registro |
| `scheduler/sls/functions/patient_record.yml` | **criar** | Interface das 5 Lambdas |
| `scheduler/serverless.yml` | modificar | Incluir o arquivo de interface novo |
| `scheduler/src/functions/appointment/list.py` | modificar | Filtro `patientId` |
| `frontend/src/router.tsx` | modificar | Rota `pacientes/:patientId/documentos` |
| `frontend/src/pages/pacientes/components/PatientsTable.tsx` | modificar | Botão Documentos |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | **criar** | A pasta do paciente |
| `frontend/src/pages/documentos/components/HistoricoDeSessao.tsx` | **criar** | A lista de sessões |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` | **criar** | Criar/editar, com as aplicações editáveis |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx` | **criar** | A tabela área+parâmetro, add/remove/editar |
| `frontend/src/pages/documentos/components/HistoricoDeEdicoes.tsx` | **criar** | O painel de "editado" |
| `frontend/src/services/sessionRecords.service.ts` | **criar** | Camada HTTP |
| `frontend/src/hooks/useSessionRecords.ts` | **criar** | Queries e mutations |
| `frontend/src/types/index.ts` | modificar | Tipos do registro, aplicação e trilha |
| `scheduler/tests/unit/test_historico_de_sessao.py` | **criar** | As regras |
| `scheduler/tests/unit/test_trilha_de_auditoria.py` | **criar** | Fiação: nada se perde numa edição |
| `frontend/src/pages/documentos/components/*.test.tsx` | **criar** | Comportamento das telas |
| `scheduler/tests/integration/historico-de-sessao.md` | **criar** | Casos via curl |
| `scheduler/tests/postman/historico-de-sessao.postman_requests.json` | **criar** | Requests |

---

## 5. Modelo de dados (proposto)

Três tabelas. A separação entre registro e aplicações é o que torna o histórico
**consultável** — a pergunta "qual parâmetro na virilha da Maria" vira um
`WHERE`, não leitura de texto corrido.

**`scheduler.patients`** — uma coluna nova

`skin_type` (`BRANCA` / `NEGRA`), nullable, escrita **só pelo painel**. É o que
seleciona qual dos dois protocolos alimenta a sugestão.

**`scheduler.patient_session_records`** — a sessão

| Coluna | Observação |
|---|---|
| `id`, `clinic_id`, `patient_id` | chaves |
| `tanned_skin` | `BOOLEAN DEFAULT FALSE`. Pele bronzeada **naquela** sessão |
| `skin_type_snapshot` | o tipo de pele usado na sugestão daquele dia. Se a profissional corrigir o cadastro depois, o registro antigo continua dizendo com que protocolo foi feito |
| `appointment_id` | **nullable**: sessão feita fora do sistema não tem agendamento |
| `session_date` | a data do atendimento, não a de digitação |
| `professional_id` | nullable, FK para `professionals`. Autoria **declarada** |
| `notes` | Observações |
| `created_by_user_id` | **nullable, hoje sempre NULL.** Nasce pronta para quando a auth por usuário existir |
| `deleted_at` | soft delete, como em `patients` |
| `version` | lock otimista, mesmo padrão de `appointments` |

**`scheduler.patient_session_applications`** — uma linha por área aplicada

| Coluna | Observação |
|---|---|
| `record_id` | FK, `ON DELETE CASCADE` |
| `area_id` | **nullable**, FK para `areas` |
| `area_name` | **snapshot de texto, sempre preenchido.** Mesmo padrão de `appointment_service_areas.area_name`: renomear a área no catálogo não pode reescrever o passado. É também o que permite digitar área fora do catálogo |
| `protocol_area_key` | nullable. Qual linha do protocolo alimentou a sugestão |
| `method` | nullable. `SHR`, `SHR_STACKING` ou `HR` |
| `fluence_j` | `NUMERIC(5,2)`. Comum aos três métodos |
| `energy_kj` | `NUMERIC(5,2)`, nullable. SHR e HR |
| `stacks` | `SMALLINT`, nullable. Só SHR Stacking |
| `passes` | `SMALLINT`, nullable. Só SHR Stacking |
| `display_order` | a ordem em que ela preencheu |

Colunas explícitas e não um `JSONB` de parâmetros: são três formatos fixos e
conhecidos, e a pergunta que justifica a tabela inteira - *"qual fluência usei"* -
tem de ser um `WHERE`, não um destrinchar de JSON.

**`scheduler.laser_protocol_parameters`** — a referência, semeada dos PDFs

Sem `clinic_id`: uma tabela só, decisão do André. `UNIQUE(skin_type, method,
protocol_area_key)`, e é dela que sai a sugestão. Guarda também
`protocol_area_name` para a tela mostrar o nome do documento.

**`scheduler.area_protocol_map`** — a ligação revisada

`area_id` → `protocol_area_key`, com `display_order`. Uma área pode mapear para
**duas** linhas: `Virilha Completa + ânus` abre em `virilha_completa` (SHR) e
`regiao_perianal` (SHR Stacking). Área sem linha aqui simplesmente não tem
sugestão - e isso é um estado válido, não um erro.

O método padrão é **derivado**: se o `protocol_area_key` tem um único método no
protocolo, vem escolhido; se tem mais de um (`Buço` tem Stacking e HR), fica em
branco para a profissional decidir.

**`scheduler.patient_session_record_audit`** — a trilha

| Coluna | Observação |
|---|---|
| `record_id` | sem FK com cascade: a trilha **sobrevive** ao registro |
| `action` | `CREATE` / `UPDATE` / `DELETE` |
| `snapshot` | `JSONB` com o estado **completo depois** da mudança, aplicações inclusas |
| `changed_at`, `changed_by_name` | quem a tela declarou |

Snapshot completo, e não diff: diff parece econômico e depois não reconstitui
nada sozinho. O registro é pequeno e escrito uma vez por sessão — o volume não
justifica economia.

---

## 6. Dependências e riscos

**Dependências**

- Migration por `setup_database.py` (idempotente), rodada antes do deploy.
- Deploy do backend é manual; a Vercel publica o frontend no merge.
  **Backend primeiro**, senão a tela chama endpoints que não existem.
- Cinco Lambdas novas. `serverless.yml` já esbarrou no limite de 500 recursos
  do CloudFormation uma vez (05/09/2026, resolvido com `versionFunctions:
  false`) — conferir a contagem antes do deploy.

**Riscos**

| Risco | Mitigação |
|---|---|
| **Dado de saúde sob auth fraca** (LGPD art. 11) | Declarado e aceito pelo André nesta task. A porta fica pronta (`created_by_user_id`); a auth por usuário deve vir como task própria, e quanto antes |
| Renomear área no catálogo reescrever o passado | `area_name` é snapshot, como em `appointment_service_areas` |
| Edição perder o que havia antes | Trilha com snapshot completo; teste de fiação dedicado |
| Excluir paciente levar o histórico junto | `patients` é soft delete; o histórico acompanha e a trilha sobrevive de qualquer jeito |
| Profissional preencher a sessão errada | O registro nasce ligado a um agendamento escolhido na tela, com data e áreas visíveis antes de salvar |
| A tabela de aplicações virar trabalho chato | O caso comum é 100% pré-preenchido — ela confere e salva |
| **Sugerir o parâmetro de outra área** por casamento de nome | O mapa é tabela explícita e revisada; sem linha no mapa, a tela diz "sem parâmetro sugerido" e não inventa |
| Protocolo mudar e reescrever o passado | A aplicação guarda os **valores**, não uma referência ao protocolo. Mudar a tabela de referência não altera nenhum registro já feito |
| HR sugerido onde o documento proíbe | Marca de bronzeada tira o HR das sugestões; pele negra mostra o aviso do fototipo VI. A decisão continua com quem aplica |
| `skin_type` vazado para o bot | O campo não entra em nenhuma tool, nem no prompt. Teste de superfície de tools cobre isso |

---

## 7. Critérios de aceite

- [ ] Botão **Documentos** em cada paciente abre `/pacientes/:id/documentos`.
- [ ] A página mostra o paciente e a lista de tipos de documento, com
      **Histórico por sessão** disponível e espaço claro para os próximos.
- [ ] Criar registro a partir de um agendamento traz **data e áreas prontas**; a
      profissional só completa os parâmetros.
- [ ] Dá para **adicionar** área fora do agendamento, **remover** e **editar**
      área e parâmetro antes de salvar.
- [ ] Criar registro **sem** agendamento funciona (sessão feita fora).
- [ ] O histórico lista em ordem decrescente, com área e parâmetro visíveis sem
      abrir nada.
- [ ] Editar marca a linha como **editado**, e o painel mostra o que havia antes,
      quando mudou e quem declarou.
- [ ] Excluir some da lista e **permanece na trilha**.
- [ ] Renomear a área no catálogo **não** muda o que está escrito no histórico.
- [ ] Os 4 estados (carregando, erro, vazio, sucesso) tratados; o vazio ensina o
      que fazer.
- [ ] Marcar o tipo de pele da paciente muda o parâmetro sugerido: axilas no SHR
      sugerem **7 J / 8 kJ** na branca e **5 J / 7 kJ** na negra.
- [ ] Escolher **SHR Stacking** troca os campos para Fluência + Stacks + Passadas.
- [ ] Área composta `Virilha Completa + ânus` nasce como **duas** linhas, com
      métodos diferentes.
- [ ] Área sem mapa (`Nariz`, `Glabela`) aparece com *"sem parâmetro sugerido"* e
      deixa digitar.
- [ ] Marcar **pele bronzeada** mostra o aviso e tira o HR das sugestões.
- [ ] Alterar a tabela de protocolos **não** muda nenhum registro já gravado.
- [ ] `Registrar sessão` no popover da Agenda abre o modal já preenchido.
- [ ] Nenhuma tool do bot lê ou escreve estas tabelas **nem o `skin_type`**.
- [ ] `pytest`, `npm run build`, `npm run lint` e `npm run test` verdes.

---

## 8. Referências

- `CLAUDE.md` e `frontend/CLAUDE.md` (princípios Impeccable para a tela nova)
- `scheduler/src/services/appointment_service.py` — padrão de snapshot de
  `area_name` e de lock otimista
- `scheduler/src/functions/auth/login.py:110` — o token compartilhado
- `scheduler/src/functions/patient/delete.py` — padrão de soft delete
- PRD `008-patient-soft-delete.md` — precedente de coluna nova em `patients`

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/012-documentos-do-paciente-historico-de-sessao.md` (19/09/2026)
- [x] Implementado em: 19/09/2026
- [x] Registrado em `TASKS_LOG.md`
