# PRD - 037 Áreas em conversa, não em botões

> Gerado na fase **Research** em 03/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Fazer o bot tratar a escolha de áreas como conversa: quando a pessoa cita uma área que tem variantes no catálogo (virilha, perna, braço, coxa, glúteo), explicar a diferença entre as variantes em texto corrido e perguntar qual ela quer. Botões ficam reservados para datas e horários.

Junto, corrigir na Nobre Laser SJC um FAQ copiado da Essência que aponta para uma área desativada lá.

---

## 2. Contexto

### A conversa que expôs o problema

Nobre Laser SJC, 03/11/2026, lead do site (+55 31 9415-7070). Depois da retomada do bot pelo painel:

| Hora (UTC) | Quem | Mensagem | Formato |
|---|---|---|---|
| 21:41 | pessoa | "Virilha" | texto |
| 23:20 | bot | "Só confirmando: na virilha, você quer incluir também a região do ânus (perianal), ou só a parte da frente?" | **botões** |
| 23:39 | pessoa | "Só a frente" | clique |
| 23:41 | bot | "Show, sem perianal então. Qual tipo de virilha você quer fazer?" | **botões** (Simples / Cavada / Completa) |
| 23:41 | pessoa | "Virilha Simples" | clique |
| 23:42 | bot | "Total: R$ 125,00 ... Temos estas datas disponíveis" | botões |

A pessoa escolheu "Simples" sem saber o que Simples, Cavada e Completa significam. O bot tinha a explicação à mão (FAQ `BIKINI_TYPES`, cadastrado na Nobre e na Essência) e não a usou.

### Causa 1: prompt e tool brigam

O `AI_SYSTEM_PROMPT` de prod (idêntico, byte a byte, nas duas clínicas) diz na etapa de áreas:

> Chame list_areas. Se a pessoa citar as áreas em texto livre, entenda direto - não a faça escolher de novo numa lista.

A descrição da tool `present_options` em `scheduler/src/services/ai_tools.py` diz o contrário:

> Present structured options to the patient. **ALWAYS use this when showing choices (services, areas, dates, times).**

Duas fontes de verdade para a mesma regra; o modelo segue uma ou outra conforme o caso. Medição em prod desde 20/10/2026, mensagens do bot que perguntam tipo de virilha ou perianal:

| Clínica | Em texto | Em botões |
|---|---|---|
| Essência | 15 | 1 |
| Nobre | 5 | 2 |

É variação do modelo sobre uma instrução ambígua, não regressão nem configuração da Nobre.

### Causa 2: explicar as variantes nunca foi regra

