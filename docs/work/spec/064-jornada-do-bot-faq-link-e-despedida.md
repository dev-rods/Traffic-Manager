# Spec - 064 Jornada do bot: FAQ como fonte, link no momento certo, despedida uma vez

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/064-jornada-do-bot-faq-link-e-despedida.md`
- **Decisões aplicadas (25/11/2026):** P1 proposta sem oferta; P2 link da
  campanha/lembrete não conta, link sozinho na primeira resposta,
  insistência = conversa até o fim; P3 tudo em modo `fonte`, bolha literal
  só como fallback; P4 calar; P5 mensagem imediata na política
  `LEADS_ONLY`; P6 três tipos de virilha com valor; P7 calar na retomada
  pelo painel; saudação pelo relógio.

---

## 1. Resumo

Só `scheduler/` (código Python, prompt no banco e eval). Nenhuma migration,
nenhuma rota nova, nada no painel. Seis frentes:

1. FAQ vira fonte: `get_faq_answer` devolve o texto ao modelo, a bolha
   literal sai só quando a ancoragem falha duas vezes.
2. Caminho de agendamento decidido antes do modelo (`caminho_de_agendamento`),
   com a trava da tool rebaixada a asserção.
3. Fecho social: guarda compartilhada que cala o bot (fluxo normal e
   retomada pelo painel) e um retorno "sem resposta" que não vira handoff.
4. Retomada responde primeiro a última pergunta (bloco no fim do prompt +
   trava).
5. Saudação pelo relógio da clínica (bloco CALENDÁRIO com hora + trava).
6. Mensagem imediata na Nobre quando a política cala o bot (P5).

Mais: prompt do banco (etapa 3 ÁREAS e retomada) reescrito por script nas
duas clínicas, default do código alinhado, eval com os três casos como
regressão.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/services/caminho_de_agendamento.py` | decide `conversa` / `link_primeiro` / `conversa_por_insistencia` antes do modelo |
| `scheduler/src/services/fecho_social.py` | `e_fecho_social` (movido de `retomada.py`) + `deve_calar(eventos, texto)` |
| `scheduler/src/services/ancoragem_do_faq.py` | confere se a fala do modelo só traz fatos presentes no item devolvido |
| `scheduler/src/services/saudacao.py` | período do dia pelo fuso da clínica e correção da saudação na saída |
| `scheduler/src/scripts/corrige_prompt_064.py` | reescreve no banco (Essência e Nobre) a etapa 3 ÁREAS, o bloco de retomada e a regra de saudação; `--dry-run` imprime o diff |
| `scheduler/tests/evaluation/fixtures_064.py` | as três conversas do PRD (anonimizadas) com asserções |
| `scheduler/tests/unit/test_caminho_de_agendamento.py`, `test_fecho_social.py`, `test_ancoragem_do_faq.py`, `test_saudacao.py` | unitários |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `src/services/ai_tools.py` | `_tool_get_faq_answer` devolve `answer` ao modelo; `_recusa_sem_o_link` vira asserção (log) e deixa de recusar; descrição da tool |
| `src/services/policy_do_faq.py` | texto da descrição da tool; `repete_o_item` deixa de descartar (só loga) |
| `src/services/conversation_agent.py` | caminho de agendamento no início de `process_message`; guarda de fecho social; retorno "calei"; ancoragem com fallback literal; retomada no fim do prompt; CALENDÁRIO com hora; trava da saudação; bloco "COMO RESPONDER DÚVIDAS" reescrito; `_build_outgoing` bolha literal depois da fala |
| `src/services/skills/__init__.py` | `bloco_do_site` passa a depender de `paciente.encontrado`, não da skill; texto sem oferta |
| `src/services/autoatendimento.py` | `pedidos_de_agendar_na_conversa` (contador na sessão) |
| `src/services/conversation_resume.py` | `ha_pergunta_em_aberto` devolve False em fecho social (P7) |
| `src/services/retomada.py` | importa `e_fecho_social` do módulo novo |
| `src/services/template_service.py` | default = prompt de prod da Essência após o script; remove "Termine TODA mensagem com uma pergunta" e `present_options` para serviços |
| `src/functions/webhook/handler.py` | P5: mensagem imediata quando `pode_responder` é falso só pela política `LEADS_ONLY` |
| `src/services/atendimento.py` | `motivo_da_recusa(...)` para o webhook saber que foi a política |
| `tests/evaluation/eval_fluxo_agente.py` | FAQ real no `DbFalso`, pacientes no corpus, fixtures 064 |
| `tests/unit/test_carrinho_do_site.py` e demais que mockam `get_faq_answer` | novo formato de retorno |

