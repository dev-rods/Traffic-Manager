# Spec - 037 Áreas em conversa, não em botões

> Gerada na fase **Spec** em 03/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/037-areas-em-conversa-nao-em-botoes.md`

---

## 1. Resumo

Três mudanças pequenas e um script. A descrição da tool `present_options`
passa a dizer que ela serve **só para datas e horários**; é a trava mais forte
sobre o modelo e muda primeiro. O bloco "3. ÁREAS" do `AI_SYSTEM_PROMPT` ganha
a regra de explicar as variantes de uma área em texto antes de perguntar qual,
e de oferecer perianal em texto depois da virilha. Como o prompt que roda é o
do banco (Essência e Nobre têm prompt próprio em `message_templates`; o
default do código não as alcança), a regra entra por um script idempotente no
padrão de `corrige_prompt_duvida.py`: simula por padrão, grava com
`--aplicar`, recusa prompt editado à mão. O default do código muda junto, para
não voltar a divergir. O FAQ `INTIMATE_AREA_SCOPE` da Nobre é corrigido via
API.

Achados da pesquisa que precisam constar:

- **O default em `template_service.py` não é o prompt de prod.** É um prompt
  mais antigo, com etapas "list_areas → present_options" e um fluxo de 7
  passos. O prompt de prod (15.232 caracteres, idêntico entre as duas clínicas)
  vem da linhagem de `scheduler/docs/prompt-essencia-pr17.txt`, já
  parametrizado com `{{clinic_display_name}}`, `{{preco_minimo}}` etc. A
  mudança de verdade é a do banco; a do default é só para quem criar clínica
  nova não herdar a regra velha.
- **FAQ sai literal.** `get_faq_answer` entrega o texto do FAQ como bolha
  própria e devolve ao modelo a instrução de não repetir (PRD 020). Então, para
  a virilha, a explicação dos tipos é a bolha do FAQ `BIKINI_TYPES`, e a fala
  do modelo é só a pergunta "qual delas você quer?". A regra do prompt tem de
  ser escrita sabendo disso, senão o modelo parafraseia o FAQ e sai repetido.
- **`present_options` não tem validação em código.** `_tool_present_options`
  só ecoa os argumentos. A restrição é por descrição e prompt; não se cria
  validador de "parece área" (ver preferências: começar pelo caminho direto).
- **Não existe teste do script precedente.** `corrige_prompt_duvida.py` nunca
  foi testado. O novo script nasce com a lógica de substituição numa função
  pura, testável, e o teste prova os três ramos (aplica, já aplicado, recusa).

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/scripts/corrige_prompt_areas.py` | Troca o bloco "3. ÁREAS" do `AI_SYSTEM_PROMPT` de cada clínica no banco. `VELHO`, `NOVO`, `aplica(conteudo) -> (novo_conteudo, status)` com status em `{"aplicado", "ja_corrigido", "bloco_ausente"}`; `main()` simula e só grava com `--aplicar` |
| `scheduler/tests/unit/test_areas_em_conversa.py` | Descrição da tool não cita áreas e cita datas/horários; `aplica` substitui uma vez, é idempotente e recusa bloco ausente; `NOVO` não contém `present_options` como instrução de uso para áreas; default do código não manda `present_options` em áreas |
| `scheduler/tests/integration/037-areas-em-conversa.md` | Roteiro manual: rodar o script em dev e prod, corrigir o FAQ da Nobre, conferir por `GET`, conversa real de "virilha" |
| `scheduler/tests/postman/037-areas-em-conversa.postman_requests.json` | `GET /clinics/{clinicId}/templates`, `GET /clinics/{clinicId}/faq`, `PUT /faq/{faqId}`; padrão de `tests/postman/CLAUDE.md` |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/services/ai_tools.py` | Descrição de `present_options` (linha ~453): escopo restrito a datas e horários, proibição explícita para serviços, áreas, variantes e sim/não |
| `scheduler/src/services/template_service.py` | Default `AI_SYSTEM_PROMPT`, etapa "2. ÁREAS" (linha ~113): tira `→ present_options`, manda entender em texto e explicar variantes |
| `docs/work/prd/037-areas-em-conversa-nao-em-botoes.md` | Status: spec gerada; depois, data de implementação |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. `ai_tools.py`: nova descrição da tool. Rodar a suíte (2019 testes) para
   pegar algum teste que dependa do texto antigo.
2. `corrige_prompt_areas.py` com `aplica()` pura, mais
   `test_areas_em_conversa.py`. Suíte verde.
3. `template_service.py`: default alinhado. Suíte verde.
4. **Dev:** exportar `RDS_*` do SSM `/dev/SUPABASE_DB_*`, rodar o script sem
   flag (simular), ler o diff, rodar com `--aplicar`. Deploy do scheduler em
   dev. Conversa de teste com "virilha" no WhatsApp de dev.
5. **Prod** (cada passo com autorização do André na mensagem): script com
   `--aplicar` em `/prod/SUPABASE_DB_*`; `PUT /faq/{id}` da Nobre; deploy do
   scheduler em prod **a partir de `origin/main`** (ver memória do deploy de
   03/11: deploy sai da árvore local).
6. Conferência: `GET /clinics/{id}/templates` nas duas clínicas e diff entre
   elas (continuam idênticas); `GET /clinics/nobrelaser-sjc/faq` mostra o
   texto novo; pacote da Lambda `WhatsAppWebhook` contém a descrição nova.
7. Docs: integration, postman, PRD com status, `TASKS_LOG.md`.

---

## 6. Detalhes por arquivo

### `scheduler/src/services/ai_tools.py`

- **Modificar** a `description` de `present_options`:

```
Present structured options to the patient. Use it ONLY for dates (the
available_dates from check_availability) and times (the available_slots from
get_time_slots). NEVER use it for services, treatment areas, variants of an
area (e.g. virilha simples/cavada/completa) or yes/no questions: those are
plain-text conversation. Up to 3 options go out as WhatsApp buttons; a tap
comes back to you as the option's label. More than 3 go out as a numbered text
list (1. label, 2. label, ...); if the patient answers with the number, it
reaches you already converted to that option's label. Either way, the next
message is her choice - do not treat it as unclear. `message` is the whole
lead-in to the options; do not repeat or rephrase it in your reply text.
```

- Nada muda em `parameters` nem em `_tool_present_options`.

### `scheduler/src/scripts/corrige_prompt_areas.py`

- **Criar**, no molde de `corrige_prompt_duvida.py` (mesmo docstring de
  propósito, mesma forma de rodar, mesma recusa a prompt editado à mão).
- `VELHO` (texto exato do prompt de prod em 03/11/2026, três linhas):

```
3. ÁREAS
   Chame list_areas. Se a pessoa citar as áreas em texto livre, entenda direto - não a faça escolher de novo numa lista.
   Confirme as áreas, chame calculate_discount e mostre o valor.
