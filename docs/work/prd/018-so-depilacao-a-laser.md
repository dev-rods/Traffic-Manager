# PRD — 018 Só depilação a laser, e uma fila para o resto

> Gerado na fase **Research**. Decisão do André em 04/10/2026.

---

## 1. Objetivo

Duas coisas, e a segunda existe por causa da primeira:

1. **O bot não fala sobre procedimento que não é depilação a laser.** Pergunta
   sobre preenchimento, toxina botulínica, bioestimulador ou estética facial vai
   para uma especialista - sem resposta, sem estimativa, sem consultar o FAQ.
2. **O painel passa a ter a fila de quem está esperando essa especialista**, com
   o motivo e o tempo de espera. Sem isso, a regra acima só produz pacientes
   esperando sem ninguém sabendo.

---

## 2. Contexto

### 2.1 A clínica vende mais do que o bot atende

A Essência vende preenchimento, toxina botulínica e bioestimulador. O bot atende
**um** desses: o laser. Não é limitação temporária - preço de injetável depende
de avaliação presencial, de quantos mililitros, da indicação. Nada disso cabe num
catálogo de áreas com preço por região, que é o que o bot tem.

### 2.2 Hoje funciona por acidente, e o acidente é frágil

`get_faq_answer` ordena por relevância e tem um piso (`busca_no_faq.PISO`).
Pergunta sobre botox não casa nada, a tool devolve vazio com a instrução de
chamar a especialista, e a resposta sai certa.

O acidente desmonta de duas formas:

| Como desmonta | O que a paciente recebe |
|---|---|
| A clínica cadastra um item de FAQ sobre botox | Resposta do bot sobre botox - o que não pode |
| A pergunta carrega palavra de laser | **Preço de depilação para quem perguntou de injetável** |

A segunda está medida: `busca("quanto custa a toxina botulinica por sessao?")`
contra o FAQ real da Essência passa do piso, porque "custa" e "sessão" casam com
itens de depilação. Esse é o erro caro - a pessoa chega na clínica com um número
na cabeça que nunca foi dela. Ver `tests/unit/test_fora_do_escopo.py`.

### 2.3 A fila não existia, e o motivo era jogado fora

`request_human_handoff` recebe `reason` e o executor só o devolvia: ninguém
gravava. A conversa ia para a fila como um telefone sem contexto, e a atendente
descobria o que a pessoa queria lendo a thread inteira.

Pior: o bloco que marca a conversa como entregue estava **copiado em sete
lugares** (seis no `conversation_agent`, um no `bot_policy`). Sete cópias que
precisavam concordar sobre o que "entregue" significa.

---

## 3. Decisões

| # | Decisão | Por quê |
|---|---|---|
| 3.1 | **Guarda determinística + instrução no prompt** | A lista barra o que nomeia, antes do modelo ver a pergunta. O prompt cobre o procedimento que a clínica vende e ninguém cadastrou. Instrução sozinha o modelo contorna - é o histórico de `areas_ambiguas`, `menor_de_idade`, `proveniencia`. |
| 3.2 | A guarda roda **antes do agente**, não depois | Enquanto a pergunta chega ao modelo, existe um caminho em que ele compõe a resposta a partir de um item de FAQ de laser. |
| 3.3 | A guarda roda **depois da agregação de mensagens** | "vocês fazem" + "botox?" em dois balões: no webhook, antes da janela, cada pedaço passaria livre. |
| 3.4 | Lista no código + coluna que **acrescenta** | A lista é o piso, igual para toda clínica, com teste. A coluna `bot_procedimentos_fora_do_escopo` cobre o procedimento novo que entra no cardápio antes de a gente saber dele. |
| 3.5 | `handoff_reason` em **vocabulário fechado** | O valor vira rótulo na fila. Texto livre do modelo faria a fila falar uma língua diferente a cada conversa. |
| 3.6 | A fila ordena pela espera **mais antiga primeiro** | Contrário do resto do painel, e de propósito: o topo tem que ser quem espera há mais tempo. `updated_at` não serve - muda a cada mensagem que a paciente manda enquanto ninguém responde. |
| 3.7 | A aba fica na **BotPage**, não em rota nova | A tela já lista conversas e já tem a thread. Rota nova duplicaria as duas. |

---

## 4. O que mudou

### Backend

| Arquivo | Mudança |
|---|---|
| `src/services/fora_do_escopo.py` | **novo** - a lista, a mensagem à paciente e a instrução do prompt |
| `src/services/bot_policy.py` | `entrega_a_humano()` - a fonte única das sete cópias; vocabulário de motivos e seus rótulos |
| `src/services/conversation_agent.py` | guarda antes do loop; as cinco cópias viram chamada; instrução no prompt; perdeu o alias do TTL |
| `src/services/conversation_engine.py` | a mesma guarda no caminho legado |
| `src/services/ai_tools.py` | `reason` validado e com `enum`; FAQ vazio aponta `faq_sem_resposta` |
| `src/functions/attendant/list_active.py` | devolve `handoff_reason`, `handoff_reason_label`, `handoff_requested_at` |
| `src/scripts/setup_database.py` | coluna `clinics.bot_procedimentos_fora_do_escopo` |

### Frontend

| Arquivo | Mudança |
|---|---|
| `src/pages/bot/components/FilaDeAtendimento.tsx` | **novo** - duas abas, com os quatro estados |
| `src/utils/esperaDesde.ts` | **novo** - "espera 3h", e o corte de 1h que acende o alerta |
| `src/pages/bot/BotPage.tsx` | a seção "Conversas pausadas" dá lugar à fila |
| `src/types/index.ts` | `ActiveConversation` ganha os campos do handoff |

---

## 5. Pendente

- **Os itens de FAQ a cadastrar.** Resposta de FAQ é política da clínica; o
  conteúdo vem da Essência, não do código. A tela de FAQ do painel já edita a
  tabela `scheduler.faq_items`.
- **A coluna extra não tem tela.** `bot_procedimentos_fora_do_escopo` só é
  editável por SQL. Os procedimentos da Essência já estão na lista do código, e
  construir a tela antes de haver um termo para pôr nela seria adiantar.
- **Rodar `setup_database.py`** nos dois stages (a migration é idempotente).

---

## 6. Status

| Fase | Quando |
|---|---|
| Research + implementação | 04/10/2026 |
| Testes | 1222 unit no scheduler, 357 no frontend, lint e build limpos |
| Deploy | pendente |
