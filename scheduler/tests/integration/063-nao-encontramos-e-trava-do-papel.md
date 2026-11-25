# 063 - "Não encontramos" na página de documentos e trava no termo em papel

PRD: `docs/work/prd/063-nao-encontramos-e-trava-do-papel.md`. Só front
(`checkin/` e `frontend/`); nenhuma rota nova, sem Postman.

## Pré-requisitos

- `checkin-dev` / `checkin-prod` publicados pela CLI da Vercel
  (`checkin/CLAUDE.md`, "Deploy"); painel pela Vercel no merge.
- Em dev o `verify/send` devolve `devCode` na resposta, então o fluxo roda
  sem ler o WhatsApp. Celular: só o do André (dev manda WhatsApp de verdade).

## Casos

| # | Cenário | Esperado |
|---|---------|----------|
| 1 | Página de documentos, número confirmado SEM sessão futura confirmada | "Não encontramos sessão para este número. Confira o celular digitado ou fale com a recepção." + "Tentar outro número" (volta ao celular). Sem "Tudo certo", sem "Entrar de novo" no cabeçalho |
| 2 | Número com sessão e termo já assinado/em papel/dispensado | "Tudo certo, {nome}" como antes |
| 3 | Número com sessão e termo pendente | boas-vindas e termo, como antes |
| 4 | Painel, "Assinado em papel" (agenda, pasta do paciente, lista) | título "Termo assinado em papel - {nome}"; "Registrar" desabilitado até marcar "Confirmo que a paciente assinou o termo impresso e ele está na pasta."; cancelar desmarca |
| 5 | Registro em lote | inalterado (fora do escopo) |

## Resultado

- dev (25/11, checkin-dev): caso 1 no navegador automatizado (Playwright,
  scratchpad `pw/docs_dev.mjs`) com o celular do André e o agendamento de
  teste cancelado antes: `checkin/appointments` devolveu `[]`, tela "Não
  encontramos sessão para este número", "Tentar outro número" voltou ao
  celular. Casos 2 a 4 pelos testes unitários (checkin 38, painel 730).
- prod (25/11): `checkin-prod` publicado, bundle novo servido em
  `documentos.draclaradourado.com.br`; PR #256 mergeado, painel na Vercel
  com o texto da trava no bundle.
- Caso de origem (Essência, paciente de final 1532): continua com o registro
  em papel indevido; regularizar pelo painel ("Pedir nova assinatura" e
  reenviar o link).