```

- `NOVO`:

```
3. ÁREAS
   Chame list_areas. Se a pessoa citar as áreas em texto livre, entenda direto - não a faça escolher de novo numa lista.
   Áreas, variantes de área e perguntas de sim ou não vão em texto corrido, como numa conversa. Nunca use present_options para isso: botões são só para datas e horários.
   Quando a área citada tiver variantes no catálogo, explique a diferença antes de perguntar qual ela quer:
   - Virilha (simples, cavada, completa): chame get_faq_answer sobre os tipos de virilha. O texto do FAQ já vai para a pessoa como mensagem própria; a sua fala é só a pergunta "qual delas você prefere?".
   - Perna, braço, coxa e glúteo (inteira ou 1/2): a diferença é a extensão. Diga isso em uma linha e pergunte qual.
   Perianal é uma área à parte: depois de a pessoa escolher o tipo de virilha, pergunte em uma linha, em texto, se quer incluir a região perianal.
   Confirme as áreas, chame calculate_discount e mostre o valor.
```

- `aplica(conteudo: str) -> tuple[str, str]`:
  - `NOVO in conteudo` → `(conteudo, "ja_corrigido")`
  - `VELHO not in conteudo` → `(conteudo, "bloco_ausente")`
  - senão → `(conteudo.replace(VELHO, NOVO, 1), "aplicado")`
- `main()`: lê `clinic_id, content` de `message_templates WHERE template_key
  = 'AI_SYSTEM_PROMPT'`; para cada, chama `aplica`, imprime o status e o
  `unified_diff` de `VELHO` para `NOVO`; com `--aplicar` faz o `UPDATE ... SET
  content = %s, updated_at = NOW()`. Sem clínica, avisa e sai.
- Usa `PostgresService` com as env `RDS_*` (vêm do SSM `/${stage}/SUPABASE_DB_*`).

### `scheduler/src/services/template_service.py`

- **Modificar** a etapa 2 do default (hoje `2. ÁREAS → Chame list_areas →
  present_options.` + pergunta + confirmação) para:

```
  2. ÁREAS → Chame list_areas. Entenda as áreas que a pessoa citar em texto;
     não use present_options para áreas (botões são só para datas e horários).
     Se a área tiver variantes (virilha simples/cavada/completa, perna ou braço
     inteiro ou 1/2), explique a diferença em uma linha por variante e
     pergunte qual. Depois confirme:
     "Você selecionou [áreas]. Deseja prosseguir para escolher a data?"
