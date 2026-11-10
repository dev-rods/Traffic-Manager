# 045 Alterar uma sessão marcada é editar, nunca marcar outra - Integration

Quem já tem sessão e pede mudança (áreas, dia, hora) tem a sessão **editada**.
Três lugares mudam, e os três precisam ser conferidos:

| Lugar | Como muda | Vale para |
|---|---|---|
| Código (`ai_tools.py`, `availability_engine.py`, `skills`, `lembrete.py`, `roteador.py`, `estado_comercial.py`) | deploy do scheduler | todas as clínicas |
| `AI_SYSTEM_PROMPT` no banco | `src/scripts/insere_galho_sessao_marcada.py` | clínicas com prompt próprio (Essência e Nobre, em prod) |
| Default do `AI_SYSTEM_PROMPT` (`template_service.py`, bloco C) | deploy do scheduler | clínicas sem prompt próprio (dev) |

## Pré-requisitos

Os mesmos de `037-areas-em-conversa.md` (SSM `SUPABASE_DB_*` → `RDS_*`,
`SCHEDULER_API_KEY`, URL do stack). Escrita em **prod** só com autorização
explícita do André.

## 1. Artefato publicado

```bash
aws lambda get-function --function-name clinic-scheduler-infra-$STAGE-WhatsAppWebhook \
  --query Code.Location --output text | xargs curl -s -o wh.zip
python -c "import zipfile; z=zipfile.ZipFile('wh.zip'); r=lambda p: z.read(p).decode();
print('def _tool_alterar_agendamento' in r('src/services/ai_tools.py'),
      'def excluindo' in r('src/services/availability_engine.py'))"
```

Esperado: `True True`.

## 2. Prompt no banco

```bash
cd scheduler
python -m src.scripts.insere_galho_sessao_marcada             # simula
python -m src.scripts.insere_galho_sessao_marcada --aplicar   # grava
python -m src.scripts.insere_galho_sessao_marcada             # "já tem o galho" nas duas
```

Saídas por clínica: `+ 2b. SESSÃO JÁ MARCADA antes de 3. ÁREAS`, `já tem o
galho`, ou `!! sem a âncora '3. ÁREAS'` (prompt editado à mão: conferir antes).
Em dev: `Nenhuma clínica com AI_SYSTEM_PROMPT próprio` (usa o default).

## 3. Fixtures em dev (foi assim em 09/11/2026)

Clínica `clinicadepilacaopremium-3fbce9` (instanceId `3EE10BD907D64112121A96031B028C8A`,
política `ALL`). Dev não tinha data futura nem paciente com sessão:

```bash
C=clinicadepilacaopremium-3fbce9; S=<service_id>; AX=<area Axilas>; MP=<area 1/2 Perna>
curl -s -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  "$URL/clinics/$C/availability-rules" -d '{"rule_date":"2026-11-25","start_time":"16:00","end_time":"21:00"}'
# a sessão da paciente de teste (16:30, Axilas + 1/2 Perna) e uma vizinha logo depois (16:45)
curl -s -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" "$URL/appointments" \
  -d "{\"clinicId\":\"$C\",\"phone\":\"5511999990000\",\"fullName\":\"Paciente Teste 045\",\"serviceId\":\"$S\",\"date\":\"2026-11-25\",\"time\":\"16:30\",\"serviceAreaPairs\":[{\"serviceId\":\"$S\",\"areaId\":\"$AX\"},{\"serviceId\":\"$S\",\"areaId\":\"$MP\"}]}"
curl -s -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" "$URL/appointments" \
  -d "{\"clinicId\":\"$C\",\"phone\":\"5511999990001\",\"fullName\":\"Vizinha Teste 045\",\"serviceId\":\"$S\",\"date\":\"2026-11-25\",\"time\":\"16:45\",\"serviceAreaPairs\":[{\"serviceId\":\"$S\",\"areaId\":\"$AX\"}]}"
```

A vizinha às 16:45 é o que torna o caso real: sem excluir a sessão dela, 16:30
"não cabe".

## 4. Conversa (webhook `POST $URL/webhook/whatsapp`, payload de `tests/mocks/webhook/ai_flow_test.json`)

O bot agrupa mensagens por ~1 min antes de responder: ler o rastro depois disso
(`message-events`, pk `CLINIC#{clinic}#PHONE#{phone}`; tools no `agent_history`
da sessão).

| Passo | Pessoa | Esperado | Log |
|---|---|---|---|
| 1 | "gostaria de remarcar para fazer somente a axila" | pergunta "fica só axilas, 25/11 às 16:30 - é isso?"; após o sim, "atualizei: somente Axilas, 25/11 às 16:30" + preparo. **Mesma linha** (`version` sobe), uma só CONFIRMED | `[PreCarga] identificar_paciente, lookup_appointments` · `[Alteracao] áreas 'Axilas, 1/2 Perna' -> 'Axilas', horário mantido` |
| 2 | "passar para as 17:00 no mesmo dia?" | move a mesma linha | `[Slots] pediu 17:00 -> cabe` · `[Alteracao] movida 16:30 -> 17:00` |
| 3 | "quero OUTRA sessão separada, só 1/2 perna, mais tarde" → "18:00, pode confirmar" | segunda linha CONFIRMED, as duas pedidas | `book_appointment` com `segunda_sessao: true`; **sem** `book_appointment recusado` |

## Casos negativos

- `book_appointment` sem `segunda_sessao` para quem tem sessão futura →
  `{"error": "ja_tem_sessao_marcada", ...}` e nada gravado
  (`[Alteracao] <phone>: book_appointment recusado, sessão futura <id>`).
- Áreas novas que não cabem no horário atual → `{"error": "nao_cabe"}`, a
  sessão continua como estava, e o bot oferece o mais próximo no mesmo dia.
- Lead nova e paciente sem próxima sessão: `alterar_agendamento` não está nas
  tools; `lookup_appointments` não é pré-carregado.
- Durante o lembrete com site: `cancel_appointment` sai; `alterar_agendamento`
  fica (§7.3 A).

## Medição em prod

`[Slots] <phone>: pediu HH:MM em YYYY-MM-DD -> nao cabe` cruzado com
`appointments` do mesmo número no mesmo dia/hora: antes desta task, 2 dos 11
dos últimos 30 dias eram o próprio horário da pessoa. Depois, esse cruzamento
tem de dar zero.
