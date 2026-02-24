# PRD — 007 Coleta de Nome Completo no Agendamento

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Adicionar um passo no fluxo de agendamento via WhatsApp para coletar o nome completo do cliente após a seleção de horário. O nome deve ser gravado diretamente na tabela `appointments` como coluna `full_name`, proporcionando identificação clara ao consultar a agenda — sem alterar a lógica de pacientes (o telefone continua como chave primária do `patients`).

---

## 2. Contexto

Atualmente, ao visualizar a agenda de agendamentos, a única referência ao cliente é o `patient_id` (que mapeia para um telefone). Isso dificulta a identificação rápida de quem é o cliente ao olhar a lista de appointments. Ter o nome completo diretamente no registro do agendamento resolve esse problema sem alterar a estrutura de pacientes.

O nome **não** precisa ser propagado para a tabela `patients` porque o número de telefone é uma chave mais forte e confiável do que um nome digitado.

---

## 3. Escopo

### Dentro do escopo

1. **Novo estado `ASK_FULL_NAME`** no fluxo de conversa — entre `SELECT_TIME` e `CONFIRM_BOOKING`
2. **Coluna `full_name`** na tabela `scheduler.appointments` (VARCHAR 255, nullable)
3. **Exibição do nome** no resumo de confirmação (`CONFIRM_BOOKING`)
4. **Passagem do nome** pelos 3 pontos de entrada de criação de appointment:
   - `conversation_engine.py` (fluxo WhatsApp)
   - `appointment/create.py` (API REST)
   - `sheets/webhook.py` (Google Sheets)
5. **Inclusão do nome** na sincronização com Google Sheets

### Fora do escopo

- Alteração na tabela `patients`
- Validação avançada do nome (CPF, documento, etc.)
- Alteração no fluxo de reagendamento ou cancelamento
- Mudanças no engine de disponibilidade

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/conversation_engine.py` | modificar | Novo estado `ASK_FULL_NAME`, transições, handler, salvar na session |
| `scheduler/src/services/appointment_service.py` | modificar | Receber `full_name` e incluir no INSERT |
| `scheduler/src/scripts/setup_database.py` | modificar | Migration: `ADD COLUMN full_name`; atualizar CREATE TABLE |
| `scheduler/src/functions/appointment/create.py` | modificar | Aceitar `fullName` no body da API REST |
| `scheduler/src/functions/sheets/webhook.py` | modificar | Aceitar `full_name` vindo da planilha |
| `scheduler/src/services/sheets_sync.py` | modificar | Incluir `full_name` na exportação para Google Sheets |

---

## 5. Dependências e riscos

- **Dependências:** Nenhuma externa. Apenas alterações internas no conversation engine, appointment service e schema do banco.
- **Riscos:**
  - Migration é idempotente (`ADD COLUMN IF NOT EXISTS`), sem breaking change
  - Coluna nullable — appointments existentes continuam funcionando sem nome
  - Input de texto livre (nome) pode conter dados inesperados — sanitizar para evitar injection

---

## 6. Critérios de aceite

- [ ] Após selecionar horário, o bot pergunta o nome completo do cliente
- [ ] O nome digitado é salvo em `session["full_name"]`
- [ ] O resumo de confirmação (`CONFIRM_BOOKING`) exibe o nome do cliente
- [ ] A coluna `full_name` existe na tabela `scheduler.appointments`
- [ ] O INSERT em `appointment_service.create_appointment()` inclui `full_name`
- [ ] A API REST (`POST /appointments`) aceita `fullName` no body
- [ ] O Google Sheets sync exporta `full_name`
- [ ] Appointments criados sem nome (via API sem o campo) funcionam normalmente (nullable)
- [ ] Fluxo WhatsApp testado end-to-end sem regressões

---

## 7. Referências

- `CLAUDE.md` (padrões do projeto)
- `scheduler/src/services/conversation_engine.py` (fluxo de estados atual)
- `scheduler/src/services/appointment_service.py` (criação de appointments)
- `scheduler/src/scripts/setup_database.py` (schema do banco)

---

## Status (preencher após conclusão)

- [x] Pendente
- [x] Spec gerada: `spec/007-appointment-full-name.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