---

## 4. Arquivos a remover

Nenhum. `retomada.e_fecho_social` fica como alias por um ciclo.

---

## 5. Ordem de implementação sugerida

1. `fecho_social.py` + guarda no agente + retorno "calei" + P7 (caso 3).
2. `saudacao.py` + CALENDÁRIO com hora + trava.
3. `caminho_de_agendamento.py` + asserção na tool + `bloco_do_site` por cadastro + contador de insistência (caso 2).
4. FAQ como fonte: tool, ancoragem, fallback literal, ordem na saída, bloco do prompt (caso 1).
5. Retomada: bloco no fim + trava "responda a última pergunta".
6. Script do prompt (dry-run, eval com `--prompt-arquivo`, gravar em dev, depois prod).
7. P5 no webhook.
8. Eval antes/depois; TASKS_LOG com os números.

Cada passo é um PR próprio quando tocar prod; 1 e 2 podem ir juntos.

---

## 6. Detalhes por arquivo

### `src/services/fecho_social.py` (criar)

- `e_fecho_social(texto) -> bool`: o de `retomada.py:105`, movido.
- `tem_conteudo_novo(texto) -> bool`: "?" ou dígito ou nome de área do
  catálogo (recebe a lista) ou data por extenso.
- `ultima_fala_do_bot_foi_fecho(eventos, agora, janela_h=24) -> bool`:
  última OUTBOUND com texto dentro da janela cujo conteúdo não termina em
  "?" e casa `obrigad|por nada|até|abraço|qualquer dúvida|à disposição|
  te esperamos|boa (sessão|semana|noite|tarde)`.
- `deve_calar(eventos, texto, areas, agora) -> bool`:
  `e_fecho_social(texto) and not tem_conteudo_novo(texto, areas) and
  ultima_fala_do_bot_foi_fecho(eventos, agora)`.
- Log `[FechoSocial] {phone}: calei` no chamador.

### `src/services/conversation_agent.py` (modificar)

- **Antes do modelo** (logo após carregar a sessão e os eventos, perto de
  466-478): se `fecho_social.deve_calar(...)`, grava a fala no histórico
  (`agent_history` com o turno `user` e um `assistant` vazio NÃO é válido:
  grava só o evento, não o histórico) e devolve `[]` com um novo campo de
  resultado `motivo="fecho_social"`. O chamador (`_processar_mensagem` no
  webhook) já trata lista vazia como "nada a enviar".
- **Retorno "sem resposta" legítimo:** em 765, `vazia` passa a considerar
  `sem_consulta_declarada_como_despedida` (a tool `sem_consulta_necessaria`
  chamada com `motivo` casando `despedid|agradec|encerr`): nesse caso
  resposta vazia é aceita e vira `[]`, sem `PEDIDO_DE_VERSAO_CURTA` nem
  handoff. Cinturão e suspensório: a guarda determinística pega o caso
  comum; esta deixa o modelo calar quando a guarda não pegou.
- **Caminho de agendamento:** depois de `identificar_paciente` e do link
  (424), `caminho = caminho_de_agendamento.decide(clinic, paciente,
  session, user_content, link)`. Entra no `ctx` (`ctx["caminho"]`) e no
  system prompt como bloco `═══ AGENDAMENTO: {LINK|CONVERSA} ═══` (texto
  em `caminho_de_agendamento.bloco(caminho, link)`). Log `[Caminho]
  {phone}: {caminho} (pedidos={n}, link_ja_foi={bool})`.
