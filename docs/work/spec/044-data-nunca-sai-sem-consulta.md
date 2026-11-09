# Spec - 044 O bot nunca pede uma data sem ter consultado a agenda

> Gerada em 09/11/2026 a partir de `prd/044-data-nunca-sai-sem-consulta.md`.
> Decisões do André: **§7.1 A** (refazer forçando a consulta, com transferência
> na segunda tentativa), **§7.2 A** (só quando as áreas já são conhecidas no
> turno), **§7.3 A** (o turno extra do "Quer ver as datas disponíveis?" só é
> medido, não bloqueia).

---

## 1. O que muda, em uma frase

Antes de a mensagem sair, se ela pede uma data **e** `check_availability` não
rodou neste turno **e** as áreas já são conhecidas, a mensagem não vai: o turno
volta ao modelo com a consulta obrigatória. Na segunda vez, uma especialista
assume.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/pergunta_de_data.py` | **novo** - a regra: este texto pede data sem oferecer nenhuma? |
| `scheduler/src/services/bot_policy.py` | novo motivo de handoff `MOTIVO_PEDIU_DATA_SEM_CONSULTA` + rótulo legível |
| `scheduler/src/services/conversation_agent.py` | registro das tools do turno; o guarda ao lado do irmão (proveniência) |
| `scheduler/tests/unit/test_pergunta_de_data.py` | **novo** - a regra, a partir dos casos reais |
| `scheduler/tests/unit/test_guarda_data_sem_consulta.py` | **novo** - o guarda no laço: refaz, insiste, transfere |

Nenhuma migration. Nenhuma mudança de prompt.

---

## 3. `pergunta_de_data.py`

```python
def pede_data_sem_consulta(texto) -> bool
```

Duas condições, nesta ordem:

1. **O texto não oferece nenhuma data nem horário.** O discriminador é
   `fatos_de_agenda(fatos_sensiveis(texto))` da `proveniencia` - o mesmo
   extrator que já decide o que é data e o que é horário no projeto. Lista de
   datas presente ⇒ a mensagem está oferecendo opções ⇒ **não** é o caso.
2. **O texto pede que a pessoa escolha ou proponha uma data.** Padrões
   conferidos contra as duas conversas reais (19/10 Essência, 09/11 Nobre) e
   contra os casos legítimos da mesma varredura.

Por que a ordem importa: *"Nossas próximas datas são 21, 22, 27 e 28 de
outubro. Qual dia fica melhor?"* casa com o padrão do passo 2 e é **correta**.
Quem a salva é o passo 1.

Não entra na regra: "Quer ver as datas disponíveis?" (decisão §7.3). Fica num
log próprio, para medir.

---

## 4. O registro das tools do turno

`conversation_agent` hoje acumula `respaldo_das_tools`, que **atravessa turnos**
(nasce de `session["respaldo_anterior"]`) e guarda resultados, não nomes. O
guarda precisa de duas respostas sobre **este** turno:

| Variável (local ao turno) | Verdadeira quando |
|---|---|
| `tools_do_turno` | conjunto dos nomes executados, na pré-carga e no laço |
| `areas_do_turno` | alguma tool executada recebeu `service_area_pairs` não vazio |

`areas_do_turno` é o que concretiza a decisão §7.2: as áreas escolhidas pela
pessoa só existem como argumento de tool (`calculate_discount`,
`calculate_duration`, `check_availability`). `list_areas` **não** conta - ela
devolve o catálogo da clínica, não a escolha de ninguém.

---

## 5. O guarda

No mesmo ponto em que a proveniência refaz a resposta (logo antes do bloco
`if inventado ...`), porque é a mesma decisão vista do outro lado:

```python
pediu_data = (pede_data_sem_consulta(texto_provisorio)
              and "check_availability" not in tools_do_turno
              and areas_do_turno)

if pediu_data and not ja_refez_data and not efeito_cometido:
    ja_refez_data = True
    # devolve o turno com "PARE ... chame check_availability"
    forcar_proxima = True
    continue
elif pediu_data:
    # insistiu: a mensagem não vai, uma especialista assume
```

- **Primeira vez:** refaz com `tool_choice={"type": "any"}`, que é o que
  `forcar_proxima` liga. Uma volta só, como nos guardas irmãos.
- **Segunda vez:** a resposta é substituída por uma frase que promete pessoa,
  não prazo, e `entrega_a_humano(session, MOTIVO_PEDIU_DATA_SEM_CONSULTA)`. É a
  decisão §7.1, com B como segunda tentativa.
- **`efeito_cometido`:** se o turno já gravou algo (agendamento, cancelamento),
  não refaz - a mesma guarda dos outros blocos, para não repetir efeito.

### Log

```
[DataSemConsulta] <phone>: pediu data sem consultar a agenda; refazendo
[DataSemConsulta] <phone>: insistiu; entregando para uma pessoa
[DataSemConsulta] <phone>: ofereceu ver as datas antes de consultar   # §7.3, só mede
```

O prefixo é único e carrega o telefone, que é o que permite contar por clínica
numa consulta do CloudWatch - hoje medir isso exige varrer mensagem por
mensagem no `message-events`.

---

## 6. Ordem de implementação

1. `pergunta_de_data.py` + teste da regra (casos reais primeiro, inclusive os
   legítimos que **não** podem casar).
2. Motivo novo em `bot_policy.py` + rótulo em `MOTIVOS_LEGIVEIS`.
3. `tools_do_turno` / `areas_do_turno` no `conversation_agent`.
4. O guarda, com os três logs.
5. Teste do laço: refaz uma vez; insiste ⇒ handoff; pergunta legítima passa;
   sem áreas não barra.
6. `pytest` completo; deploy em dev; prod só com aval do André.

---

## 7. O que esta spec deliberadamente não faz

- **Não mexe no prompt.** A instrução da seção 4 já está correta.
- **Não força `check_availability` na pré-carga.** No início da conversa ela
  não tem argumentos, e chamá-la vazia devolveria o piso de 15 minutos como se
  fosse duração real (comentário do `roteador.py`).
- **Não bloqueia o turno extra** do "Quer ver as datas disponíveis?" (§7.3).
- **Não toca** na `{{collected_data_summary}}` vazia (PRD §5).
