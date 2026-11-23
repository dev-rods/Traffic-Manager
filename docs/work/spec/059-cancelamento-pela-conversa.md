# Spec - 059 Cancelamento pela conversa (partes A e B)

> Do PRD `prd/059-cancelamento-pela-conversa.md`, §3 A e B. A parte C (tarefa
> quando o bot não responde) fica para um PR próprio, por decisão do André em
> 23/11/2026.

## 1. Resumo

Duas mudanças pequenas no agente, nenhuma migração:

- **A.** Na janela do lembrete, `cancel_appointment` volta a existir para o
  modelo (com ou sem site) e o prompt manda cancelar direto quando o pedido é
  inequívoco. Remarcar continua pelo link quando há domínio.
- **B.** Depois de um `cancel_appointment` com sucesso, a resposta é o texto
  da clínica (templates `CANCELADO_PELA_CONVERSA` e
  `CANCELADO_PELA_CONVERSA_LINK`), no lugar da fala do modelo.

## 2. `src/services/cancelamento_pela_conversa.py` (novo)

Nos moldes de `orientacoes_pos_sessao`: `TEXTO`, `TEXTO_DO_LINK` (com
`{{link}}`), `TEXTO_SEM_LINK`, e `mensagem(template_service, clinic_id, link)`
que lê os templates da clínica, cai no padrão quando vazios ou quando o banco
falha, e monta cabeça + corpo. Sem link, o corpo é o convite a remarcar pela
conversa.

## 3. `src/services/lembrete.py`

- Saem `FERRAMENTAS_DE_SAIDA` e `ferramentas_a_remover`.
- `bloco_de_prompt`: com site, "CANCELAR ou não vou poder ir → cancele AGORA
  com cancel_appointment, sem perguntar; REMARCAR → link; áreas →
  alterar_agendamento". Sem site, cancela e remarca por aqui.

## 4. `src/services/conversation_agent.py`

- `_ferramentas_para` deixa de remover ferramentas; só a skill poda e o
  lembrete acrescenta `confirm_attendance`. `_nome_da_tool` sai (sem uso).
- Antes de `_build_outgoing`: se `efeito_cometido == "cancel_appointment"`,
  `final_text` vira `confirmacao_de_cancelamento(template_service, clinic_id,
  link)` e `pending_buttons = None`. Substitui, não anexa.

## 5. `src/services/skills/__init__.py`

`PACIENTE_COM_HORARIO` ganha o item 5: cancelar direto quando inequívoco,
uma pergunta só se ambíguo ou com mais de uma sessão, resposta em uma linha
porque a confirmação completa sai pelo código.

## 6. Testes

- `test_cancelamento_pela_conversa.py` (novo): mensagem com e sem link,
  template da clínica, banco fora; no agente, cancelou → confirmação padrão
  substitui a fala do modelo, sem domínio sem link, tool com erro não manda a
  confirmação.
- `test_lembrete_sobreposicao.py` e `test_lembrete_no_agente.py` ajustados:
  cancelar fica com site; o bloco manda cancelar aqui e remarcar pelo link.

## 7. Dev

Roteiro `scheduler/tests/integration/059-cancelamento-pela-conversa.md`,
smoke `smoke_059_dev.py` (scratchpad) na Premium de dev com telefones
fictícios, domínio setado só durante o smoke.

## Autorrevisão

- Fonte única: a decisão "cancelar vs. link" mora só no bloco do lembrete e na
  skill; nenhuma outra tool é filtrada. O texto mora num módulo e em dois
  templates, nunca no prompt.
- Falha fechada: template indisponível → texto padrão; tool com `error` →
  nada de confirmação.
- O que não muda: PRD 054 (desfecho), `confirm_attendance`, remarcar pelo
  link, `alterar_agendamento`.
