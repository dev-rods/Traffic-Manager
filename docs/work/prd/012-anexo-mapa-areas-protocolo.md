# Anexo — 012 · Mapa entre área do catálogo e área do protocolo

> **Este arquivo precisa ser revisado por quem aplica o laser antes de virar
> migration.** É ele que decide qual fluência a tela sugere para cada área.
>
> Montado por leitura dos PDFs em `Documentos Laser/` e **confirmado pelo André
> em 19/09/2026**. Uma única linha segue aberta, marcada com ⚠️.

O mapa existe porque os nomes **não** batem, e casar por aproximação é o defeito
de 16/09/2026 repetido num lugar onde ele queima pele. Área sem linha aqui não é
erro: significa "sem parâmetro sugerido", e a profissional digita.

---

## 1. Ligação direta (nome diferente, mesma área)

| Área do catálogo | `protocol_area_key` | Métodos disponíveis |
|---|---|---|
| Linha alba | `linha_alba` | SHR |
| Axilas | `axilas` | SHR, HR |
| 1/2 Braço | `meio_braco` | SHR |
| Lombar | `lombar` | SHR |
| Glúteo | `gluteos` | SHR |
| Coxas | `coxas` | SHR |
| 1/2 Perna | `meia_perna` | SHR |
| Virilha Simples | `virilha_simples` | SHR |
| Virilha Cavada | `virilha_cavada` | SHR |
| Virilha Completa | `virilha_completa` | SHR |
| Peitoral | `peitoral` | SHR |
| Abdômen | `abdomen` | SHR |
| Ombros | `ombros` | SHR |
| Buço | `buco` | SHR Stacking, HR |
| Mento/Queixo | `mento_queixo` | SHR Stacking, HR |
| Rosto Completo | `rosto_completo` | SHR Stacking |
| Pescoço | `pescoco` | SHR Stacking |
| Aréola | `areola` | SHR Stacking, HR |
| Mão ou Pé + Dedos | `mao_pe_dedos` | SHR Stacking |
| Perianal/ânus | `regiao_perianal` | SHR Stacking |
| Costeleta | `costeleta` | SHR Stacking, HR |
| Barba contorno | `barba_contorno` | SHR Stacking, HR |
| Nuca | `nuca` | SHR Stacking |
| Orelhas | `orelha_externa` | SHR Stacking |

---

## 2. Área composta → duas linhas no registro

| Área do catálogo | Abre em | Métodos |
|---|---|---|
| Virilha Completa + ânus | `virilha_completa` + `regiao_perianal` | SHR + SHR Stacking |
| Costas total + ombros | `costas` + `ombros` | SHR + SHR |
| Peitoral + abdômen | `peitoral` + `abdomen` | SHR + SHR |
| Barba Comp. + Pescoço | `barba_completa` + `pescoco` | SHR Stacking + SHR Stacking |

---

## 3. Áreas "inteiras" que usam o parâmetro da "metade"

Confirmado pelo André em 19/09/2026: o protocolo só tem a versão reduzida, e a
área inteira usa o mesmo parâmetro.

| Área do catálogo | `protocol_area_key` | Métodos |
|---|---|---|
| 1/2 Coxa | `coxas` | SHR |
| 1/2 Glúteo | `meio_gluteo` | SHR |
| Braço Completo | `meio_braco` | SHR |
| Perna Completa | `meia_perna` | SHR |
| Pernas Completas | `meia_perna` | SHR |
| 1/2 Virilha | `interno_virilha` | SHR, SHR Stacking, HR |

### `interno_virilha`: duas linhas do documento, uma região

Os PDFs escrevem a mesma região com dois nomes, conforme o método:

- **"Interno da virilha (lábios)"** — aparece no SHR
- **"Interno da virilha (reforço)"** — aparece no SHR Stacking e no HR