Não há, em nenhum lugar, instrução para explicar os tipos antes de perguntar qual: nem no prompt de prod, nem nas skills por estado (`scheduler/src/services/skills/__init__.py`), nem no código, nem em PRD ou commit anterior. Os fixes anteriores sobre virilha foram outros: entender nomes ditos em texto livre (PRs #55 e #86) e combos. A única fonte que descreve Simples, Cavada e Completa é o FAQ `BIKINI_TYPES`, e o prompt manda chamar `get_faq_answer` quando a pessoa **pergunta**, não antes de oferecer as opções.

### Causa 3 (lateral): FAQ da Essência copiado para a Nobre

O FAQ `INTIMATE_AREA_SCOPE` da Nobre responde:

> Se quiser incluir a região perianal, escolha a área 'Virilha Comp. + ânus'.

Essa área foi desativada na Nobre em 16/10/2026 (alinhamento com o site). Lá, perianal é a área "Perianal / Ânus", somada à Virilha Completa. Quem perguntar vai ser apontado para uma opção que não existe.

### O que não é deste PRD

A retomada rodou numa sessão sem histórico de agente e a abertura do bot entrou como `[atendente da clínica]`. É efeito do bug do nono dígito, corrigido e em prod pelo PR #165.

---

## 3. Escopo

### Dentro do escopo
- Descrição da tool `present_options`: usar para **datas e horários**. Áreas, variantes de área e perguntas de sim/não vão em texto.
- Regra nova no prompt (`AI_SYSTEM_PROMPT`, etapa 3 ÁREAS): quando a área citada tem variantes no catálogo retornado por `list_areas`, explicar cada variante em uma linha, em texto corrido, e perguntar qual. Usar o texto do FAQ quando existir um para a área (`BIKINI_TYPES` para virilha); sem FAQ, descrever pelo nome das variantes, sem inventar escopo.
- Mesma regra para perianal: oferecer como adicional em texto, uma linha, só quando a área escolhida for virilha.
- Atualizar o default em `template_service.py` **e** o template gravado no banco de cada clínica em dev e prod (o prompt que roda é o do banco).
- Corrigir o FAQ `INTIMATE_AREA_SCOPE` da Nobre em prod para citar "Virilha Completa + Perianal / Ânus".
- Teste de comportamento que prove que, com "virilha" na mensagem, a rodada não emite `present_options` e o texto cita as três variantes.

### Fora do escopo
- Mudar o formato de datas e horários (continuam em botões ou lista numerada).
- Mexer no agregador de rajada, no eco ou no nono dígito (PRD 033, PR #165).
- Revisar os outros 36 FAQs copiados da Essência para a Nobre (candidato a task própria; este PRD corrige só o que a investigação achou).

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/ai_tools.py` | modificar | Descrição de `present_options`: escopo restrito a datas e horários |
| `scheduler/src/services/template_service.py` | modificar | Default do `AI_SYSTEM_PROMPT`: etapa 3 ÁREAS com a regra de variantes |
| `message_templates.AI_SYSTEM_PROMPT` (banco, dev e prod, todas as clínicas) | atualizar via `PUT /templates/{id}` | Mesma mudança do default |
| `faq_items.INTIMATE_AREA_SCOPE` (banco, prod, `nobrelaser-sjc`) | atualizar via API de FAQ | Nome da área correto na Nobre |
| `scheduler/tests/unit/` | criar | Teste da regra de variantes e da ausência de botões para áreas |

---

## 5. Dependências e riscos

- **Dependências:** API de templates e de FAQ em prod (chave em SSM `/prod/SCHEDULER_API_KEY`). Escrita em prod exige autorização explícita do André na mensagem.
- **Riscos:**
  - Mensagens de área ficam mais longas (3 a 4 linhas para virilha). Aceito: a pessoa precisa dessa informação para escolher.
  - O modelo pode voltar a usar botões para áreas por hábito. A descrição da tool é a trava mais forte, por isso ela muda junto com o prompt, e não só o prompt.
  - Prompt no banco diverge do default do código se um dos dois for esquecido. Checklist do PR deve ter os dois.

---

## 6. Critérios de aceite

- [ ] Com a mensagem "virilha" e catálogo com Simples/Cavada/Completa, o bot responde em texto, cita as três variantes com uma linha cada e pergunta qual, sem chamar `present_options`.
- [ ] Perianal é oferecido em texto, uma linha, só depois da virilha escolhida.
- [ ] Datas e horários continuam saindo por `present_options`.
- [ ] Descrição da tool não contém mais "areas" na lista de usos.
- [ ] `AI_SYSTEM_PROMPT` idêntico entre default do código e banco (dev e prod), conferido por diff.
- [ ] FAQ `INTIMATE_AREA_SCOPE` da Nobre cita área ativa; conferido via `GET /clinics/nobrelaser-sjc/faq`.
- [ ] Teste unitário cobre a rodada "virilha" sem botões.

---

## 7. Referências

- `CLAUDE.md` (padrões do projeto)
- PR #165 (eco do bot com nono dígito): causa da sessão sem histórico nesta conversa
- PRD 018 (só depilação a laser), PRD 020 (arquitetura de atendimento único: FAQ literal, áreas sempre confirmadas)
- Alinhamento da Nobre com o site em 16/10/2026 (áreas desativadas, entre elas "Virilha Completa + ânus")

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada: `spec/037-areas-em-conversa-nao-em-botoes.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
