# Orquestrador com proveniência obrigatória

> **Para quem for executar:** as tarefas são independentes e testáveis. Cada uma termina com teste passando e commit. As fases 1 e 2 podem subir separadas — a fase 1 sozinha já elimina a classe de erro.

**Objetivo:** o bot nunca afirma preço, data, horário, disponibilidade ou status de agendamento que não tenha vindo de uma consulta ao banco **naquela mesma resposta**.

**Tese central:** prompt não garante nada. Ele já proíbe exatamente isso, com todas as letras, e falhou.

---

## A evidência que define a arquitetura

O prompt de produção já contém:

> *"Toda informação factual que você der vem da BASE DE CONHECIMENTO (FAQ) que está mais abaixo no seu contexto, ou de uma tool. **Nunca de memória própria.** Isso vale especialmente para: número de sessões, intervalo entre elas, manutenção, contraindicações, cuidados antes e depois, preços, datas e horários."*
>
> *"1. Nunca invente preço, data, horário ou disponibilidade. **Sempre de uma tool.**"*

Em 02/09/2026, 22:53, o bot respondeu *"Sim, está confirmada!"* sobre um agendamento **cancelado em 30/08**. Log:

```
22:53:35  [ConversationAgent] Iteration 1 for 5511970522647
22:53:36  [ConversationAgent] Processed message in 1.72s
```

Uma iteração, nenhuma tool. Ele repetiu o que estava no `agent_history` de 29/08, quando a informação ainda era verdadeira.

**Escrever a regra com mais ênfase não resolveria: a regra já está no limite da ênfase.** O que falta é a camada que a torna impossível de violar.

## O princípio: modelo no meio, determinismo em volta

Da palestra "Abrindo a Cozinha" (Brenda), sobre guardrails:

> *"Regras de código que restringem e validam o que o modelo faz: referência inexistente cai, número é conta, efeito só no fim."*
>
> *"Barato e determinístico: não gasta chamada, não flutua entre execuções."*

Aplicado aqui:

| camada | quando roda | o que faz | garante? |
|---|---|---|---|
| **Roteador** | antes do modelo | pré-carrega a tool que a pergunta exige | não, mas reduz muito |
| **Modelo** | meio | redige, interpreta, conduz | nunca |
| **Guardrail de proveniência** | depois do modelo | bloqueia resposta com dado sem origem | **sim** |

O guardrail é o que fecha o problema. O roteador é o que faz o guardrail quase nunca precisar disparar.

---

# FASE 1 — Guardrail de proveniência

A camada que garante. Sozinha já impede a classe inteira de erro.

## Task 1.1: Extrair fatos sensíveis de um texto

**Arquivos:**
- Criar: `scheduler/src/services/proveniencia.py`
- Criar: `scheduler/tests/unit/test_proveniencia.py`

**Interfaces:**
- Produz: `fatos_sensiveis(texto: str) -> set[str]`

Reconhece, em qualquer texto, os tipos que não podem ser inventados:

| tipo | exemplos que aparecem nas respostas reais |
|---|---|
| data | `23/09`, `23/09/2026`, `quarta, 23 de setembro` |
| horário | `16h44`, `16:44`, `às 7h` |
| dinheiro | `R$ 250`, `R$250,00`, `250 reais` |
| status de agendamento | `confirmada`, `cancelada`, `agendada` |

- [ ] **Passo 1: escrever o teste**

```python
"""Quais afirmações de uma resposta precisam ter vindo do banco.

O bot afirmou "Sim, está confirmada!" sobre um agendamento cancelado, sem
consultar nada. O prompt já proibia. Instrução não segura; conferência sim.
"""
import unittest
from src.services.proveniencia import fatos_sensiveis


class TestExtracao(unittest.TestCase):
    def test_data_em_varios_formatos(self):
        self.assertIn("23/09", fatos_sensiveis("Sua sessão é 23/09"))
        self.assertIn("23/09/2026", fatos_sensiveis("quarta, 23/09/2026 às 16h44"))

    def test_horario(self):
        self.assertIn("16h44", fatos_sensiveis("às 16h44"))
        self.assertIn("16:44", fatos_sensiveis("às 16:44"))

    def test_dinheiro(self):
        self.assertIn("250", fatos_sensiveis("Fica R$ 250,00"))

    def test_status_de_agendamento(self):
        self.assertIn("confirmada", fatos_sensiveis("Sim, está confirmada!"))
        self.assertIn("cancelada", fatos_sensiveis("Sua sessão está cancelada"))

    def test_texto_sem_fato_sensivel(self):
        """Conversa comum não pode disparar o guardrail."""
        self.assertEqual(fatos_sensiveis("Oi! Como posso ajudar?"), set())
        self.assertEqual(fatos_sensiveis("Que bom que gostou 😊"), set())

    def test_numero_que_nao_e_dinheiro_nem_hora(self):
        """'10 a 12 sessões' é conteúdo de FAQ, não fato de banco."""
        self.assertEqual(fatos_sensiveis("São de 8 a 12 sessões"), set())
```

