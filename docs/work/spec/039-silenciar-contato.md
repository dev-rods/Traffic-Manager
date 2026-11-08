# Spec - 039 Silenciar o bot para um contato, sem prazo

> Gerada em 08/11/2026 a partir de `docs/work/prd/039-silenciar-contato.md`
> (decisões de §4.1 e §4.2 tomadas pelo André em 08/11/2026).

---

## 0. O desenho em uma tela

O silêncio é um **registro no Postgres**, não um estado da sessão. Ele é lido
por quem já lê o banco antes de decidir, e entra em `atendimento` como
**argumento explícito** - a função continua pura e sem I/O.

```
  painel  --POST /attendant/mute-->  scheduler.contatos_silenciados  (fonte única)
                                              |
                      +-----------------------+-----------------------+
                      v                       v                       v
                 webhook                 outbound                retomada /
            (alguém escreveu)         (fila de envio)         conversation_resume
                      |                       |                       |
                      +---- silenciado=True --+-----------------------+
                                              v
                        atendimento.pode_responder / pode_iniciar / motivo_da_pausa
                                   (1a porta, antes de todas)
```

**Por que argumento e não campo de sessão:** `session_store.grava_atendimento`,
quando a sessão ainda não existe, grava o dict inteiro
(`put_item(Item=session)`). Um campo injetado viraria cópia persistida de um
dado cujo dono é o Postgres, livre para divergir em silêncio. O PRD foi
corrigido nesse ponto (§6).

---

## 1. Ordem de implementação

1. Migration (tabela).
2. `src/services/silencio.py` (serviço novo, dono do registro).
3. `src/services/atendimento.py` (a porta nova).
4. Call sites do backend (6).
5. Endpoints `mute` / `unmute` + leitura nos handlers do painel.
6. Lista de pacientes (selo no cadastro).
7. Frontend.
8. Testes.
9. Dev -> conferência -> prod.

Cada passo é verificável sozinho. Os passos 1 a 4 já produzem o comportamento
(sem jeito de ligar pela interface); o 5 liga.

---

## 2. Backend

### 2.1 Migration

`scheduler/src/scripts/setup_database.py` - em `TABLES` (tabela nova, não é
`ALTER`):

```sql
CREATE TABLE IF NOT EXISTS scheduler.contatos_silenciados (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
    phone VARCHAR(20) NOT NULL,
    motivo TEXT NOT NULL,
    silenciado_por VARCHAR(120) NOT NULL,
    silenciado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reativado_por VARCHAR(120),
    reativado_em TIMESTAMPTZ
)
```

E o índice que faz a unicidade valer só para o silêncio **vivo** - mesmo
padrão de `uq_patient_consents_em_andamento` (PRD 036):

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_contatos_silenciados_ativo
    ON scheduler.contatos_silenciados (clinic_id, phone)
    WHERE reativado_em IS NULL
```

O histórico fica: silenciar, reativar e silenciar de novo gera três linhas, e
`reativado_em IS NULL` é sempre no máximo uma. Nada é apagado - a auditoria é
metade do motivo de a tabela existir (PRD §6, razão 3).

### 2.2 `src/services/silencio.py` (novo)

Dono do registro. Faz I/O, e só ele.

| Função | O que faz |
|---|---|
| `esta_silenciado(clinic_id, phone, db=None) -> bool` | uma linha viva existe? |
| `silenciados_da_clinica(clinic_id, db=None) -> set[str]` | todos os telefones vivos, para as listas do painel |
| `detalhe(clinic_id, phone, db=None) -> dict \| None` | `{motivo, silenciado_por, silenciado_em}`, para o cabeçalho |
| `silencia(clinic_id, phone, motivo, por, db=None) -> dict` | insere; já silenciado é idempotente (devolve o vigente, não duplica) |
| `reativa(clinic_id, phone, por, db=None) -> bool` | marca `reativado_*` na linha viva; devolve se havia o que reativar |

Regras:

- `phone` sempre por `normalize_phone` na entrada de **toda** função. É o
  mesmo telefone em três formatos no banco se isso escorregar.
- `motivo` obrigatório, `strip()`, 3 a 500 caracteres. Vazio é `ValueError`:
  silenciar sem motivo é o que produz o número esquecido (PRD §5).
- `esta_silenciado` falha **fechado para o silêncio**: erro de banco devolve
  `False` e o bot responde. O contrário (erro -> tudo mudo) calaria todas as
  clínicas numa instabilidade do Postgres. Loga `warning`.

### 2.3 `src/services/atendimento.py`

Vocabulário novo, ao lado dos existentes:

```python
PAUSA_SILENCIADO = "muted"
```

Assinatura das três funções ganha um keyword-only com default:

```python
def pode_responder(clinic, session, phone, agora=None, *, silenciado=False) -> bool:
    if silenciado:
        return False          # 1a porta: vence bot_paused, pessoa e política
    ...