- **FAQ:**
  - `faq_entregues` continua existindo, mas passa a receber só itens que
    DEVEM sair literais (fallback). O retorno da tool muda (ver
    `ai_tools`).
  - Depois da resposta final, se houve `get_faq_answer` neste turno:
    `ancoragem_do_faq.confere(texto_final, itens_consultados)`. Falhou →
    uma reescrita com "PARE. Use só o que o item do FAQ diz: {trechos
    faltantes}. Não acrescente prazos, quantidades ou produtos que não
    estão nele."; falhou de novo → o item vai para `faq_entregues`
    (bolha literal) e a fala do modelo é reduzida à saudação/pergunta
    (`policy_do_faq.fala_sem_o_item`, que já existe). Log `[FAQ]
    ancoragem falhou 2x; literal`.
  - `_build_outgoing`: bolhas de `faq_entregues` DEPOIS da fala do modelo.
  - Bloco "COMO RESPONDER DÚVIDAS" (1444-1458) reescrito: "get_faq_answer
    devolve o texto da clínica. Responda só o que foi perguntado, com as
    palavras do item, curto. Não acrescente nada que não esteja nele. Não
    cole o item inteiro: explicação completa só se ela pedir."
  - Mais de 2 itens por turno: mantém o handoff.
- **Retomada:** com gatilho `__RETOMAR_CONVERSA__`, o bloco de retomada
  sai do meio do template e é anexado como ÚLTIMO bloco do system prompt,
  com a pergunta em aberto extraída: `retomada.ultima_pergunta(eventos)`
  (última INBOUND com "?" ou começando por `quanto|qual|quando|tem|como|
  onde`). Trava na resposta final: se há pergunta em aberto e a resposta
  não contém nenhum termo dela (lematização simples por raiz de 4 letras)
  nem dígito, reescreve uma vez com "PARE. Responda primeiro: '{pergunta}'.
  Depois conduza." Log `[Retomada] respondeu fora da pergunta`.
- **CALENDÁRIO com hora:** `calendario.bloco(hoje)` ganha `agora` (hora
  local da clínica, `clinic.timezone` como já usado pelo check-in) e a
  linha "Agora: {HH:MM}, {período}." Prompt (DATAS, 1494) ganha a regra da
  saudação (ver `saudacao.py`).
- **Trava da saudação** na resposta final: `saudacao.corrige(texto,
  periodo_atual)`: se o texto tem `bom dia|boa tarde|boa noite` de outro
  período, troca pelo atual; se o texto começa com a saudação copiada da
  pessoa ("Olá, boa noite" idêntico ao início da mensagem dela) e o
  período não bate, idem. Sem período (fuso ausente) → "Olá". Log
  `[Saudacao] corrigi {de} -> {para}`.

### `src/services/caminho_de_agendamento.py` (criar)

```
CONVERSA = "conversa"
LINK_PRIMEIRO = "link_primeiro"
CONVERSA_POR_INSISTENCIA = "conversa_por_insistencia"

def decide(clinic, paciente, session, texto, link) -> str
```

- Sem `link` (clínica sem domínio) ou `not paciente.get("encontrado")` →
  `CONVERSA`.
- `autoatendimento.link_ja_foi(session)` (7 dias, só link do BOT) →
  `CONVERSA`.
- `pede_agendar(texto)`: regex `agendar|marcar|horário|horario|vaga|data|
  dia \d|remarcar` (sem `cancelar`). Se não pede → `CONVERSA` (dúvida é
  respondida aqui; nada muda).
- Pede e `session["pedidos_de_agendar_na_conversa"] == 0` → marca 1 e
  devolve `LINK_PRIMEIRO`.
- Pede de novo (contador ≥ 1), ou texto casa `não consigo|nao consigo|não
  abre|prefiro aqui|por aqui mesmo|pode marcar você|marca pra mim` →
  `CONVERSA_POR_INSISTENCIA` (grava `session["insistiu_em"]`).
- `bloco(caminho, link)`:
  - `LINK_PRIMEIRO`: "═══ AGENDAMENTO: LINK ═══ Esta pessoa já é paciente e
    a clínica agenda pelo site. Responda em UMA frase que é pelo link
    {link}, e se coloque à disposição para dúvidas. Não pergunte áreas,
    não ofereça datas, não chame check_availability nem book_appointment,
    e não ofereça marcar por aqui."
  - `CONVERSA_POR_INSISTENCIA`: "═══ AGENDAMENTO: CONVERSA ═══ Ela já
    recebeu o link e pediu de novo por aqui: conduza o agendamento até o
    fim nesta conversa. Nunca mande o link de novo, nem no fechamento."
  - `CONVERSA`: vazio (fluxo de sempre).
