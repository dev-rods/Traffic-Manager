# PRD — 006 UX Improvements v1 (Feedback Colaborador)

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Implementar 10 melhorias de UX no fluxo de agendamento WhatsApp, coletadas em sessão de feedback com colaborador. As melhorias abrangem: mensagem de boas-vindas, formatação de texto, tabela de preços, skip de etapas desnecessárias, exibição de informações contextuais, opção de falar com atendente, formato de datas e parametrização de tempo máximo de sessão.

---

## 2. Contexto

Feedback direto de usuário/colaborador que testou o fluxo completo de agendamento. Os pontos identificados melhoram clareza, reduzem atrito e adicionam proteções legais ao processo de booking.

---

## 3. Escopo

### Dentro do escopo

1. **Endereço na boas-vindas** — Incluir endereço da clínica na mensagem de welcome
2. **Negrito nas dúvidas (FAQ)** — Formatar perguntas do FAQ com `*bold*` (WhatsApp markdown)
3. **Remover duração da tabela de preços** — Não exibir `(Xmin)` na listagem de serviços/áreas
4. **Skip de serviço quando há apenas 1** — Pular etapa SELECT_SERVICES e ir direto para áreas
5. **Remover preço na seleção de serviço** — Na lista de serviços, mostrar só o nome (sem `R$`)
6. **Manter preço na seleção de áreas** — Na lista de áreas, continuar exibindo preço
7. **"Falar com atendente" a partir da escolha de áreas** — Adicionar botão/opção em SELECT_AREAS e estados seguintes
8. **Dia da semana nos dias disponíveis** — Formato: `DD/MM/YYYY (segunda-feira)` em vez de só `DD/MM/YYYY`
9. **Parametrizar tempo máximo de soma de áreas** — Config na clínica `max_session_minutes` (default 60), validar ao selecionar áreas
10. **Mensagem de recomendações finais com confirmação** — No estado BOOKED, enviar mensagem com instruções pré-sessão e pedir confirmação de leitura (proteção jurídica)

### Fora do escopo

- Mudanças no engine de disponibilidade
- Novos canais de comunicação
- Dashboard administrativo
- Mudanças na integração Google Sheets

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/conversation_engine.py` | modificar | Items 1-10: fluxo de conversa, mensagens, lógica de skip, validação |
| `scheduler/src/services/template_service.py` | modificar | Templates WELCOME_NEW, WELCOME_RETURNING, BOOKED, novo template RECOMMENDATIONS |
| `scheduler/src/scripts/setup_database.py` | modificar | Adicionar coluna `max_session_minutes` na tabela clinics |
| `scheduler/src/scripts/seed_clinic.py` | modificar | Seed do novo campo e instruções pré-sessão |

---

## 5. Dependências e riscos

- **Dependências:** Nenhuma externa. Apenas alterações no conversation engine e templates.
- **Riscos:**
  - Migration do campo `max_session_minutes` (idempotente, sem breaking change)
  - Mudança no fluxo de estados (skip de serviço) requer teste cuidadoso
  - "Falar com atendente" precisa definir mecanismo (notificar owner? encaminhar mensagem?)

---

## 6. Critérios de aceite

- [ ] Mensagem de boas-vindas inclui endereço da clínica
- [ ] Perguntas do FAQ aparecem em negrito no WhatsApp
- [ ] Tabela de preços NÃO exibe duração
- [ ] Com 1 serviço ativo, fluxo pula direto para seleção de áreas
- [ ] Lista de serviços não mostra preço; lista de áreas mantém preço
- [ ] Opção "Falar com atendente" disponível a partir de SELECT_AREAS
- [ ] Dias disponíveis mostram dia da semana (ex: `21/02/2026 (sábado)`)
- [ ] Campo `max_session_minutes` existe na tabela clinics (default 60)
- [ ] Soma de duração das áreas validada contra `max_session_minutes`
- [ ] Mensagem pós-booking inclui recomendações e pede confirmação de leitura
- [ ] Fluxo testado end-to-end sem regressões

---

## 7. Referências

- `CLAUDE.md` (padrões do projeto)
- Feedback de colaborador (sessão 2026-02-21)
- `scheduler/src/services/conversation_engine.py` (fluxo atual)

---

## Status (preencher após conclusão)

- [x] Pendente
- [x] Spec gerada: `spec/006-ux-improvements-v1.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
