# Spec — 030 Registro de sessão: vários métodos por área + "Interno de Virilha"

- **PRD de origem:** `prd/030-registro-de-sessao-multi-metodo.md`

## 1. Resumo

Mudança de apresentação no frontend do prontuário: as aplicações (linhas
planas, uma por área+método, como já são no banco) passam a ser editadas e
exibidas agrupadas por área, com "+ Adicionar método" por área. A busca de
"+ Adicionar área" ganha a sugestão fixa "Interno de Virilha"
(`protocol_area_key = interno_virilha`, sem `area_id`). Backend sem mudança
de código de produção; ganha um teste de regressão.

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `frontend/src/lib/aplicacoes.ts` | Funções puras de agrupamento/edição da lista plana |
| `frontend/src/lib/aplicacoes.test.ts` | Testes das funções acima |

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `frontend/src/lib/protocolo.ts` | `AREAS_PADRAO` (Interno de Virilha) |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx` | UI por bloco de área com N linhas de método; sugestão padrão |
| `frontend/src/pages/documentos/components/AplicacoesField.test.tsx` | Casos novos (multi-método, remover linha, Interno de Virilha) |
| `frontend/src/pages/documentos/components/HistoricoDeSessao.tsx` | Exibir agrupado por área |
| `frontend/src/pages/documentos/components/HistoricoDeEdicoes.tsx` | Exibir agrupado por área |
| `scheduler/tests/unit/test_historico_de_sessao.py` | Teste: N métodos na mesma área passam por `valida_aplicacoes` mantendo ordem e campos |
| `TASKS_LOG.md`, PRD 030 | Status |

## 4. Ordem de implementação

1. `lib/aplicacoes.ts` + testes.
2. `AREAS_PADRAO` em `lib/protocolo.ts`.
3. `AplicacoesField` + testes.
4. Histórico (lista e trilha).
5. Teste backend.
6. lint / build / test / pytest; teste manual no dev.

## 5. Detalhes por arquivo

### `frontend/src/lib/aplicacoes.ts` (novo)

```ts
export interface BlocoDeArea {
  chave: string                     // `${area_name}|${protocol_area_key ?? ''}`
  area_name: string
  area_id: string | null
  protocol_area_key: string | null
  linhas: { indice: number; aplicacao: AplicacaoDeSessao }[]  // índice na lista plana
}

agrupaPorArea(aplicacoes): BlocoDeArea[]
```
- Agrupa por `area_name` + `protocol_area_key` preservando a ordem da
  primeira ocorrência. Linhas não consecutivas da mesma área (registros
  antigos) caem no mesmo bloco.
- `achata(blocos)` → lista plana na ordem dos blocos, `display_order`
  renumerado 0..n-1. Toda mutação do campo passa por ele, garantindo que o
  que vai pro backend fica contíguo por área.
- `adicionaMetodo(aplicacoes, chaveDoBloco, parametros, skinType)` → insere
  linha nova ao fim do bloco. Método pré-escolhido só se restar exatamente
  um método com sugestão do protocolo ainda não usado no bloco (mesma regra
  de "um só, já escolhe" de hoje); senão `null`. Parâmetros via `sugestao`.
- `removeLinha(aplicacoes, indice)` e `removeBloco(aplicacoes, chave)`.

### `frontend/src/lib/protocolo.ts`

```ts
/** Áreas que a tela sempre sugere, fora do catálogo: não são vendidas. */
export const AREAS_PADRAO = [
  { nome: 'Interno de Virilha', protocol_area_key: 'interno_virilha' },
] as const
```
Comentário explicando por que não é área do catálogo (PRD 030).

### `AplicacoesField.tsx`

- Renderiza `agrupaPorArea(aplicacoes)`: um `<li>` por bloco (borda como
  hoje — não é card dentro de card, as linhas internas são separadas por
  divisor, sem borda própria).
- Cabeçalho: nome da área + "Remover" (área inteira,
  `aria-label="Remover {área}"`, mantém o rótulo atual).
- Cada linha: `<select>` de método (mesmas opções/avisos de hoje) +
  `ParametrosDoMetodo` + "Remover método" (só com >1 linha,
  `aria-label="Remover {método||'linha'} de {área}"`). O aviso "O protocolo
  não traz X para esta área" fica por linha.
- Rodapé do bloco: botão texto "+ Adicionar método" (ghost, target ≥ 44px de
  altura útil com padding).
- `trocaMetodo` continua por índice na lista plana.
- Sugestões de "+ Adicionar área": `AREAS_PADRAO` que casam com o texto e
  cujo nome não exista (case-insensitive) no catálogo, depois as do
  catálogo; limite total 6. Escolher chama
  `adiciona(nome, null, protocol_area_key)`.
- `key` estável: `bloco.chave` para blocos; `indice` para linhas.

### `HistoricoDeSessao.tsx` / `HistoricoDeEdicoes.tsx`

- Usar `agrupaPorArea`; `<dt>` = área uma vez; `<dd>` = linhas
  `Método · resumo` unidas por " / " (lista) — "sem parâmetro registrado"
  mantido para linha sem método/valor.
- Extrair a formatação de uma linha para `resumoDaLinha(a)` em
  `lib/prontuario.ts` (hoje duplicada nos dois componentes).

### `scheduler/tests/unit/test_historico_de_sessao.py`

- `valida_aplicacoes` com Axilas/SHR(8, 8) + Axilas/HR(20, 1): duas linhas,
  mesma `area_name`, `display_order` 0 e 1, campos preservados.
- Interno de Virilha sem `area_id` e com `protocol_area_key='interno_virilha'`
  é aceita.

## 6. Testes manuais (dev)

1. Prontuário de uma paciente → Registrar sessão → Axilas: SHR 8/8,
   "+ Adicionar método" → HR 20/1 → salvar → histórico mostra
   `Axilas — SHR · 8 J · 8 kJ / HR · 20 J · 1 kJ`.
2. Editar: remover a linha HR → salvar → trilha mostra as duas versões.
3. "+ Adicionar área" → "vir" → "Interno de Virilha" → SHR → fluência
   sugerida conforme pele.
