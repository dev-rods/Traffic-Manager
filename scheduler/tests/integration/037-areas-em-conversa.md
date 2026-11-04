# 037 Áreas em conversa, não em botões - Integration

Áreas, variantes de área e perguntas de sim/não saem em texto. Botões
(`present_options`) ficam só para datas e horários. Virilha ganha a explicação
dos tipos pelo FAQ `BIKINI_TYPES` antes da escolha; perianal é oferecido em
texto depois.

Três lugares mudam, e os três precisam ser conferidos:

| Lugar | Como muda | Vale para |
|---|---|---|
| Descrição da tool `present_options` (`ai_tools.py`) | deploy do scheduler | todas as clínicas |
| `AI_SYSTEM_PROMPT` no banco (`message_templates`) | `src/scripts/corrige_prompt_areas.py` | clínicas com prompt próprio (Essência e Nobre, em prod) |
| Default do `AI_SYSTEM_PROMPT` (`template_service.py`) | deploy do scheduler | clínicas sem prompt próprio (dev) |

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
STAGE=dev   # ou prod
export RDS_HOST=$(get /$STAGE/SUPABASE_DB_HOST) RDS_PORT=$(get /$STAGE/SUPABASE_DB_PORT) \
       RDS_DATABASE=$(get /$STAGE/SUPABASE_DB_NAME) RDS_USERNAME=$(get /$STAGE/SUPABASE_DB_USER) \
       RDS_PASSWORD=$(get /$STAGE/SUPABASE_DB_PASSWORD)
API_KEY=$(get /$STAGE/SCHEDULER_API_KEY)
URL=$(aws cloudformation describe-stacks --stack-name clinic-scheduler-infra-$STAGE \
      --query "Stacks[0].Outputs[?contains(OutputKey,'ServiceEndpoint')].OutputValue" --output text)
```

Escrita em **prod** (script com `--aplicar`, `PUT`, deploy) só com autorização
explícita do André.

## 1. Prompt no banco

```bash
cd scheduler
python -m src.scripts.corrige_prompt_areas             # simula: mostra o diff por clínica
python -m src.scripts.corrige_prompt_areas --aplicar   # grava
python -m src.scripts.corrige_prompt_areas             # segunda vez: "já corrigido" em todas
```

Saídas possíveis por clínica:

- `aplicado` + diff: o bloco `3. ÁREAS` foi trocado.
- `já corrigido`: nada a fazer.
- `!! o bloco esperado NÃO está neste prompt`: alguém editou o bloco à mão.
  Não sobrescreve; conferir o texto antes.
- `Nenhuma clínica com AI_SYSTEM_PROMPT próprio`: o stage usa o default do
  código (é o caso de dev em 03/11/2026).

Conferir pelo que roda, não pelo exit code:

```bash
for c in clinicaessenciaestetica-9668a4 nobrelaser-sjc; do
  curl -s -H "x-api-key: $API_KEY" "$URL/clinics/$c/templates" \
  | python -c "import json,sys; t=[x for x in json.load(sys.stdin)['data'] if x['template_key']=='AI_SYSTEM_PROMPT'][0]['content']; print('$c', 'Nunca use present_options' in t)"
done
```

Esperado: `True` nas duas. E os dois prompts continuam idênticos entre si.

## 2. FAQ da Nobre (só prod)

O `INTIMATE_AREA_SCOPE` da Nobre cita "Virilha Comp. + ânus", área desativada
lá em 16/10/2026.

```bash
FAQ_ID=$(curl -s -H "x-api-key: $API_KEY" "$URL/clinics/nobrelaser-sjc/faq" \
  | python -c "import json,sys; print([x for x in json.load(sys.stdin)['data'] if x['question_key']=='INTIMATE_AREA_SCOPE'][0]['id'])")

curl -s -X PUT -H "x-api-key: $API_KEY" -H "Content-Type: application/json" "$URL/faq/$FAQ_ID" \
  -d '{"answer": "Não. A Virilha Completa e a região perianal são áreas diferentes, com valores diferentes. Se quiser incluir o perianal, é a área Perianal / Ânus, somada à Virilha Completa."}'
```

Conferir com o `GET` de novo: a resposta não contém mais "Virilha Comp.".

## 3. Deploy

Dev: `serverless deploy --stage dev --aws-profile dev-andre`.

Prod: a partir de uma worktree em `origin/main`, nunca da árvore de trabalho
(em 03/11/2026 um deploy saiu de uma branch de feature e subiu sem o fix).
Depois, provar que o pacote tem a descrição nova:

```bash
aws lambda get-function --function-name clinic-scheduler-infra-$STAGE-WhatsAppWebhook \
  --query Code.Location --output text | xargs curl -s -o /tmp/wh.zip
python -c "import zipfile; print('ONLY for dates' in zipfile.ZipFile('/tmp/wh.zip').read('src/services/ai_tools.py').decode())"
```

## 4. Conversa real

Num número de teste, com a clínica em política que responda a ele:

| Passo | Pessoa | Esperado do bot |
|---|---|---|
| 1 | "virilha" | Bolha do FAQ com Simples/Cavada/Completa (texto literal do FAQ) + uma pergunta em texto "qual delas você prefere?". **Sem botões.** |
| 2 | "cavada" | Pergunta em texto, uma linha, se quer incluir a região perianal. **Sem botões.** |
| 3 | "não" | Confirma Virilha Cavada, valor, e em seguida **datas em botões** (até 3) ou lista numerada (4+). |
| 4 | escolhe a data | Horários em botões/lista. |

Conferir também no `agent_history` da sessão (DynamoDB
`clinic-scheduler-infra-{stage}-conversation-sessions`) que `present_options`
só aparece a partir do passo 3.

## Casos negativos

- Pessoa cita duas áreas sem variante ("axilas e buço"): nenhuma explicação
  de variante, segue direto para confirmar e calcular.
- Pessoa já diz a variante ("virilha completa"): não repete a explicação dos
  tipos; só oferece perianal em texto.
