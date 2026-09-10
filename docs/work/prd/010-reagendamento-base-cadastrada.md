# 010 - Agendamento de pacientes já cadastrados (campanha mensal)

**Status:** plano, aguardando aprovação
**Data:** 09/09/2026

## Problema

Todo início de mês a clínica dispara, pelo painel (Pacientes → seleção → Disparar
mensagem), um aviso às pacientes sem agendamento futuro com as datas de laser já
abertas. Dali em diante tudo é manual: a pessoa pergunta horários, a atendente
confirma as áreas, passa os horários, a pessoa escolhe, a atendente fecha e manda
as recomendações.

É o mesmo trabalho que o bot já faz para leads da landing page, feito à mão para a
base inteira.

## Diferenças em relação ao fluxo de lead

| | Lead (hoje) | Paciente cadastrado (novo) |
|---|---|---|
| Boas-vindas | sim | **não** - a conversa já começou com o disparo |
| Preço | anunciado no fluxo | **só se perguntarem** |
| Dados pessoais | pede nome, CPF, nascimento | **já temos** - nunca pergunta |
| Áreas | descobre do zero | **propõe as da última sessão** e confirma |
| Datas | qualquer disponível | **as datas da campanha** |
| Encerramento | recomendações | recomendações (igual) |

## Decisão de arquitetura: nem 1 nem 2, mas o meio

A pergunta era entre (1) um orquestrador novo e (2) enfiar os dois fluxos no
prompt atual e deixar o modelo se localizar. A opção 2 é arriscada pelo motivo
certo: o modelo **inferindo** em que fluxo está pode trocar de fluxo no meio da
conversa, e o erro aparece como "o bot pediu meu CPF de novo".

Mas a opção 1 cobra caro em outro lugar. As regras de agendamento - disciplina de
tools, proveniência, descontos mutuamente exclusivos, formato dos horários - não
mudam entre os dois fluxos. Duplicadas em dois prompts, elas divergem na primeira
alteração e ninguém percebe: é o modo de falha que mais custou nesta base.

**Proposta: um orquestrador só, com o modo decidido em CÓDIGO e injetado como
bloco de contexto.** O modelo não escolhe nada - ele recebe, já resolvido, um
bloco dizendo em que fluxo está e o que muda. É exatamente o mecanismo que já
existe para `single_service_hint`, `discount_context` e o bloco de calendário.

Isso elimina o risco da opção 2 (o modelo não infere) sem pagar o preço da
opção 1 (uma fonte só para as regras comuns).

```
AI_SYSTEM_PROMPT  (regras comuns: tools, proveniência, descontos, formato)
   + bloco do modo  ← decidido em código a partir da sessão
        LEAD          → boas-vindas, coleta cadastro, anuncia preço
        REAGENDAMENTO → sem boas-vindas, sem coleta, preço só se perguntarem
```

## O que de fato bloqueia hoje (o mais importante)

O prompt é a parte fácil. Duas guardas silenciariam o bot na base inteira:

**1. `bot_enabled` só liga para lead de landing page.** A clínica está em
`LEADS_ONLY`, e `should_bot_reply` exige `session["bot_enabled"]`, que só é
marcado quando existe lead com `source='landing-page'` (webhook/handler.py:285).
Paciente cadastrada não é lead. O bot ficaria mudo para todo mundo.

**2. `PAUSA_CHAT_ANTERIOR` é permanente e pegaria todas.** Na primeira vez que o
webhook vê alguém, ele confere se já havia conversa no WhatsApp antes de nós e
pausa para sempre (handler.py:320). Toda paciente cadastrada tem histórico com a
clínica. A regra está certa para lead - conversa que já era de gente - e errada
aqui, porque **nesta campanha quem começou a conversa fomos nós, de propósito**.

Sem tratar as duas, o fluxo novo não responde uma única mensagem, e a suíte
passaria verde - o mesmo desenho de falha do IAM que matou a agregação.

## Desenho

### Marcar no disparo, não adivinhar depois
O disparo em massa (`useSendBatchMessages` → `POST /send`) hoje não encosta na
sessão. Passa a, para cada paciente, abrir a sessão com:

- `bot_enabled = True` (destrava o `LEADS_ONLY`)
- `modo = "REAGENDAMENTO"`
- `campanha_expira_em` (epoch)
- **nenhuma pausa** - e a marca vale como "nós começamos", então
  `PAUSA_CHAT_ANTERIOR` não se aplica a esta conversa

A marca nasce do ato do disparo. Nada é inferido do texto da mensagem.

### Prazo da campanha
Resposta de três semanas depois não pode cair no fluxo de um mês que passou.
`campanha_expira_em` default 14 dias (parametrizável). Vencido, a sessão volta a
ser conversa comum e cai nas regras de hoje.

### Datas da campanha
As datas abertas vão na sessão no disparo (`datas_da_campanha`) e entram no bloco
de contexto. O bot não inventa data: oferece essas e confirma disponibilidade com
`check_availability`/`get_time_slots`, como já faz.

### Áreas da última sessão
`lookup_appointments` já existe mas só traz agendamentos ativos. Precisa de uma
consulta ao histórico para propor "as mesmas áreas da última vez?" - que é
literalmente o que a atendente faz hoje. Ou uma tool nova enxuta
(`ultimas_areas`), ou o dado no bloco de contexto do disparo. **Prefiro no bloco:**
é um dado só, conhecido no disparo, e evita mais um round-trip de tool.

### Dados pessoais
`book_appointment` exige `full_name`. Vem no bloco de contexto, do cadastro. O
bot passa para a tool sem nunca perguntar.

### Preço
`calculate_discount` continua sendo chamada antes de `book_appointment` - o preço
gravado tem de estar certo. O que muda é só o prompt não **anunciar** o valor a
menos que perguntem.

## O que é reaproveitado inteiro

Agregador de 68s, proveniência, pausa quando humano responde, calendário
determinístico, todas as 15 tools, o loop do agente e o webhook. Nada disso muda.

## Riscos

| Risco | Tratamento |
|---|---|
| Bot responde por cima da atendente | Pausa por resposta humana continua valendo, sem alteração |
| Disparo marca quem não devia | A marca é por paciente selecionada no painel, não por regra automática |
| Paciente responde após a campanha | `campanha_expira_em` |
| Bot oferece data fora da campanha | Datas na sessão + proveniência de datas já bloqueia resposta |
| Modo errado no meio da conversa | Impossível por construção: o modo é da sessão, não do julgamento do modelo |
| Marcar estreia em paciente antiga | Contagem automática já responde False para quem tem histórico |

## Fases

1. **Guardas** - `modo` e `bot_enabled` na sessão pelo disparo; `CHAT_ANTERIOR`
   passa a não se aplicar a sessão de campanha. Testado com mutação.
2. **Bloco de modo** no `_build_system_prompt` + texto do modo REAGENDAMENTO.
3. **Contexto do paciente** (nome, últimas áreas, datas da campanha).
4. **Painel** - o disparo passa a abrir a campanha; deixar visível que o bot
   assume dali em diante.
5. **Piloto no seu número antes da base.**

## Aberto para decisão

- Quantas datas por padrão (3?) e quem escolhe no disparo
- Prazo da campanha (sugiro 14 dias)
- Piloto: disparar para um punhado antes da base inteira
