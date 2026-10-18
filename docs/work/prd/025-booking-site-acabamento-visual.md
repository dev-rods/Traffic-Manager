# PRD — 025 Booking-site: acabamento visual

> Gerado na fase **Research**. Use como input para a fase Spec.
> Origem: comparação do Rodrigo, em 18/10/2026, entre a página antiga (SalonSoft
> "Agende Online", a referência da task 009) e o site atual em produção.

---

## 1. Objetivo

Deixar o site com o acabamento da referência sem mudar o fluxo: mais
contraste, identidade da clínica visível em todas as etapas, calendário
compacto e ações principais fáceis de achar no celular.

## 2. Diferenças observadas (prints de 18/10/2026, celular)

| # | Referência | Atual | Efeito |
|---|---|---|---|
| V1 | Fundo branco, texto grafite com contraste alto | Fundo creme e texto secundário marrom-claro (`ink-500` #8a7757 sobre #faf9f6, ~4:1) | Página "lavada", com leitura cansativa no sol |
| V2 | Avatar + "Seja bem-vindo(a)" + nome da clínica em **todas** as etapas | Só na lista de serviços; nas etapas só há um logo pequeno no topo | A pessoa perde a referência de onde está agendando |
| V3 | Títulos em negrito, grafite, em frase normal ("Selecione o profissional") | Títulos em CAIXA ALTA, marrom e espaçados ("SELECIONE AS ÁREAS DE TRATAMENTO") | Parecem rótulos de formulário e não guiam |
| V4 | Calendário: faixa compacta com mês centralizado, dias em blocos pequenos (SEG/12) e selecionado em creme com destaque dourado | Grade de caixas grandes com borda, repetindo "out" em cada uma, e mês alinhado à esquerda | Ocupa a tela, tem ruído e pouco destaque no escolhido |
| V5 | Resumo em cartão com sombra suave, ícones de data e preço, e excluir em botão rosa | Cartão com borda marrom e texto solto | Menos hierarquia |
| V6 | "Continuar" verde em largura total | Botão pequeno à direita, que desabilitado fica verde-claro e parece quebrado | No celular, a ação principal fica escondida no canto |
| V7 | Acento creme/dourado + verde para confirmar | Acento terracota (checkbox, nota de desconto salmão) + verde | Três cores competindo; a terracota briga com o verde do desconto |
| V8 | Espaçamento enxuto no topo | `py-10` + "Voltar" + `gap-8`: o conteúdo começa no meio da tela | No celular, a primeira dobra é quase vazia |

## 3. Escopo

Só apresentação (`booking-site/src`): tokens de cor, componentes e layout.
Sem mudança de API, fluxo, textos de negócio ou testes de comportamento. Os
testes existentes devem continuar passando sem mudança de expectativa, exceto
pelo que for só de texto de cabeçalho.

Fora: logo/marca da plataforma no topo (a referência mostra a marca do
SalonSoft; aqui o topo é da clínica) e escolha de profissional (removida na
023).

## 4. Critérios de aceite

1. Texto secundário com contraste ≥ 4.5:1; nenhum texto marrom.
2. Avatar e nome da clínica aparecem na lista de serviços e em todas as
   etapas do agendamento.
3. Títulos de seção em frase normal, negrito, grafite.
4. Dias disponíveis numa faixa horizontal compacta (rolável quando não cabe),
   com mês centralizado, sem repetir o mês em cada dia; o escolhido em creme
   com destaque dourado.
5. "Continuar" em largura total no celular.
6. Acento único creme/dourado; verde só para ação principal e economia.
7. Sem rolagem horizontal da página em 375 px; alvos de toque ≥ 44 px.

## 5. Status

- [x] Spec gerada (`spec/025-booking-site-acabamento-visual.md`)
- [x] Implementado (2026-10-18; revisão visual em 375 e 1280 px, sem overflow nem erro de console)
- [ ] Deploy prod
