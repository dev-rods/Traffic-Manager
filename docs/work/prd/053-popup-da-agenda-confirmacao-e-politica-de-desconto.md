# PRD - 053 Pop-up da agenda: confirmação antes de mandar mensagem e política de desconto da clínica como padrão

> Gerado na fase **Research**. Use como input para a fase Spec.
> Fluxo: PRD → spec → PR → deploy **dev** → validação → deploy prod.

---

## 1. Objetivo

Dois ajustes no pop-up que abre ao clicar num agendamento na tela de agenda
(`AppointmentPopover`) e nos modais que ele abre:

1. **Nenhuma ação que fale com a paciente ou mexa em dinheiro executa no
   primeiro clique.** Hoje "Enviar link pelo WhatsApp" (cobrança) e "Enviar
   link dos documentos" disparam a mensagem na hora, e "Recebi em dinheiro" dá
   baixa no pagamento na hora. Toda ação crítica passa a mostrar o que vai
   acontecer e esperar um segundo gesto, com um "Voltar" ao lado, no mesmo
   padrão do cancelar (modal) e do "Pedir nova assinatura" (inline). Vale
   também para marcar falta e marcar confirmado: têm "Desfazer", mas o toast
   some e o estado já mudou na agenda que a equipe inteira vê.
2. **"Política da clínica" é o desconto padrão do agendamento manual.** Hoje o
   "Novo agendamento" nasce em "Sem desconto" e, ao salvar, o backend só aplica
   o desconto combinado com a paciente. Primeira sessão e faixas por quantidade
   de áreas, que o bot e o site aplicam, nunca entram num agendamento feito pela
   recepção. A opção "Sem desconto" continua existindo, mas como escolha
   explícita, não como padrão.

---

## 2. Contexto

### 2.1 Ações do pop-up hoje

| Ação | Onde | Efeito fora da tela | Confirmação hoje | Volta |
|---|---|---|---|---|
| Cancelar agendamento | `CancelAppointmentModal` | libera o horário | modal "Tem certeza" | não |
| Editar: data, horário, áreas, desconto, duração | `EditAppointmentModal` | muda preço/horário | resumo do PRD 043 (`ResumoDaAlteracao`) | editar de novo |
| Enviar / reenviar link de pagamento | `EnviarLinkDePagamento` | **WhatsApp + cobrança no Asaas** | **nenhuma** | não (mensagem enviada) |
| Enviar / reenviar link dos documentos | `EnviarLinkDosDocumentos` | **WhatsApp** | **nenhuma** | não |
| Recebi em dinheiro | `PagamentoDoAgendamento` | **pagamento PAID** (aqui e no Asaas) | **nenhuma** | estorno pelo Caixa |
| Pedir nova assinatura | `TermoDoAgendamento` | vigente vira REVOKED; sem mensagem | inline "Sim, pedir / Não" | não |
| Dispensar nesta sessão / Assinado em papel | `TermoDoAgendamento` | registro do termo | modal próprio | não |
| Marcar falta / Marcar confirmado / Desfazer | popover | status | nenhuma, por decisão (PRD 027) | "Desfazer" no toast |

As três linhas em negrito são o problema. A mensagem chega no celular da
paciente antes de a recepção perceber que clicou; em "Enviar link pelo
WhatsApp" a primeira vez também cria a cobrança no Asaas (`checkin.cobra`;
o reenvio reaproveita a cobrança viva). O botão fica `disabled` durante o
envio, então o clique duplo já não dispara duas, mas o clique errado dispara
uma.

O `EnviarLinkDePagamento` é o mesmo componente da linha do Caixa (prop
`compacto`): a confirmação vale lá também.