def pode_iniciar(clinic, session, phone, agora=None, *, transacional=False,
                 silenciado=False) -> bool:
    # repassa a pode_responder; `transacional=True` NÃO pula o silêncio
    ...

def motivo_da_pausa(clinic, session, phone, agora=None, *, silenciado=False):
    if silenciado:
        return PAUSA_SILENCIADO   # antes de attendant e clinic_paused
    ...
```

`default=False` é deliberado: todo chamador que não souber do silêncio
continua funcionando como hoje, e o teste de §4 garante que não sobrou
chamador esquecido.

O comentário da decisão 9.1 (linha ~79) passa a dizer que a exceção existe,
onde ela mora e por quê - senão o módulo afirma uma regra que ele já não tem.

### 2.4 Os seis call sites

| Arquivo | Linha (hoje) | O que muda |
|---|---|---|
| `functions/webhook/handler.py` | 419 | já tem `clinic` e banco: `silenciado=silencio.esta_silenciado(clinic_id, phone)` |
| `functions/outbound/processor.py` | 169 | idem, no laço de envio |
| `services/retomada.py` | 146 | recebe `clinic`; consulta e repassa (`transacional=True` não isenta) |
| `services/conversation_resume.py` | 101 | idem |
| `services/elegibilidade_do_bot.py` | 89 | `por_que_nao_pode` ganha o motivo `silenciado`, com texto em `motivo_legivel` |
| `functions/attendant/handler.py` | 261, 267 | `_handle_status` passa a refletir o silêncio |

Listas do painel (consulta em lote, nunca uma query por telefone):

| Arquivo | O que muda |
|---|---|
| `functions/attendant/conversations.py` (~115) | `mudos = silencio.silenciados_da_clinica(clinic_id)` e `silenciado=phone in mudos` |
| `functions/attendant/list_active.py` (~102) | idem |

O lembrete (`functions/reminder/processor.py`) **não muda**: ele não chama
`pode_iniciar` hoje, e por decisão §4.1 continua entregando o lembrete a
número silenciado. O que fica calado é a resposta - e isso já sai de graça,
porque a resposta entra pelo webhook, que agora consulta o silêncio.

### 2.5 Endpoints

Em `functions/attendant/handler.py`, ao lado de `activate`/`deactivate`, e em
`sls/functions/attendant/interface.yml` (duas rotas `http` novas; **nenhuma
mudança de IAM** - as credenciais do Postgres chegam por variável de ambiente
do `provider`, não por role):

```
POST /attendant/mute     {clinic_id, phone, motivo}  -> 200 {status, silenciado_em}
POST /attendant/unmute   {clinic_id, phone}          -> 200 {status}
```

- `motivo` ausente ou curto: 400 com mensagem em português.
- `mute` de quem já está silenciado: 200, idempotente.
- `unmute` de quem não está: 200 com `message` dizendo que não havia silêncio
  (o botão não pode dar erro por corrida entre duas recepcionistas).
- Autor: a mesma identidade de quem pausa hoje (`para_o_staff` / `identidade`).
  Sem identidade utilizável, `"painel"`.
- `mute` **não** mexe na sessão. São estados independentes: o contato pode
  estar silenciado e com atendente ao mesmo tempo, e o selo mostra `muted`
  porque é o estado mais forte (PRD §4.2).
- `unmute` também não retoma o bot por si: se havia pausa de 24 h, ela segue
  valendo até vencer. Reativar o bot é o botão que já existe.

### 2.6 Lista de pacientes

`functions/patient/list.py`: o `SELECT` ganha

```sql
EXISTS (SELECT 1 FROM scheduler.contatos_silenciados s
         WHERE s.clinic_id = p.clinic_id AND s.phone = p.phone
           AND s.reativado_em IS NULL) AS silenciado
