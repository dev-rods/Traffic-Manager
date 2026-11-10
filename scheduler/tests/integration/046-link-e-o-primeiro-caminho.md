# 046 Para quem já é paciente, o link é o primeiro caminho - Integration

Em clínica com `custom_domain`, quem **já é paciente** e pede para marcar recebe
o link do site primeiro. O bot só agenda na conversa como segunda tentativa.
Tudo entra por código (deploy do scheduler): não há script de prompt.

| Peça | Onde | O que faz |
|---|---|---|
| `autoatendimento.link_de_agendamento` | `conversation_agent.py` | o link, a partir do `custom_domain`; vazio sem domínio |
| `skills.bloco_do_site(link)` | prompt das skills de paciente (nunca na de lead nova) | "PRIMEIRA TENTATIVA É O SITE" |
| `_recusa_sem_o_link` | `ai_tools.py` | `check_availability` e `book_appointment` devolvem `primeiro_o_link` até o bot ter escrito o link nesta conversa |
| `marca_link_enviado` / `link_ja_foi` | sessão (`link_enviado_em`, 7 dias) | só mensagem **do bot** com o link libera a segunda tentativa |
| `FLUXO_DA_CAMPANHA_PELO_LINK` | `prompt_da_campanha.adapta(prompt, link)` | campanha com domínio começa pelo link |

## Pré-requisitos

Os mesmos de `045-alterar-sessao-marcada.md`. Em dev nenhuma clínica tem
domínio: dar um `custom_domain` temporário à clínica de teste e **tirar no fim**
(o lembrete também passa a mandar o link enquanto ele existir).

## 1. Artefato publicado

```bash
aws lambda get-function --function-name clinic-scheduler-infra-$STAGE-WhatsAppWebhook \
  --query Code.Location --output text | xargs curl -s -o wh.zip
python -c "import zipfile; z=zipfile.ZipFile('wh.zip'); r=lambda p: z.read(p).decode();
print('primeiro_o_link' in r('src/services/ai_tools.py'),
      'def link_ja_foi' in r('src/services/autoatendimento.py'),
      'bloco_do_site' in r('src/services/conversation_agent.py'))"
```

Esperado: `True True True`.

## 2. Fixtures em dev (foi assim em 10/11/2026)

```sql
update scheduler.clinics set custom_domain = 'agendar.teste-046.invalid'
 where clinic_id = 'clinicadepilacaopremium-3fbce9';
-- paciente cadastrada: qualquer telefone com linha em scheduler.patients na clínica
-- lead nova: um telefone sem cadastro
```

## 3. Conversa (webhook `POST $URL/webhook/whatsapp`, payload de `tests/mocks/webhook/ai_flow_test.json`)

O bot agrupa mensagens por ~1 min: ler o rastro depois disso (`message-events`,
pk `CLINIC#{clinic}#PHONE#{phone}`; tools no `agent_history` da sessão).

| Passo | Pessoa | Esperado | Log |
|---|---|---|---|
| 1 | paciente cadastrada: "quero marcar mais uma sessão, quais dias vocês têm?" | uma frase dizendo que é pelo site + o link; **sem** áreas, **sem** datas | `[Link] <phone>: check_availability recusado, link ainda não foi` · `[Link] <phone>: link enviado` |
| 2 | "não consigo abrir o link, pode marcar por aqui?" | segue o agendamento na conversa (áreas, datas) | `[Link] <phone>: segunda tentativa - check_availability na conversa` |
| 3 | lead nova: "quero agendar axilas" | fluxo de sempre (boas-vindas, áreas) | nenhum `[Link]` |

Sessão da paciente após o passo 1: `session.link_enviado_em` preenchido.

## Casos negativos

- Clínica sem `custom_domain`: nada muda (bloco vazio, tools sem recusa).
- Link só no texto do disparo ou da recepção, não na fala do bot: as tools
  continuam recusando até o bot escrever o link.
- `link_enviado_em` com mais de 7 dias: o bot volta a mandar o link primeiro.

## Limpeza

```sql
update scheduler.clinics set custom_domain = null
 where clinic_id = 'clinicadepilacaopremium-3fbce9';
```