- Campanha e lembrete: não entram na decisão (P2); o bloco da campanha
  (`prompt_da_campanha.py:70-86`, "1. LINK / 2. SE ELA NÃO CONSEGUIR") é
  coerente e fica.

### `src/services/ai_tools.py` (modificar)

- `_recusa_sem_o_link` (707-732): se `ctx["caminho"] == LINK_PRIMEIRO` e a
  tool é `check_availability`/`book_appointment`, NÃO recusa; loga
  `[Caminho] VIOLAÇÃO: {tool} com caminho=link_primeiro` (métrica do eval)
  e segue. Em `CONVERSA_POR_INSISTENCIA`, nada. Remove o erro
  `primeiro_o_link`.
- `_tool_get_faq_answer` (983-1033): devolve
  `{"question": label, "answer": item["answer"], "instruction": "Answer
  ONLY what the patient asked, briefly, using the words of this text. Do
  not add facts that are not in it. Do not paste the whole text unless
  the patient asked for the full explanation."}`. Empilha em
  `ctx["faq_consultados"]` (novo), não em `faq_entregues`. Log `[FAQ]
  consultado {chave}`.
- Descrição da tool em `policy_do_faq.definicao_da_tool`: "Get the
  clinic's own answer text for ONE question. Use it as the only source
  for your reply: answer just what was asked, briefly, in your words but
  with the facts of the text. If no item answers, do NOT call this tool..."

### `src/services/ancoragem_do_faq.py` (criar)

- `fatos(texto) -> set`: números (com unidade colada: `7 dias`, `-3°C`,
  `30%`), nomes próprios de produto (palavras capitalizadas fora do início
  de frase), e termos de uma lista fixa (`isotretinoína|roacutan|
  gestante|lactante|peeling|ácido|cera|pinça|protetor`).
- `confere(fala, itens) -> list[str]`: fatos da fala que não aparecem em
  nenhum item consultado; vazio = ancorada.
- Deliberadamente permissivo: pega o modelo acrescentando prazo ou
  quantidade; não tenta julgar paráfrase.

### `src/services/policy_do_faq.py` (modificar)

- `repete_o_item` deixa de descartar a fala: só loga `[FAQ] o modelo
  colou o item` (métrica). Com o modo fonte, copiar é aceitável; o
  objetivo é não colar o item inteiro sem pergunta, e isso o prompt e o
  eval medem.
- `MAX_ITENS_POR_TURNO = 2` fica.

### `src/services/skills/__init__.py` (modificar)

- `bloco_do_site` deixa de existir como bloco de skill; o texto migra para
  `caminho_de_agendamento.bloco`. `conversation_agent.py:432-433` troca a
  condição "skill != PRIMEIRO_AGENDAMENTO" por "caminho != CONVERSA".

### `src/services/autoatendimento.py` (modificar)

- `CAMPO_PEDIDOS = "pedidos_de_agendar_na_conversa"`, `registra_pedido`,
  `pedidos`. Zera quando `link_ja_foi` vence (7 dias) ou após
  `book_appointment` com sucesso.

### `src/services/conversation_resume.py` (modificar)

- `ha_pergunta_em_aberto`: ao achar a última INBOUND com texto, se
  `fecho_social.e_fecho_social(texto)` e não `tem_conteudo_novo` → False
  (P7). O painel mostra "última mensagem foi um agradecimento", reusando
  o alerta `FECHO_SOCIAL` de `retomada.py:58-65`.

### `src/services/saudacao.py` (criar)

- `periodo(agora_local) -> "manhã"|"tarde"|"noite"` (até 12h, até 18h,
  depois).
- `saudacao_do_periodo(p)`: "Bom dia" / "Boa tarde" / "Boa noite".
- `corrige(texto, p) -> str` como descrito acima; preserva o resto.
- Regra no prompt (bloco DATAS do código): "Cumprimente pelo período de
  AGORA (linha 'Agora:' do CALENDÁRIO), nunca copiando a saudação da
  pessoa. Em dúvida, 'Olá'."

### `src/functions/webhook/handler.py` e `src/services/atendimento.py` (P5)

- `atendimento.motivo_da_recusa(clinic, session, phone, silenciado)` →
  `"politica"` quando a única porta fechada é `_politica_permite`.
