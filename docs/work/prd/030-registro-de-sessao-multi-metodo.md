# PRD 030 — Registro de sessão: vários métodos por área + "Interno de Virilha"

**Data:** 2026-11-16
**Origem:** pedidos da clínica no projeto "Fluxo de registrar sessão do
paciente" (Notion, editado em 09/11).

## 1. Problema

O registro de sessão (PRD 012) aceita, para cada área, **um** método com
**um** conjunto de parâmetros. Na prática a profissional usa mais de um
método na mesma área na mesma sessão — ex.: *Axilas: SHR 8 J · 8 kJ, HR 20 J ·
1 kJ*. Hoje ela não consegue registrar isso: ou escolhe um, ou adiciona a
área duas vezes como se fossem duas áreas.

Além disso, ao adicionar área a tela só sugere as áreas do catálogo da
clínica. "Interno de Virilha" não é vendida (não pode virar área do
catálogo), mas é diferenciada na hora de aplicar e precisa ser registrável
sem digitar texto livre — e com o parâmetro do protocolo, que já existe
(`interno_virilha` em `protocolo_laser.py`).

## 2. O que muda

1. **1 área → N métodos → N parâmetros (1:1 com o método).**
   - Cada área vira um bloco com uma ou mais *linhas de método*. Cada linha
     tem método + os campos daquele método (como hoje).
   - "+ Adicionar método" no bloco cria uma linha nova na mesma área.
   - Cada linha pode ser removida quando há mais de uma; "Remover" no
     cabeçalho tira a área inteira.
   - Repetir o método na mesma área é permitido (ex.: duas passadas de SHR
     com fluências diferentes). Software não decide conduta — mesmo
     princípio de PRD 012.
   - Trocar o método de uma linha repõe a sugestão do protocolo naquela
     linha, como hoje.
2. **Histórico agrupa por área.** Lista e trilha de edições mostram
   `Axilas — SHR · 8 J · 8 kJ / HR · 20 J · 1 kJ` em vez de repetir a área.
3. **"Interno de Virilha" sempre sugerida.** Aparece entre as sugestões de
   "+ Adicionar área" (mesmo filtro por texto das áreas do catálogo), sem
   `area_id`, com `protocol_area_key = interno_virilha` — portanto com a
   sugestão de parâmetro do protocolo ao escolher o método. Não aparece
   duplicada se a clínica tiver uma área com esse mesmo nome.

## 3. Decisão de modelagem

**Sem migração.** `patient_session_applications` já é uma linha por
(área, método) e não tem restrição de unicidade por área; o backend já grava
e devolve N linhas para a mesma área. O agrupamento é de apresentação:
linhas consecutivas com o mesmo `area_name` + `protocol_area_key` formam um
bloco. A pergunta que justifica a tabela — *"que parâmetro usei na virilha
da Maria da última vez?"* — continua sendo um `WHERE`, agora com uma linha
por método.

Alternativa descartada: tabela filha `application_methods`. Exigiria
migração, reescrita do snapshot da trilha e de todas as leituras, sem ganho
de consulta.

## 4. Escopo

### Dentro
- Frontend: `AplicacoesField`, histórico (`HistoricoDeSessao`,
  `HistoricoDeEdicoes`), constante da área padrão, testes.
- Backend: teste de unidade garantindo que N métodos na mesma área passam
  pela validação e mantêm a ordem; nenhum código de produção muda.

### Fora
- Cadastrar "Interno de Virilha" no catálogo de áreas ou no mapa
  área→protocolo.
- Bot / WhatsApp (não lê prontuário).
- Mudar as tabelas de protocolo.

## 5. Riscos

- Registros antigos com a mesma área adicionada duas vezes passam a
  aparecer como um bloco com dois métodos — que é exatamente o que eles
  eram. Aceitável.
- A composta `Virilha Completa + ânus` já vira duas aplicações com nomes do
  protocolo diferentes (`Virilha completa`, `Região perianal`) → continuam
  dois blocos.

## 6. Critérios de aceite

- [ ] Na área "Axilas" consigo registrar SHR (8 J, 8 kJ) e HR (20 J, 1 kJ),
      salvar, reabrir e ver as duas linhas no mesmo bloco.
- [ ] Remover uma linha de método mantém a área; "Remover" tira a área toda.
- [ ] O histórico mostra a área uma vez, com os métodos separados.
- [ ] Digitando "int" ou "vir" em "+ Adicionar área" aparece "Interno de
      Virilha"; ao escolher SHR, a fluência sugerida do protocolo é
      preenchida conforme o tipo de pele.
- [ ] Registros existentes abrem e salvam sem alteração de dados.
- [ ] `npm run lint`, `npm run build`, `npm run test` e `pytest` do
      scheduler passam.

## Status

- Spec: `docs/work/spec/030-registro-de-sessao-multi-metodo.md`
- Implementado em 2026-11-16 (branch `feat/030-registro-sessao-multi-metodo`).
- Extra: o aviso do HR em `RegistroDeSessaoModal` passou a considerar qualquer
  linha da sessão, não só o primeiro método (com N métodos por área, o HR
  depois de um SHR ficava sem aviso).