```

- Etapas 3 (datas) e 4 (horários) continuam com `present_options`.

### `scheduler/tests/unit/test_areas_em_conversa.py`

- **Criar.** Casos:
  - `test_tool_de_opcoes_e_so_para_datas_e_horarios`: lê a descrição de
    `present_options` em `ai_tools` e confere que cita `check_availability`
    e `get_time_slots` e que a frase de uso não lista `areas` nem
    `services` como caso positivo (procurar por `"ONLY for dates"` e
    `"NEVER use it for services, treatment areas"`).
  - `test_aplica_troca_o_bloco_uma_vez`: prompt com `VELHO` entre dois blocos
    vizinhos ("2. DÚVIDA" antes, "4. DATA E HORÁRIO" depois) → status
    `aplicado`, `NOVO` presente, vizinhos intactos, `VELHO` ausente.
  - `test_aplica_e_idempotente`: `aplica(aplica(p)[0])` devolve
    `ja_corrigido` e o mesmo texto.
  - `test_aplica_recusa_prompt_editado`: bloco com uma palavra trocada →
    `bloco_ausente`, texto devolvido igual ao de entrada.
  - `test_novo_nao_manda_botoes_para_areas`: em `NOVO`, toda ocorrência de
    `present_options` está numa frase com "Nunca" (negação). Isto é o
    teste de texto possível para um prompt; o comportamento é verificado no
    roteiro de integração.
  - `test_default_do_codigo_nao_manda_botoes_para_areas`: no
    `DEFAULT_TEMPLATES["AI_SYSTEM_PROMPT"]`, a linha da etapa ÁREAS não
    contém `→ present_options`, e as linhas de DATAS e HORÁRIOS contêm.
- Sem banco, sem mock de Dynamo: tudo é função pura ou constante.

### `scheduler/tests/integration/037-areas-em-conversa.md`

- **Criar.** Seções: pré-requisitos (SSM, `MSYS_NO_PATHCONV=1`, perfil
  `dev-andre`); rodar o script em dev (simular, aplicar); conferir via `GET
  /clinics/{clinicId}/templates` que o bloco está lá; corrigir o FAQ da Nobre:

```
source .env
curl -s -H "x-api-key: $API_KEY" "$URL/clinics/nobrelaser-sjc/faq" | jq '.[] | select(.question_key=="INTIMATE_AREA_SCOPE") | .id'
curl -s -X PUT -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  "$URL/faq/{faqId}" -d '{"answer": "Não. A Virilha Completa e a região perianal são áreas diferentes, com valores diferentes. Se quiser incluir o perianal, é a área Perianal / Ânus, somada à Virilha Completa."}'
```

- Caso de conversa: mandar "virilha" num número de teste; esperado: bolha do
  FAQ com os três tipos + pergunta em texto, sem botões; escolher "cavada";
  esperado: pergunta de perianal em texto; responder "não"; esperado: valor e
  depois **datas em botões**.

### `scheduler/tests/postman/037-areas-em-conversa.postman_requests.json`

- **Criar** com os três requests acima, seguindo `tests/postman/CLAUDE.md`.

---

## 7. Convenções a respeitar

- Prompt e FAQ moram no banco por clínica: toda mudança de regra tem de ir
  ao default do código **e** ao banco de dev **e** de prod, e ser conferida
  por `GET` depois, não só pelo exit code do script.
- Script de correção de prompt: simula por padrão, `--aplicar` grava,
  idempotente, recusa texto editado à mão (padrão de
  `corrige_prompt_duvida.py`).
- Escrita em prod (banco via script, `PUT` na API, deploy) é ação do André
  ou exige autorização explícita dele na mensagem.
- Deploy do scheduler a partir de `origin/main`, não da árvore de trabalho;
  conferir o pacote da Lambda depois.
- Sem travessão em texto novo de prompt: hífen simples.
- Em bash no Windows: `MSYS_NO_PATHCONV=1` para paths `/dev/...` e `/prod/...`.
