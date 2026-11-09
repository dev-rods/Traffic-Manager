# PRD - 044 O bot nunca pede uma data sem ter consultado a agenda

> Gerado na fase **Research** em 09/11/2026. Use como input para a fase Spec.
> Pedido do André, a partir de uma conversa da Nobre Laser: "não passou as
> datas como opção".
>
> Nomes e telefones das conversas ficam fora deste documento; o rastro real
> está nos logs e no `message-events`, e as conversas citadas estão
> identificadas por data e hora.

---

## 1. Objetivo

Quando a conversa chega na etapa de data, as datas têm de vir de
`check_availability`. Hoje o modelo às vezes pergunta **"qual data fica melhor
pra você?"** sem nunca ter consultado a agenda - e aí a pessoa responde um dia
que não existe.

---

## 2. O caso que originou isto

Nobre Laser, 09/11/2026. Lead vinda do site, conversa inteira em 11 minutos:

| Hora (UTC) | Quem | O quê |
|---|---|---|
| 15:24 | ela | chega pelo site, quer valores e agendar |
| 15:26 | bot | apresenta a clínica, pergunta as áreas |
| 15:26 | ela | informa duas áreas |
| 15:27 | bot | explica os tipos de virilha, pergunta qual e se inclui perianal |
| 15:34 | ela | escolhe |
| 15:35 | bot | fecha o valor e pergunta: **"Agora me diz: qual data fica melhor pra você?"** |

Os logs do turno das 15:35 mostram as tools executadas: `list_areas`,
`calculate_discount`. **`check_availability` não foi chamada.** O modelo
escreveu a pergunta de data sozinho.

A conversa está parada nessa pergunta desde então.

### Por que isso é pior na Nobre

A Nobre concentra o atendimento em **cerca de uma data por mês** em São José
dos Campos. "Qual data fica melhor pra você?" convida a pessoa a escolher um
dia que quase certamente não existe - e a próxima mensagem do bot terá de
negar a data que ele mesmo pediu.

### Não é a primeira vez

Varredura de todas as mensagens de saída de produção (Essência e Nobre):

| Quando | Clínica | O que aconteceu |
|---|---|---|
| 19/10/2026 16:09 | Essência | "Qual data fica melhor para você?" sem consulta. Resposta dela: **"Já te respondi"**. Três dias depois: "obrigada, eu já fechei" - com a clínica, não com o bot |
| 09/11/2026 15:35 | Nobre | o caso acima |

Os outros casos que casaram com o padrão de busca são legítimos: listaram as
datas que a tool devolveu e **depois** perguntaram qual delas - que é o
comportamento correto.

Variante mais branda, no mesmo dia (09/11 02:36, Nobre): em vez de consultar,
o bot perguntou "Quer ver as datas disponíveis?" e só consultou depois do "Sim".
Custa um turno, não gera data inexistente. Entra na medição, não no bloqueio
(ver §7.3).

---

## 3. Por que acontece

### 3.1 O prompt já manda o contrário

A seção 4 do `AI_SYSTEM_PROMPT` (em produção, nas duas clínicas) diz:

> 4. DATA E HORÁRIO
> Chame check_availability e mostre as datas que voltarem.
> [...]
> SE check_availability NÃO RETORNAR NENHUMA DATA: [...] chame
> request_human_handoff com reason="sem_disponibilidade"

A instrução existe, é específica, e tem até a saída para o caso de agenda
vazia - que nunca roda, porque depende da tool que não foi chamada.

### 3.2 O roteador não força essa consulta - de propósito

`roteador.py` pré-carrega tools antes de o modelo escrever. O comentário no
código explica por que `check_availability` fica fora:

> Só entram aqui tools que respondem sem argumento. `check_availability` e
> `calculate_duration` dependem das áreas que a pessoa escolheu, que só existem
> na conversa - pré-carregá-las com argumento vazio devolveria o piso de 15
> minutos como se fosse a duração real.

A decisão está certa para o **começo** da conversa. O furo é o **depois**:
quando as áreas já estão definidas, nada obriga a disponibilidade a vir da
tool, e a regra fica só no prompt - que é pedido, não garantia.

### 3.3 A `proveniencia` não enxerga pergunta

`proveniencia.py` barra **afirmação** de data e horário sem respaldo de tool
(`fatos_de_agenda`), e já tem o mecanismo de refazer a resposta forçando a
consulta. Mas "qual data fica melhor?" não afirma data nenhuma: não há fato a
conferir, e o verificador aprova - com `tools=11` no log, no caso de 09/11.

É a mesma classe de erro que a proveniência resolve, do lado da **pergunta**.

---

## 4. A proposta

**Pedir uma data sem ter consultado a agenda passa a ser tratado como afirmar
uma data sem consultar: a resposta não vai, e o modelo refaz com a consulta
obrigatória.**

O mecanismo já existe e está em produção para o caso irmão
(`conversation_agent.py`, por volta da linha 853): o código devolve o turno ao
modelo com um "PARE" explícito e `forcar_proxima = True`, uma vez só, e segue
com o resultado. O novo guarda usa o mesmo caminho:

```
detectou pergunta de data aberta
  E nenhuma check_availability neste turno
  E as áreas já são conhecidas neste turno
    -> não envia; devolve ao modelo:
       "PARE. Você pediu uma data sem consultar a agenda. Chame
        check_availability e mostre as datas que ela devolver."
```

As áreas vêm do próprio turno: `calculate_discount` já roda com
`service_area_pairs` antes da mensagem de valor, como aconteceu nos dois casos.

---

## 5. Achado fora do escopo

A variável `{{collected_data_summary}}`, que o `AI_SYSTEM_PROMPT` renderiza na
linha 7, é preenchida com **string vazia** em `conversation_agent.py`
(`"collected_data_summary": ""`). A linha do prompt existe nas duas clínicas e
nunca carregou nada. Não tem relação com este bug e não entra neste PRD - fica
registrado para decidir se ganha conteúdo ou se sai do prompt.

---

## 6. Escopo

### Dentro

- Detectar pergunta de data/horário aberta sem `check_availability` no turno.
- Refazer uma vez, forçando a consulta, pelo mecanismo que já existe.
- Log próprio para medir a frequência (hoje não há como contar sem varrer
  mensagem por mensagem).
- Testes: o caso de 09/11; pergunta legítima **depois** da tool não pode ser
  barrada; conversa sem áreas definidas não é barrada.

### Fora

- Mudar o prompt. A instrução já está lá e é clara; o problema é não ser
  garantida.
- Forçar `check_availability` na pré-carga do roteador: continua sem os
  argumentos no início da conversa, pelo motivo do §3.2.
- O turno extra do "Quer ver as datas disponíveis?" (ver §7.3).
- A `{{collected_data_summary}}` vazia (§5).

---

## 7. Decisões para o André

### 7.1 O que fazer quando o guarda pega

| Opção | O que acontece | Risco |
|---|---|---|
| **A. Refazer forçando a consulta** (recomendada) | a pessoa recebe as datas reais, numa mensagem só | o modelo pode insistir; depois de uma tentativa, segue para B |
| B. Transferir para a especialista | sempre resolve, sempre custa uma pessoa | gasta atendimento humano num caso que a tool resolveria |
| C. Só registrar no log | mede o tamanho antes de agir | a pessoa continua recebendo a pergunta errada |

Recomendo **A**, com **B** como segunda tentativa - é exatamente o desenho que
já roda para a data afirmada sem respaldo.

### 7.2 Quando o guarda vale

| Opção | Alcance |
|---|---|
| **A. Só quando as áreas já são conhecidas no turno** (recomendada) | pega os dois casos reais; não interfere no começo da conversa, onde o prompt manda trazer de volta para as áreas |
| B. Qualquer pergunta de data sem consulta | pegaria também "quando abre a agenda?" no primeiro contato, onde o prompt manda **não** consultar ainda (§4 do prompt) |

Recomendo **A**. **B** brigaria com uma regra do prompt que está correta.

### 7.3 O turno extra ("Quer ver as datas disponíveis?")

Recomendo **só medir**, sem bloquear: não gera data inexistente, e numa clínica
com poucas datas pode até ser gentil. Se a medição mostrar que ele aparece
muito e derruba conversão, vira trabalho próprio.

---

## 8. Arquivos impactados

| Arquivo | Mudança |
|---|---|
| `scheduler/src/services/pergunta_de_data.py` (novo) | a regra: este texto pede data sem ter consultado? |
| `scheduler/src/services/conversation_agent.py` | o guarda no mesmo ponto do irmão (proveniência), refazendo uma vez |
| `scheduler/tests/unit/` | os dois casos reais, o legítimo e o do começo da conversa |

Nenhuma migration. Nenhuma mudança de prompt.

---

## 9. Critérios de aceite

- [ ] Mensagem que pede data sem `check_availability` no turno, com áreas já
      conhecidas, não é enviada: o modelo refaz com a consulta.
- [ ] Mensagem que pergunta "qual dessas datas?" **depois** da tool passa
      intacta.
- [ ] Pergunta de data no primeiro contato, sem áreas, não é barrada.
- [ ] Insistência após a segunda tentativa cai para a especialista.
- [ ] Log permite contar quantas vezes o guarda pegou, por clínica.
- [ ] `pytest` verde.

---

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Barrar pergunta legítima e calar o bot | O guarda exige as duas condições (sem consulta no turno E áreas conhecidas); teste específico para a pergunta legítima |
| Mais uma volta no laço = mais latência e custo | Uma volta, uma vez por mensagem, só no caso pego - o mesmo custo que o guarda irmão já aceita |
| O modelo insistir na pergunta aberta | Segunda tentativa vai para a especialista, como no §7.1 |

---

## 11. Referências

- `src/services/roteador.py` - o que é pré-carregado, e por que a
  disponibilidade não é.
- `src/services/proveniencia.py` e `conversation_agent.py` (~linha 853) - o
  guarda irmão, do lado da afirmação.
- PRD 020 (arquitetura de atendimento), PRD 030 (próximas N datas).

---

## Status

- [ ] Aprovado: §7.1, §7.2 e §7.3 pendentes
- [ ] Spec gerada
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