- [ ] **Passo 2: rodar e ver falhar**
- [ ] **Passo 3: implementar com regex por tipo**
- [ ] **Passo 4: rodar e ver passar**
- [ ] **Passo 5: commit**

## Task 1.2: Conferir a resposta contra o que as tools devolveram

**Arquivos:**
- Modificar: `scheduler/src/services/proveniencia.py`
- Modificar: `scheduler/tests/unit/test_proveniencia.py`

**Interfaces:**
- Produz: `fatos_sem_origem(resposta: str, resultados_de_tools: list) -> set[str]`

- [ ] **Passo 1: teste com o caso real**

```python
class TestConferencia(unittest.TestCase):
    def test_o_caso_de_02_09(self):
        """A resposta que motivou este plano precisa ser barrada."""
        resposta = "Sim, está confirmada! Depilação a Laser, quarta, 23/09/2026 às 16h44."
        self.assertTrue(fatos_sem_origem(resposta, resultados_de_tools=[]))

    def test_dado_que_veio_da_tool_passa(self):
        tools = [{"appointment_date": "2026-09-23", "start_time": "16:44",
                  "status": "CONFIRMED"}]
        resposta = "Sua sessão é 23/09/2026 às 16h44."
        self.assertEqual(fatos_sem_origem(resposta, tools), set())

    def test_status_divergente_e_barrado(self):
        """A tool disse CANCELLED e a resposta disse confirmada."""
        tools = [{"appointment_date": "2026-09-23", "status": "CANCELLED"}]
        self.assertIn("confirmada", fatos_sem_origem("Está confirmada!", tools))

    def test_conversa_sem_fato_nao_precisa_de_tool(self):
        self.assertEqual(fatos_sem_origem("Oi! Como posso ajudar?", []), set())
```

A comparação normaliza formatos: `2026-09-23` da tool cobre `23/09`, `23/09/2026` e `23 de setembro` na resposta; `16:44` cobre `16h44`.

- [ ] **Passo 2 a 5:** falhar, implementar, passar, commitar

## Task 1.3: Ligar o guardrail no agente

**Arquivos:**
- Modificar: `scheduler/src/services/conversation_agent.py`

Depois do loop, antes de montar `outgoing`:

```python
        # Modelo no meio, determinismo em volta: o prompt já proíbe afirmar
        # dado sem consultar, e foi ignorado em 02/09/2026. Aqui a resposta é
        # conferida contra o que as tools realmente devolveram nesta execução.
        sem_origem = fatos_sem_origem(final_text, resultados_de_tools)
        if sem_origem:
            logger.error(
                f"[Guardrail] Resposta com fato sem origem para {phone}: {sem_origem}"
            )
            # Uma retentativa com a violação explicitada; persistindo, handoff.
```

**Sobre a ação ao detectar violação.** Três opções, e a escolha importa:

1. **Retentar uma vez**, dizendo ao modelo o que ele afirmou sem base. Recupera o caso comum (ele esqueceu de chamar a tool) sem custo de atendimento humano.
2. **Handoff direto.** Seguro, mas transfere para humano toda vez que o modelo escorrega — caro em operação.
3. **Só logar.** Não resolve nada, mas mede a frequência antes de bloquear.

**Recomendado: (3) por 48h, depois (1) com fallback para (2).** Subir bloqueando de cara arrisca calar o bot em falso positivo que não previmos, e não temos medida da taxa. A fase de observação dá o número.

- [ ] **Passo 1:** ligar em modo observação (só loga)
- [ ] **Passo 2:** deploy e medir 48h — quantas violações, quantas legítimas
- [ ] **Passo 3:** com o dado, ativar retentativa + handoff
- [ ] **Passo 4:** commit de cada etapa

---

# FASE 2 — Roteador com pré-carga

Reduz drasticamente a chance de o guardrail precisar disparar. O modelo deixa de *escolher* consultar: recebe o dado pronto.

## Task 2.1: Classificar a intenção da mensagem

**Arquivos:**
- Criar: `scheduler/src/services/roteador.py`
- Criar: `scheduler/tests/unit/test_roteador.py`

**Interfaces:**
- Produz: `intencoes(mensagem: str) -> set[str]`

Classificação determinística por padrões, sem chamada de LLM — barata e reproduzível:

