# KANBAN — Traffic Manager

> Workflow: Backlog → Ready → In Progress → QA (pausa p/ Rodrigo validar)
>
> Tarefas **concluídas** são registradas em [`TASKS_LOG.md`](./TASKS_LOG.md), que é
> o histórico detalhado. Este arquivo é só a fila do que ainda não foi feito.

---

## 📋 BACKLOG

Ordenado por prioridade. Itens marcados **[05/10]** foram descobertos na sessão
de 05/10/2026 e ainda não tinham dono.

### 🔴 Produto quebrado para a paciente

**B-01 · Resposta de campanha vai para uma pessoa** — PRD `019-resposta-de-campanha.md`
Em 30/09 a clínica disparou campanha de outros procedimentos para **320**
pacientes pedindo "responda esta mensagem"; **30** responderam e **2** receberam
do bot que a clínica *não oferece* o produto. O PR #88 resolve o caso que nomeia
o procedimento (Marie), e **não** resolve o que não nomeia (Yasmin). A exposição
se repete a cada campanha. **[05/10]**

**B-02 · O bot confunde reclamação com consulta de agenda** — sem PRD
Quando a Marie respondeu "Vocês que mandaram essa mensagem. Não entendi…", o bot
respondeu "não encontrei nenhum agendamento ativo no seu nome, pode ter sido
algum engano" - mapeou um desacordo para busca de agendamento e disse à paciente
que a campanha da clínica foi engano. Defeito separado do B-01; o #88 evita
*chegar* nesse ponto no caso dela, não o defeito em si. **[05/10]**

**B-03 · `nobrelaser-sjc` ganhou a guarda do 018 sem pedir** — sem PRD
Prod tem 4 clínicas e a guarda de procedimento fora do escopo vale para todas.
As três além da Essência passam a mandar pergunta de não-laser para a fila sem
ter solicitado. Decidir: a guarda vira opt-in por clínica, ou avisa-se as outras.

### 🟡 Medições com data marcada

**B-04 · Atribuição dos 30 agendamentos no Google** — conferir no Google Ads se o
evento "Agendou pelo WhatsApp" recebeu atribuição. As 15 compras já confirmaram
15,0 atribuídas.

**B-05 · `offline_conversion_upload_*_summary`** — conferir entre 05 e 10/10, que
é o primeiro ciclo com o cron no último dia do mês.

**B-06 · Cobertura de `NO_SHOW`** — medir por volta de 04/12/2026, antes de
promover o evento PURCHASE a biddable.

**B-07 · Falsos positivos do detector do 018** — o detector casa por **menção**,
inclusive em negação e histórico: *"não quero botox, quero laser"* e *"já fiz
preenchimento antes, mas agora quero laser"* vão para a fila. Agora que os
motivos ficam gravados, contar quantos `procedimento_fora_do_escopo` citavam
laser na mesma mensagem - e só então decidir se vale complicar a regra. **[05/10]**

### 🟢 Infraestrutura e dívida

**B-08 · Linter Python no `scheduler/` e no `infra/`** — não existe nenhum
configurado, e por isso 9 imports mortos acumularam sem nada apontar (`Any`,
`Dict`, `Optional` em `ai_tools`; `field`, `esta_pausado`, `TemplateService` em
`conversation_agent`; `Any`, `field`, `calcula_duracao` em `conversation_engine`).
O `frontend/` tem ESLint com `--max-warnings 0` e está limpo - é a prova de que a
causa é a ausência da ferramenta. Um `ruff` fecha a classe inteira. **[05/10]**

**B-09 · Check órfão `Vercel – booking-site`** — falha em **todo** PR porque
`booking-site/` não existe no repo. Mascara check vermelho de verdade. O conserto
é reconfigurar ou apagar o projeto na conta Vercel do Rodrigo, fora do repo.

**B-10 · Rate limit no `/auth/login`** — aceita tentativas ilimitadas. Pesa mais
desde a primeira conta de recepção.

**B-11 · ADMIN ainda usa a API key compartilhada** — STAFF já tem sessão própria;
metade da dívida de autenticação por usuário segue aberta. É o que mantém
`created_by_user_id` como autoria *declarada*, não provada.

**B-12 · CloudFormation em 452/500 no `scheduler`** — os 74 log groups são o
próximo ganho.

**B-13 · Banco de `dev` inacessível** — o pooler do Supabase fecha a conexão
(`aws-1-us-east-1.pooler.supabase.com:6543`). Scripts que apontam para dev falham;
só prod responde. **[05/10]**

**B-14 · Bug do `translate` e verificador de drift de schema** — `Ú→o`, `Ç→u`.

**B-15 · Imagem em Python 3.9.**

**B-16 · Ondas 2-4 de UX do painel** — ordem do formulário, acentos, contraste.

**B-17 · `HarmonizacaoBookingForm.tsx` sem `submitLead`** na landing page.

**B-18 · Rastreio de clique no WhatsApp** — exige conversion action **nova**: a
`Lead - Whatsapp` está `REMOVED`, que é irreversível.

### ⚪ PRs antigos a decidir

- **#4** `chore: configure no-mistakes validation gate`
- **#5** `ci: GitHub Actions para deploy do backend` — vale reavaliar: resolveria
  o deploy manual, e conversa com o B-08
- **#6** `feat: Fatia 0 do sistema multi-agente`

---

## ✅ READY

Cards com plano + meta-plano definidos, prontos para execução.

*(nenhum)*

---

## 🔄 IN PROGRESS

Card em execução ativa.

*(nenhum)*

---

## 🔍 QA

Implementação concluída. **Aguardando validação do Rodrigo.**

*(nenhum)*

---

## ✔️ DONE

Entregas ficam em [`TASKS_LOG.md`](./TASKS_LOG.md), com o detalhe de cada uma.

O antigo **CARD-001 (Frontend React — Painel do Dono da Clínica**, criado em
2026-03-08) está entregue: o painel existe em `frontend/`, em produção na Vercel.

---

## Como usar

1. **Backlog** → Descrever o card com escopo claro
2. **Ready** → Adicionar Plano + Meta-plano ao card antes de mover
3. **In Progress** → Um card por vez. Registrar tokens de início.
4. **QA** → Trabalho do agent pausa aqui. Rodrigo valida.
5. **Done** → Registrar em `TASKS_LOG.md` após aprovação.