- No ramo "Resposta automática suprimida" (420-438): se motivo é
  `"politica"` e `session.get("aviso_de_espera_em")` não está nas últimas
  24 h, envia por `envia_texto` (eco reconhecido, não pausa o bot) o
  template `AVISO_DE_ESPERA` (default em `template_service`: "Oi! Que bom
  ter você por aqui 😊 Já recebi sua mensagem e uma especialista da
  {{clinic_display_name}} vai te responder em instantes.") e grava
  `aviso_de_espera_em`. Não muda `handler`, não conta como fala do bot
  para a retomada (`metadata.kind = "aviso_de_espera"`, ignorado por
  `ha_pergunta_em_aberto`).

### `src/scripts/corrige_prompt_064.py` (criar)

Reescreve em `message_templates.AI_SYSTEM_PROMPT` das duas clínicas (a
partir do texto atual, por âncoras, como `corrige_prompt_areas.py`):

- Etapa **3. ÁREAS**, item da virilha, NOVO texto:
  > Virilha sem o tipo dito: chame list_areas e responda com as três
  > opções e o valor de cada uma, em três linhas curtas (simples: só o que
  > fica para fora do biquíni; cavada: quase toda, deixando uma faixa
  > central; completa: toda a região), e pergunte qual ela quer. Use
  > get_faq_answer dos tipos só se ela pedir a explicação completa.
  > Depois do tipo, pergunte em uma linha se quer incluir a região
  > perianal.
- Etapa **2. DÚVIDA**: "Chame get_faq_answer e responda só o que foi
  perguntado, curto, com as palavras do item. Não cole o texto inteiro."
- **RETOMADA DE CONVERSA**: fica no banco, mas o agente anexa também no
  fim (código); o texto ganha "Nunca comece pela etapa de áreas se há
  pergunta em aberto: a pergunta vem primeiro."
- **Despedida** (novo parágrafo em COMO VOCÊ ESCREVE): "Depois de se
  despedir ou agradecer, não responda a outra despedida ou agradecimento.
  Só volte se houver pergunta ou informação nova."
- `--dry-run` imprime o diff; `--stage dev|prod`. Eval com
  `--prompt-arquivo` antes de gravar em prod.

### `src/services/template_service.py` (modificar)

- Default `AI_SYSTEM_PROMPT` = prompt de prod da Essência após o script
  (uma fonte). Remove "Termine TODA mensagem com uma pergunta" e
  "list_services → present_options". `AVISO_DE_ESPERA` novo.

### `tests/evaluation/` (modificar e criar)

- `DbFalso` carrega o FAQ real da clínica (leitura de prod, como o prompt).
- Corpus ganha pacientes: `identificar_paciente` devolve `encontrado=True`
  com e sem sessão futura para um subconjunto (parâmetro `--pacientes`).
- `fixtures_064.py`: três conversas sintéticas equivalentes aos casos
  (sem nomes nem números reais) com asserções:
  1. "Quanto é a depilação na virilha?" → uma mensagem; contém os três
     tipos e três valores; zero bolhas literais; saudação do período atual.
  2. Campanha com link + "podemos marcar dia 3 às 15:30?" → primeira
     resposta contém o domínio e não contém pergunta de áreas; segunda
     mensagem "prefiro marcar por aqui" → `book_appointment` chamada e
     nenhuma resposta posterior contém o domínio.
  3. "Muito obrigada" após confirmação do sistema → resposta de
     despedida; "Até 🙂" → zero mensagens (`motivo=fecho_social`).
- Métricas novas no relatório: `faq_literal`, `faq_colado`, `caminho_
  violado`, `calei`, `saudacao_corrigida`, `retomada_fora_da_pergunta`.

---

## 7. Convenções a respeitar

- Logging com prefixo por módulo (`[FechoSocial]`, `[Caminho]`,
  `[Saudacao]`, `[FAQ]`, `[Retomada]`), telefone mascarado como no resto.
- Nada de nome ou telefone real em teste, fixture ou doc.
- Prompt de prod só muda por script com `--dry-run` e eval antes
  (lição do PRD 037: PUT por curl corrompeu acentos).
- Deploy: dev, smoke das rotas tocadas (webhook com o número do André),
  eval, depois prod. Nunca dev e prod em paralelo.
- Mudança de regra: varrer todos os pontos que decidem o mesmo (link:
  skill, tool, campanha, lembrete, cancelamento) antes de fechar o PR.