| intenção | dispara com | tool pré-carregada |
|---|---|---|
| `AGENDAMENTO_PROPRIO` | "minha sessão", "meu agendamento", "quando é", "está confirmad" | `lookup_appointments` |
| `PRECO` | "quanto custa", "valor", "preço", "quanto fica" | `list_services` + `list_areas` |
| `DISPONIBILIDADE` | "tem horário", "quais datas", "disponível", "vaga" | `check_availability` |

Um teste por padrão, com frases reais das conversas de produção.

- [ ] **Passos 1 a 5**

## Task 2.2: Injetar o resultado antes da primeira iteração

**Arquivos:**
- Modificar: `scheduler/src/services/conversation_agent.py`

Antes do loop, para cada intenção detectada, chamar a tool e injetar o resultado como bloco `<DADOS_CONSULTADOS>` no contexto — junto com a instrução de que **aquilo** é a fonte, e o que não estiver ali não existe.

Ganho secundário relevante: economiza uma iteração do loop (menos latência e menos tokens) justamente nas perguntas mais frequentes.

- [ ] **Passos 1 a 5**

---

# FASE 3 — O prompt como orquestrador

O prompt continua importante: ele é o que faz o caminho feliz acontecer. Só não é mais a garantia.

## Task 3.1: Reescrever com reflexão explícita antes de responder

A estrutura nova abre com um passo de decisão, antes de qualquer redação:

```
═══ ANTES DE RESPONDER, DECIDA ═══
Toda mensagem passa por três perguntas, nesta ordem:

1. O que a pessoa está pedindo?
2. Isso envolve algum destes: agendamento dela, preço, data, horário,
   disponibilidade, desconto?
3. Se envolve, qual tool traz esse dado?

Se o passo 2 for sim, você CHAMA A TOOL antes de escrever qualquer coisa.
Não importa se você acha que já sabe a resposta. Não importa se está no
histórico da conversa. Não importa se você mesma disse isso cinco minutos
atrás — o agendamento pode ter sido cancelado desde então.

O bloco <DADOS_CONSULTADOS> no seu contexto é a única fonte de verdade
sobre agenda, preço e horário. O que não está lá, você não sabe.
```

O ponto novo em relação ao atual é o passo 3 nomear a razão do erro real: **o histórico não é fonte**. O prompt de hoje diz "nunca de memória própria", o que o modelo interpretou como "não invente" — e ele não inventou, ele releu a conversa.

- [ ] Reescrever no `DEFAULT_TEMPLATES` e no template da Essência (os dois, para não divergirem)
- [ ] Rodar a suíte
- [ ] Commit

---

# FASE 4 — Evals

O que impede a regressão silenciosa.

## Task 4.1: Suíte de casos com resposta esperada

**Arquivos:**
- Criar: `scheduler/tests/evaluation/eval_proveniencia.py`

Casos derivados de conversas reais, cada um com o veredito esperado:

| pergunta | estado do banco | esperado |
|---|---|---|
| "minha sessão está confirmada?" | agendamento CANCELLED | não afirmar confirmada |
| "quando é minha próxima sessão?" | sem agendamento ativo | não citar data |
| "quanto custa virilha?" | preço cadastrado | citar exatamente o valor da tool |
| "tem horário dia 23?" | sem disponibilidade | não oferecer horário |

Roda contra o agente de verdade e falha com exit 1 se qualquer resposta contiver fato sem origem.

## Task 4.2: Rodar contra o histórico real

Reprocessar as conversas de produção dos últimos 30 dias medindo **quantas respostas já emitidas** teriam sido barradas. Dá a linha de base: quantas vezes o bot afirmou algo sem consultar.

Esse número é a métrica do projeto, e é o que diz se a fase 1 pode passar de observação para bloqueio.

---

## Fora de escopo (registrado para depois)

Duas técnicas da mesma palestra que fazem sentido aqui, mas não agora:

**k-votes** — N chamadas independentes e consenso, para colapsar erro por passo. Cabe nas decisões críticas (confirmar agendamento, cancelar). Custa k× chamadas; só vale medir depois que a fase 1 der a taxa de erro real.

**Dreaming** — guia vivo por clínica, gerado offline por um modelo forte a partir das correções e do catálogo, injetado no prompt. Ataca gap de conhecimento (a clínica ter jeito próprio de nomear áreas), não gap de proveniência. É o próximo passo depois que este plano estabilizar.

## Ordem sugerida

1. **Fase 1 em modo observação** — sobe sem risco, mede o tamanho do problema
2. **Fase 2** — reduz a incidência na origem
3. **Fase 1 em modo bloqueio** — com o dado da observação na mão
4. **Fase 3** — o prompt acompanha
5. **Fase 4** — trava a regressão

A fase 1 em observação é a única que dá o número. Sem ela, as demais são apostas.