Falta e confirmado têm "Desfazer" no toast e, por isso, o PRD 027 decidiu
não pedir confirmação. O André reverteu essa decisão em 20/11/2026: o status
muda na agenda de todo mundo no clique, e o toast dura segundos. Passam a
confirmar como as demais. Os desfazeres ("Desmarcar falta", "Desfazer
confirmação") seguem sem confirmação: são a volta.

### 2.2 Desconto no agendamento manual hoje

- `DescontoField` tem três modos: **Sem desconto** (padrão), **Parceria
  (100%)**, **Personalizado** (% ou R$, PRD 050).
- No "Novo agendamento", `none` omite o bloco de desconto do payload. No
  backend, `AppointmentService.create_appointment` lê "ninguém opinou"
  (`discount_pct` 0, sem razão, sem centavos) e aplica **só**
  `desconto_personalizado.do_paciente`. Não chama `politica_de_desconto.decide`.
- `decide` é a regra da clínica (personalizado > maior entre primeira sessão e
  faixa 2/3 > nada) e é chamada pelo bot (`ai_tools`) e pelo site
  (`carrinho.cota`, `public_booking/create_appointment`). O painel é a única
  porta que não passa por ela: a mesma paciente, o mesmo carrinho, paga mais
  quando a recepção agenda do que quando agenda sozinha pelo site.
- O modal pré-seleciona "Personalizado N%" quando a paciente tem
  `custom_discount_pct`, para a atendente ver o total certo. É um remendo do
  mesmo buraco: a política inteira não aparece, só o pedaço combinado.
- A estreia (`isFirstVisit`) é mandada sempre pelo painel, como decisão da
  pessoa; `decide` hoje pergunta ao banco (`e_primeira_visita`). As duas
  respostas podem divergir num agendamento manual.
- Na edição, `descontoDoAgendamento` lê `first_session`/`tier_2`/`tier_3`
  (razões que só chegam pelo bot e pelo site) como "Personalizado N%". Mudar
  as áreas reaplica o mesmo percentual gravado, mesmo que a faixa de áreas já
  não valha.

---

## 3. Escopo

### Dentro do escopo

**Confirmação (item 1)**

- Um componente só de confirmação inline, em `components/ui`, com o texto do
  que vai acontecer, o botão da ação e um **"Voltar"**. Substitui o bloco
  ad hoc de "Pedir nova assinatura" e entra em:
  - **Enviar / reenviar link de pagamento**: "Mandar o link de cobrança de
    R$ X para (telefone) pelo WhatsApp?" Na primeira vez também diz que a
    cobrança será criada. O passo do CPF, quando o backend pede, vem depois da
    confirmação, não antes.
  - **Enviar / reenviar link dos documentos**: "Mandar o link do termo e da
    ficha para (telefone) pelo WhatsApp?" Com a data do último envio, quando
    houver.
  - **Recebi em dinheiro**: "Registrar R$ X recebido em dinheiro? O pagamento
    fica como pago aqui e no Asaas."
  - **Pedir nova assinatura**: mesmo texto de hoje, no componente novo.
- Enquanto a confirmação está aberta, o resto da linha não some: a pessoa vê o
  estado atual e o que vai mudar. "Voltar" fecha sem efeito.
  - **Marcar falta** e **Marcar como confirmado**: "Marcar falta de (nome)
    às (hora)?" / "Marcar (nome) como confirmada?" O "Desfazer" do toast
    continua existindo depois.
- Cancelar e Editar não mudam: já pedem confirmação (modal e resumo do 043).
- "Desmarcar falta" e "Desfazer confirmação" seguem diretos: são a volta.
- Testes dos componentes: a mutation **não** é chamada no primeiro clique; é
  chamada após confirmar; "Voltar" não chama. O Caixa herda a confirmação da
  cobrança pelo mesmo componente.

**Política de desconto (item 2)**

- `DescontoField` ganha o modo **"Política da clínica"**, primeiro da lista e
  padrão no "Novo agendamento". Ordem: Política da clínica · Sem desconto ·
  Parceria (100%) · Personalizado.
- Com "Política da clínica" selecionada, o modal mostra, ao vivo, o que a
  política decide para aquela paciente e aquelas áreas: "1ª sessão: 10%
  (-R$ 20,00)", "2-4 áreas: 15%", "combinado com a paciente: 12,5%" ou "sem
  desconto pela política". Para isso nasce `POST clinics/{clinicId}/quote`
  (`agenda.ler`), que chama `carrinho.cota` com telefone e devolve original,
  percentual, razão e final. A rota pública do site esconde a razão por ser
  aberta; esta é autenticada e mostra.
- Ao salvar com "Política da clínica", o painel **não manda** desconto; o
  backend decide. `create_appointment`, quando ninguém opinou, passa a chamar
  `politica_de_desconto.decide` (que já inclui o personalizado da paciente) em
  vez de só `desconto_do_paciente`. É a mesma função do bot e do site: as três
  portas gravam a mesma coisa.
- "Sem desconto" continua um botão como hoje, sem justificativa. Por baixo,
  o payload leva um marcador ("zero, de propósito": `discountPct: 0` com
  `discountReason: "none"`), porque "nada no payload" passa a significar
  "aplica a política". Invisível para quem usa.
- Primeira sessão: a política consulta o banco, como já faz
  (`e_primeira_visita`: conta só agendamentos `CONFIRMED`; cancelado e falta
  não são visita). O botão "Primeira visita" do modal segue marcando o
  registro, não o desconto. A cotação ao vivo mostra o que o banco decidiu, e
  o modal avisa quando o botão e a cotação discordam ("o sistema não considera
  esta a primeira sessão: já há sessão confirmada").
- Paciente com desconto combinado no cadastro: o modal abre em
  "Personalizado N%" já preenchido, como hoje. É o único caso em que a
  política não é o padrão, e grava o mesmo que a política gravaria (combinado
  vence tudo em `decide`). Sem combinado, abre em "Política da clínica".
- Edição: `descontoDoAgendamento` passa a ler `first_session`/`tier_2`/`tier_3`
  como "Política da clínica", exibindo a razão gravada. Com esse modo
  selecionado e áreas alteradas, o backend **decide de novo** ao salvar
  (`update_appointment_services` chama `decide` quando a razão gravada é da
  política); o resumo do 043 mostra "de 2-4 áreas: 15% para 5+ áreas: 20%".
  Parceria e personalizado continuam congelados como hoje.
- Popover e "Hoje" já rotulam `first_session`/`tier_2`/`tier_3`; nada muda.
  Relatórios filtram por `discount_pct > 0 OR discount_cents > 0`; a razão
  `none` com zero não entra, como hoje.
- Testes: contrato painel ↔ backend para `none`; `create_appointment` sem
  opinião grava a decisão de `decide`; estreia do painel vence a do banco;
  edição com razão da política re-decide; `quote` do painel devolve razão.

### Fora do escopo

- Trava no servidor contra reenvio em sequência (janela mínima entre links).
  A confirmação resolve o clique errado; o reenvio deliberado continua livre.
- Texto das mensagens de WhatsApp.
- Avisar a paciente quando a recepção remarca (PRD futuro, desde o 043).
- Mudar como o bot ou o site decidem o desconto. Eles já usam `decide`.
- Página "Descontos" (regras da clínica) e o desconto por paciente no cadastro.
- Reaplicar política em agendamentos antigos criados pelo painel sem desconto.

---

## 4. Decisões (confirmadas pelo André em 20/11/2026)

1. **Confirmação inline, não modal.** O pop-up é um cartão flutuante; abrir
   um modal por cima dele esconde o contexto que a pessoa precisa para
   confirmar. "Pedir nova assinatura" já faz inline e funciona. Cancelar fica
   em modal porque tem o desvio "vai remarcar?" (PRD 035).
   *Decidido: inline com "Voltar", um componente só para as seis ações.*
2. **"Recebi em dinheiro" entra na confirmação** mesmo tendo estorno pelo
   Caixa: a baixa vai ao Asaas e o estorno é outra ação, em outra tela, com
   rastro. Não é um "Desfazer" de toast.
   *Decidido: confirma.*
3. **Falta e confirmado também confirmam.** Têm "Desfazer" no toast, mas o
   status muda na agenda de todo mundo no clique. Decisão do André em
   20/11/2026, revertendo o PRD 027. Os desfazeres seguem diretos.
   *Decidido: confirma.*
4. **"Política da clínica" é o padrão na criação; na edição o padrão é o
   gravado.** Abrir "Editar" e ver o desconto trocado por baixo seria o bug do
   050 ao contrário.
   *Decidido: sim.*
5. **Com "Política da clínica" na edição, mudar áreas re-decide.** A faixa por
   quantidade de áreas depende das áreas; congelar o percentual gravado deixa
   a paciente com 15% de "2-4 áreas" em 6 áreas. O resumo do 043 mostra a
   troca antes de salvar. Alternativa: congelar e exigir que a recepção
   escolha de novo.
   *Decidido: re-decide, com o resumo mostrando de → para.*
6. **"Sem desconto" é um botão, sem justificativa.** A diferença entre "zero
   de propósito" e "ninguém decidiu" é interna ao payload (razão `none`) e não
   aparece na tela. Decidido pelo André: nada a pedir a quem usa.
   *Decidido: marcador interno, tela igual.*
7. **Primeira sessão é o banco quem diz.** Regra: existe sessão `CONFIRMED`
   anterior? Então não é a primeira. Cancelado e falta não contam como visita.
   É o que `e_primeira_visita` já faz; a política segue consultando-a, e o
   botão "Primeira visita" do modal não manda no desconto. Quando discordam, o
   modal avisa.
   *Decidido: banco, com a regra "diferente de cancelado ou falta".*
8. **Desconto combinado da paciente vem pré-preenchido e precede a política.**
   É o único caso em que "Política da clínica" não é o padrão. O gravado é o
   mesmo que a política gravaria, porque o combinado vence tudo em `decide`.
   *Decidido: pré-preenche "Personalizado N%", como hoje.*

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `frontend/src/components/ui/Confirmacao.tsx` (+ test) | criar | confirmação inline: texto, botão da ação (loading), "Voltar" |
| `frontend/src/pages/agenda/components/EnviarLinkDePagamento.tsx` (+ test) | modificar | confirmação antes de `enviar.mutate`; CPF depois da confirmação; vale no Caixa (`compacto`) |
| `frontend/src/pages/agenda/components/EnviarLinkDosDocumentos.tsx` (+ test) | modificar | confirmação antes de `enviar.mutate` |
| `frontend/src/pages/agenda/components/PagamentoDoAgendamento.tsx` (+ test) | modificar | confirmação antes de `receber.mutate` |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` (+ test) | modificar | "Pedir nova assinatura" usa o componente novo |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` (+ test) | modificar | "Marcar falta" e "Marcar como confirmado" confirmam inline antes de chamar o handler e fechar |
| `frontend/src/lib/desconto.ts` (+ test) | modificar | modo `policy`; padrão da criação vira a política; `payloadDoDesconto('none')` → `{discountPct: 0, discountReason: 'none'}`; `descontoDoAgendamento` lê razões da política; `textoDoDesconto` para o resumo |
| `frontend/src/pages/agenda/components/DescontoField.tsx` (+ test) | modificar | quarto modo, primeiro da lista; mostra a cotação ao vivo quando `policy` |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | modificar | padrão `policy` (ou `custom` pré-preenchido quando a paciente tem combinado); cotação via hook; aviso quando "Primeira visita" discorda da cotação; `policy` omite desconto no payload |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` | modificar | `policy` com áreas alteradas sinaliza o backend para re-decidir (forma exata na spec); resumo do 043 com de → para da política |
| `frontend/src/services/appointments.service.ts`, `hooks/useAppointments.ts` | modificar | `cotar(clinicId, body)` e `useCotacao` |
| `frontend/src/types/index.ts` | modificar | `Cotacao` e razão `none` |
| `scheduler/src/functions/appointment/quote.py` + `sls/functions/appointment/interface.yml` | criar | `POST clinics/{clinicId}/quote`, `agenda.ler`; registrar em `test_rotas_abertas_ao_staff` |
| `scheduler/src/services/appointment_service.py` | modificar | `create_appointment`: sem opinião → `decide` (banco decide a estreia); `update_appointment_services`: razão da política → re-decide |
| `scheduler/src/services/politica_de_desconto.py` | modificar | `RAZAO_NENHUM = "none"`; `RAZOES_DA_POLITICA` |
| `scheduler/src/functions/appointment/create.py`, `update.py` | modificar | aceitam `discountReason: "none"` com pct 0; recusam `none` com desconto > 0 |
| `scheduler/tests/unit/...` | modificar/criar | criação pela política, cotação do painel, contrato `none`, re-decisão na edição |
| `scheduler/tests/integration/053-popup-da-agenda.md` | criar | roteiro curl dev/prod |
| `scheduler/tests/postman/...` | criar | request da cotação |

Sem migration: `discount_reason` já é texto livre.

---

## 6. Dependências e riscos

- **Dependências:** `politica_de_desconto.decide`, `carrinho.cota`,
  `primeira_visita.e_primeira_visita`, permissão `agenda.ler` para a cotação.
- **Risco: mudar o padrão muda o preço de quem a recepção agenda.** É o
  objetivo, mas a recepção precisa ver o total antes de salvar: a cotação ao
  vivo no modal é parte obrigatória, não enfeite. Sem ela, o modal mostraria
  um total e o backend gravaria outro, que é o bug que o 050 corrigiu.
- **Risco: razão `none` nova em leitores antigos.** Popover, "Hoje" e
  relatórios só rotulam quando há desconto; `none` com zero não aparece.
  Conferir na spec se o Sheets sync grava a razão.
- **Risco: re-decidir na edição altera um preço já cobrado.** O aviso do 043
  ("já foi pago, mudar o valor não altera o que foi cobrado") já existe e
  cobre.
- **Risco: "Primeira visita" ligado e política sem 1ª sessão.** O botão
  marca o registro e o banco decide o desconto; podem discordar (sessão
  anterior confirmada e a recepção marcando estreia). O aviso no modal
  expõe a diferença antes de salvar; quem quiser o desconto escolhe
  "Personalizado".
- **Risco: confirmação em falta/confirmado muda um hábito.** São os botões
  mais usados do pop-up. O texto da confirmação tem de ser curto e o botão de
  confirmar, o primeiro no foco, para o custo ser um Enter.
- **Deploy:** backend primeiro (a rota de cotação precisa existir quando o
  painel subir pela Vercel). Em prod, a Vercel sobe no merge; o painel tolera
  404 na cotação mostrando "não foi possível cotar" e mantendo o salvar.

---

## 7. Critérios de aceite

- [ ] Clicar em "Enviar link pelo WhatsApp", "Enviar link dos documentos",
      "Recebi em dinheiro", "Pedir nova assinatura", "Marcar falta" e "Marcar
      como confirmado" não executa nada; mostra o texto do efeito, o botão da
      ação e "Voltar".
- [ ] "Desmarcar falta" e "Desfazer confirmação" seguem diretos.
- [ ] "Voltar" fecha sem chamada à API; confirmar chama uma vez.
- [ ] A linha do Caixa pede a mesma confirmação para a cobrança.
- [ ] "Novo agendamento" abre em "Política da clínica" e mostra, ao vivo, a
      razão e o valor que a política decide; muda ao trocar áreas ou paciente.
- [ ] Salvar com "Política da clínica" grava o mesmo que o bot gravaria para a
      mesma paciente e carrinho (teste com `decide`).
- [ ] "Sem desconto" grava `discount_pct 0` e `discount_reason 'none'`;
      nenhum desconto da política entra.
- [ ] Paciente com combinado: o modal abre em "Personalizado N%" preenchido.
- [ ] Primeira sessão pela política segue o banco (só `CONFIRMED` conta;
      cancelado e falta não); o modal avisa quando "Primeira visita" discorda.
- [ ] Editar um agendamento com `tier_2` e subir para a faixa 3 mostra no
      resumo "de 2-4 áreas para 5+ áreas" e grava o novo percentual.
- [ ] Editar sem tocar no desconto não muda o gravado.
- [ ] `POST clinics/{clinicId}/quote` listado em
      `test_rotas_abertas_ao_staff` com `agenda.ler`.
- [ ] pytest, vitest, build e lint verdes.

---

## 8. Referências

- PRD 027 (falta/confirmado sem confirmação, com desfazer), PRD 029 (link de
  cobrança), PRD 035 (cancelar vs remarcar), PRD 043 (resumo da alteração),
  PRD 048 (link dos documentos), PRD 050 (desconto por valor).
- `scheduler/src/services/politica_de_desconto.py` (docstring: por que a
  decisão mora num lugar só).
- `frontend/CLAUDE.md`, "Design Principles".

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/053-popup-da-agenda-confirmacao-e-politica-de-desconto.md` (20/11/2026)
- [x] Implementado em dev: 20/11/2026 (PR #226, layer 202; cotação em `POST appointments?simular=true` porque prod está em 494/500 recursos do CloudFormation; roteiro API verde, painel pendente)
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