```

e `_serialize_row` inclui `silenciado` **apenas quando `True`** (decisão
§4.2: quem não está silenciado não ganha campo nem selo). Subconsulta, não
`JOIN`, para não mexer no `GROUP BY` que já é sensível ali.

---

## 3. Frontend

| Arquivo | O que muda |
|---|---|
| `src/types/index.ts` | `PauseReason` ganha `'muted'`; `Patient` ganha `silenciado?: boolean` |
| `src/lib/motivoDaPausa.ts` | `muted` nos três mapas: "Bot silenciado por alguém da clínica" / "Silenciado" / `bg-purple-50 text-purple-700`; filtro `silenciadas` com rótulo "Silenciadas" e cláusula em `passaNoFiltro` |
| `src/services/bot.service.ts` | `silenciar(clinicId, phone, motivo)` e `reativarSilencio(clinicId, phone)` |
| `pages/bot/components/ConversationThread.tsx` | botão "Silenciar bot" (abre modal pedindo o motivo) quando não silenciado; "Reativar bot" quando silenciado; cabeçalho mostra motivo, autor e data |
| `pages/bot/components/ConversationList.tsx` e `FilaDeAtendimento.tsx` | o selo sai de `SELO_DA_PAUSA`, então só precisam do motivo novo chegando |
| `pages/bot/BotPage.tsx` | mutations novas + invalidação das queries de conversa |
| `pages/pacientes/components/PatientsTable.tsx` e `PatientCard.tsx` | selo "Bot silenciado" quando `patient.silenciado` |

O modal de motivo é um `Modal` + `textarea` obrigatório, no padrão dos modais
de `pacientes`. Nada de `window.prompt`.

---

## 4. Testes

**Backend** (`scheduler/tests/unit/`):

- `test_silencio.py`: normalização do telefone, motivo obrigatório,
  idempotência de `silencia`, `reativa` sem silêncio vivo, histórico de três
  linhas com uma só viva, e `esta_silenciado` falhando fechado quando o banco
  estoura (dublê que levanta).
- `test_atendimento_silenciado.py`: `silenciado=True` barra `pode_responder`
  e `pode_iniciar` **inclusive** com `transacional=True`, com `bot_enabled`,
  com campanha viva e com lembrete vivo (os três caminhos de `LEADS_ONLY`);
  `motivo_da_pausa` devolve `muted` à frente de `attendant` e `clinic_paused`.
- `test_silencio_em_todo_chamador.py`: **guarda por AST** - varre `src/` e
  falha se alguma chamada a `pode_responder` / `pode_iniciar` /
  `motivo_da_pausa` fora de `atendimento.py` não passar `silenciado=`. É o que
  impede o próximo chamador de nascer furado. Por AST, não por texto: busca em
  texto casa com docstring.

**Frontend**: caso `muted` em `ConversationList.test.tsx`, filtro novo em
`motivoDaPausa` e selo em `PatientsTable.test.tsx`.

---

## 5. Dev -> prod

1. `python src/scripts/setup_database.py` em dev (migration idempotente).
2. `serverless deploy --stage dev` (deploy completo; `deploy function` quebra
   nas layers).
3. Conferir em dev **pela rota**, não só pelo teste: silenciar um número,
   mandar mensagem por ele e ver o webhook recusar com `muted`; conferir o
   selo no painel e no cadastro; reativar e ver o bot voltar.
4. Mesma sequência em prod, nessa ordem (migration, deploy, conferência).
5. Trocar a pausa de 24 h do contato real da Essência pelo silêncio, e só
   então considerar o PRD entregue.
6. `TASKS_LOG.md` e Status do PRD.

Prod e dev nunca em paralelo.

---

## 6. O que esta spec não faz

- Relatório de "silenciados há muito tempo" (fase 2, PRD §8).
- Silenciar automaticamente por conteúdo da conversa (PRD próprio, com LGPD).
- Bloquear mensagem transacional para número silenciado (decisão §4.1).