É a mesma área anatômica: "reforço" é a passagem complementar com outro método,
como as observações do HR deixam claro ("pode ser utilizado em áreas com pouca
resposta ao SHR, como (...) interno da virilha").

**Decisão minha, e vale conferir:** unifiquei numa chave só, `interno_virilha`,
com três linhas de método. O `protocol_area_name` de cada linha mantém a palavra
do documento, para a profissional reconhecer o que está lendo. Se `lábios` e
`reforço` forem regiões diferentes na prática de vocês, é só me dizer e eu
separo em duas chaves.

---

## 3b. Sem protocolo nos PDFs — parâmetro dado pelo André

⚠️ **Estas duas linhas não constam em nenhum dos dois documentos.** O parâmetro
veio do André em 19/09/2026 e está semeado como SHR Stacking, ponteira pontual:

| `protocol_area_key` | Fluência (J) | Stacks | Passadas |
|---|---|---|---|
| `glabela` | 4 | 2 | 2 |
| `nariz` | 4 | 2 | 2 |

**Aberto:** foi dado **um valor só**, e todas as outras linhas têm valor
diferente para pele branca e negra. Semeei **4 para as duas**, que erra para o
lado seguro na pele branca (as demais áreas de Stacking vão de 5 a 6 na branca).
Se a pele negra tiver de ser menor, me diga o número.

### `meio_gluteo` — só pele branca

| `protocol_area_key` | Método | Branca | Negra |
|---|---|---|---|
| `meio_gluteo` | SHR | 8 J / 7 kJ | **sem linha** |

Dado pelo André em 19/09/2026: mesma fluência do glúteo inteiro, metade da
energia (14 → 7). O raciocínio é claro e a energia escala com a área tratada.

**Aberto, e de propósito:** o 8 J é o valor da pele **branca** — na negra o
glúteo inteiro é 7 J. Copiar 8 para a pele negra seria sugerir **acima** do
protocolo dela, que é a direção que queima. Preferi não semear: na pele negra a
tela vai dizer "sem parâmetro sugerido" até alguém dar o número.

Pelo padrão das outras linhas seria 7 J / 6 kJ, mas esse número tem de vir de
quem aplica.

Registrado aqui com procedência explícita porque a tabela é referência clínica:
quem ler daqui a um ano precisa saber o que veio do PDF e o que veio de decisão
da clínica.

---

## 4. Áreas do protocolo que a clínica não vende

Ficam na tabela de referência e aparecem quando a profissional **adiciona uma
área manualmente**, mesmo sem estar no catálogo:

| `protocol_area_key` | Nome no documento | Métodos |
|---|---|---|
| `joelho` | Joelho | HR |
| `cotovelo` | Cotovelo | HR |
| `costas` | Costas | SHR |
| `barba_completa` | Barba completa | SHR Stacking |

---

## 5. Os valores, como serão semeados

79 linhas: 74 transcritas dos PDFs e 5 dadas pelo André — `glabela` e `nariz`
(nos dois tipos de pele) e `meio_gluteo` (só pele branca). Conferir antes do
deploy.

### SHR — Fluência (J) / Energia (kJ)

| `protocol_area_key` | Branca | Negra |
|---|---|---|
| `linha_alba` | 7 / 5 | 5 / 4 |
| `axilas` | 7 / 8 | 5 / 7 |
| `meio_braco` | 7 / 8 | 5 / 7 |
| `lombar` | 7 / 8 | 5 / 7 |
| `gluteos` | 8 / 14 | 7 / 12 |
| `meio_gluteo` ⚠️ | 8 / 7 | — sem linha |
| `coxas` | 8 / 14 | 7 / 12 |
| `meia_perna` | 8 / 14 | 7 / 12 |
| `virilha_simples` | 7 / 5 | 5 / 4 |
| `virilha_cavada` | 7 / 5 | 5 / 4 |
| `virilha_completa` | 7 / 6 | 5 / 5 |
| `interno_virilha` | 6 / 3 | 4 / 2,5 |  ← doc: "Interno da virilha (lábios)"
| `peitoral` | 7 / 8 | 5 / 7 |
| `abdomen` | 7 / 8 | 5 / 7 |
| `costas` | 7 / 8 | 5 / 7 |
| `ombros` | 7 / 8 | 5 / 7 |

### SHR Stacking — Fluência (J) / Stacks / Passadas

Stacks e passadas são **3 e 2 em todas as linhas dos PDFs**. `glabela` e `nariz`
são 2 stacks, por serem acréscimo do André e não dos documentos.

| `protocol_area_key` | Branca | Negra |
|---|---|---|
| `buco` | 6 / 3 / 2 | 5 / 3 / 2 |
| `mento_queixo` | 6 / 3 / 2 | 5 / 3 / 2 |
| `rosto_completo` | 6 / 3 / 2 | 5 / 3 / 2 |
| `pescoco` | 6 / 3 / 2 | 5 / 3 / 2 |
| `areola` | 6 / 3 / 2 | 5 / 3 / 2 |
| `mao_pe_dedos` | 6 / 3 / 2 | 5 / 3 / 2 |
| `regiao_perianal` | 6 / 3 / 2 | 5 / 3 / 2 |
| `interno_virilha` | 6 / 3 / 2 | 4 / 3 / 2 |  ← doc: "Interno da virilha (reforço)"
| `costeleta` | 6 / 3 / 2 | 5 / 3 / 2 |
| `barba_contorno` | 6 / 3 / 2 | 5 / 3 / 2 |
| `barba_completa` | 5 / 3 / 2 | 4 / 3 / 2 |
| `nuca` | 5 / 3 / 2 | 4 / 3 / 2 |
| `orelha_externa` | 5 / 3 / 2 | 4 / 3 / 2 |
| `glabela` ⚠️ | 4 / 2 / 2 | 4 / 2 / 2 |  ← fora dos PDFs, ver 3b |
| `nariz` ⚠️ | 4 / 2 / 2 | 4 / 2 / 2 |  ← fora dos PDFs, ver 3b |

### HR — Fluência (J) / Energia (kJ)

Energia é **1,0 em todas as linhas**, nos dois documentos.

| `protocol_area_key` | Branca | Negra |
|---|---|---|
| `buco` | 17 / 1,0 | 14 / 1,0 |
| `mento_queixo` | 17 / 1,0 | 14 / 1,0 |
| `areola` | 17 / 1,0 | 14 / 1,0 |
| `costeleta` | 17 / 1,0 | 14 / 1,0 |
| `barba_contorno` | 15 / 1,0 | 12 / 1,0 |
| `interno_virilha` | 15 / 1,0 | 12 / 1,0 |  ← doc: "Interno da virilha (reforço)"
| `axilas` | 17 / 1,0 | 14 / 1,0 |
| `joelho` | 15 / 1,0 | 12 / 1,0 |
| `cotovelo` | 17 / 1,0 | 14 / 1,0 |

---

## 6. Avisos que a tela mostra

Texto vindo dos documentos, palavra por palavra:

| Quando | Aviso |
|---|---|
| `tanned_skin` marcado | "Pele bronzeada: reduza a fluência. No SHR Stacking, reduza também os stacks e/ou as passadas. Nunca utilize o método HR, independentemente do fototipo." |
| HR + pele negra | "Utilize somente nas tonalidades mais claras de pele negra, fototipos IV e V, após avaliação criteriosa. Não utilize no fototipo VI." |
| HR, sempre | "Método mais agressivo, mais eficiente e mais dolorido, com maior risco de queimaduras." |
