# WORKFLOW — Traffic Manager

> Processo de trabalho entre Rodrigo e agent-rods ⚡

---

## Princípios

- **State of the art** — sempre a melhor solução conhecida, não a mais rápida
- **Ready for prod** — código que vai direto pra produção, sem "depois a gente melhora"
- **Completeness** — sem meios-termos, sem TODOs esquecidos, sem edge cases ignorados

---

## Fluxo de uma Task

### 1. Backlog — Definição do Card
O Rodrigo (ou o agent) descreve o card com:
- Título claro
- Descrição do problema/necessidade
- Escopo (o que entra e o que NÃO entra)
- Token budget estimado

### 2. Ready — Planejamento (2 etapas obrigatórias)

Antes de mover para In Progress, o agent cria:

#### 2a. Plano
- Arquivos a criar / modificar / deletar
- Ordem de implementação
- Decisões técnicas relevantes (libs, padrões, trade-offs)
- Riscos identificados

#### 2b. Meta-plano (como validar o plano)
- Como vamos saber que o plano está correto?
- Critérios de aceite (o que define "pronto"?)
- Como testar cada parte?
- O que pode dar errado e como detectar?

> ⚠️ O agent **não começa a codar** sem o Rodrigo aprovar o plano + meta-plano.

### 3. In Progress — Execução

Ao iniciar:
1. Verificar tokens com `session_status`
2. Registrar tokens de início no TOKEN_LOG.md
3. Implementar seguindo o plano aprovado
4. Testar conforme o meta-plano
5. Documentar (atualizar CLAUDE.md, criar testes/mocks se necessário)

Durante execução:
- Monitorar contexto a cada etapa significativa
- Se > 70% → pausar, compactar, continuar
- Nunca desviar do plano sem comunicar

### 4. QA — Validação do Rodrigo

Ao mover para QA:
1. Registrar tokens de fim no TOKEN_LOG.md
2. Atualizar KANBAN.md com status QA
3. Escrever summary do que foi feito + como testar
4. **PARAR.** O trabalho do agent termina aqui.

O Rodrigo valida, testa, e decide:
- ✅ Aprovado → move para Done
- 🔁 Revisão necessária → volta para In Progress com feedback

---

## Monitoramento de Tokens

Antes de cada task:
```
session_status → verificar contexto atual
```

Limites:
- 🟢 < 50% → livre
- 🟡 50-70% → atenção
- 🟠 70-85% → compactar antes de continuar
- 🔴 > 85% → parar, nova sessão ou compactação obrigatória

---

## Regras Gerais

- **Um card por vez** em In Progress
- **Sem surpresas** — qualquer desvio do plano é comunicado antes de executar
- **Documentação não é opcional** — faz parte do Definition of Done
- **Testes fazem parte do card** — sem testes = card incompleto
- **CLAUDE.md é vivo** — atualizar quando descobrir padrões novos

---

## Stack de Referência

### Scheduler (backend)
- Python, AWS Lambda, Serverless Framework
- PostgreSQL RDS (schema `scheduler`)
- DynamoDB (sessions, events, reminders)
- Z-API (WhatsApp)

### Frontend (Scheduler Panel)
- React 19 + TypeScript (strict) + Vite 7
- TailwindCSS v4 + React Router v7 + TanStack Query v5
- Axios (interceptors) + React Hook Form + Zod
- Vitest + Testing Library
- Deploy: Vercel
- Auth: `x-api-key` header via Axios interceptor
- Padrões detalhados: `frontend/CLAUDE.md`
