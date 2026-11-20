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
   padrão do cancelar (modal) e do "Pedir nova assinatura" (inline).
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

As ações reversíveis (falta, confirmado) ficam como estão: têm "Desfazer" no
toast, e a decisão do PRD 027 de não pedir confirmação ao que tem volta
continua valendo. Cerimônia em tudo treina a clicar sem ler.

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
- Cancelar e Editar não mudam: já pedem confirmação (modal e resumo do 043).
- Falta, confirmado e seus desfazeres não mudam (reversíveis, toast).
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
- "Sem desconto" vira escolha explícita: o painel manda `discountPct: 0` com
  `discountReason: "none"`. O backend grava a razão, e "ninguém opinou" fica
  reservado a payload sem desconto nenhum (bot e site sempre opinam).
- A estreia que a recepção marca vale para a política: `create_appointment`
  passa `is_first_visit` (quando veio booleano) para `decide` como
  `e_primeira`, em vez de deixar `decide` consultar o banco de novo. Uma
  resposta só para "é a primeira?".
- A pré-seleção de "Personalizado N%" pela paciente com combinado sai: a
  política já cobre, e a cotação ao vivo mostra "combinado com a paciente".
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

## 4. Decisões (para o André confirmar ou derrubar no spec)

1. **Confirmação inline, não modal.** O pop-up é um cartão flutuante; abrir
   um modal por cima dele esconde o contexto que a pessoa precisa para
   confirmar. "Pedir nova assinatura" já faz inline e funciona. Cancelar fica
   em modal porque tem o desvio "vai remarcar?" (PRD 035).
   *Proposta: inline com "Voltar", um componente só para as quatro ações.*
2. **"Recebi em dinheiro" entra na confirmação** mesmo tendo estorno pelo
   Caixa: a baixa vai ao Asaas e o estorno é outra ação, em outra tela, com
   rastro. Não é um "Desfazer" de toast.
   *Proposta: confirma.*
3. **Falta e confirmado seguem sem confirmação.** Têm "Desfazer" no toast e o
   PRD 027 decidiu assim. Pedir confirmação neles tiraria peso da confirmação
   de quem precisa.
   *Proposta: mantém.*
4. **"Política da clínica" é o padrão na criação; na edição o padrão é o
   gravado.** Abrir "Editar" e ver o desconto trocado por baixo seria o bug do
   050 ao contrário.
   *Proposta: sim.*
5. **Com "Política da clínica" na edição, mudar áreas re-decide.** A faixa por
   quantidade de áreas depende das áreas; congelar o percentual gravado deixa
   a paciente com 15% de "2-4 áreas" em 6 áreas. O resumo do 043 mostra a
   troca antes de salvar. Alternativa: congelar e exigir que a recepção
   escolha de novo.
   *Proposta: re-decide, com o resumo mostrando de → para.*
6. **"Sem desconto" grava `discount_reason = 'none'`.** É o que diferencia
   "a recepção decidiu que não tem desconto" de "ninguém decidiu" sem criar
   flag nova no payload. Alternativa: flag `applyClinicPolicy: false`.
   *Proposta: razão `none`.*
7. **A estreia marcada no painel vence a conta do banco dentro de `decide`.**
   Hoje o painel já manda `isFirstVisit` sempre, por decisão anterior; a
   política tem que seguir a mesma resposta ou a tela mostra "1ª sessão" e
   cobra sem o desconto.
   *Proposta: `create_appointment` passa o booleano para `decide`.*
8. **A pré-seleção de "Personalizado N%" sai.** Com a cotação ao vivo
   mostrando "combinado com a paciente: N%", manter a pré-seleção duplicaria a
   fonte: gravaria `custom` por um caminho e a política gravaria o mesmo
   `custom` por outro.
   *Proposta: sai.*

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `frontend/src/components/ui/Confirmacao.tsx` (+ test) | criar | confirmação inline: texto, botão da ação (loading), "Voltar" |
| `frontend/src/pages/agenda/components/EnviarLinkDePagamento.tsx` (+ test) | modificar | confirmação antes de `enviar.mutate`; CPF depois da confirmação; vale no Caixa (`compacto`) |
| `frontend/src/pages/agenda/components/EnviarLinkDosDocumentos.tsx` (+ test) | modificar | confirmação antes de `enviar.mutate` |
| `frontend/src/pages/agenda/components/PagamentoDoAgendamento.tsx` (+ test) | modificar | confirmação antes de `receber.mutate` |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` (+ test) | modificar | "Pedir nova assinatura" usa o componente novo |
| `frontend/src/lib/desconto.ts` (+ test) | modificar | modo `policy`; padrão da criação vira a política; `payloadDoDesconto('none')` → `{discountPct: 0, discountReason: 'none'}`; `descontoDoAgendamento` lê razões da política; `textoDoDesconto` para o resumo |
| `frontend/src/pages/agenda/components/DescontoField.tsx` (+ test) | modificar | quarto modo, primeiro da lista; mostra a cotação ao vivo quando `policy` |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | modificar | padrão `policy`; cotação via hook; sem pré-seleção pelo `custom_discount_pct`; `policy` omite desconto no payload |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` | modificar | `policy` com áreas alteradas sinaliza o backend para re-decidir (forma exata na spec); resumo do 043 com de → para da política |
| `frontend/src/services/appointments.service.ts`, `hooks/useAppointments.ts` | modificar | `cotar(clinicId, body)` e `useCotacao` |
| `frontend/src/types/index.ts` | modificar | `Cotacao` e razão `none` |
| `scheduler/src/functions/appointment/quote.py` + `sls/functions/appointment/interface.yml` | criar | `POST clinics/{clinicId}/quote`, `agenda.ler`; registrar em `test_rotas_abertas_ao_staff` |
| `scheduler/src/services/appointment_service.py` | modificar | `create_appointment`: sem opinião → `decide(..., e_primeira=do booleano)`; `update_appointment_services`: razão da política → re-decide |
| `scheduler/src/services/politica_de_desconto.py` | modificar | `RAZAO_NENHUM = "none"`; `RAZOES_DA_POLITICA`; `decide` aceita estreia já decidida |
| `scheduler/src/functions/appointment/create.py`, `update.py` | modificar | aceitam `discountReason: "none"` com pct 0; recusam `none` com desconto > 0 |
| `scheduler/tests/unit/...` | modificar/criar | criação pela política, estreia do painel, cotação do painel, contrato `none`, re-decisão na edição |
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
- **Risco: a estreia vinda do painel é o que a pessoa marcou.** Se marcar
  errado, a política dá 1ª sessão a quem não é. É o mesmo risco que o campo já
  carrega hoje para o relatório; a cotação mostra "1ª sessão: 10%" e dá chance
  de corrigir.
- **Deploy:** backend primeiro (a rota de cotação precisa existir quando o
  painel subir pela Vercel). Em prod, a Vercel sobe no merge; o painel tolera
  404 na cotação mostrando "não foi possível cotar" e mantendo o salvar.

---

## 7. Critérios de aceite

- [ ] Clicar em "Enviar link pelo WhatsApp", "Enviar link dos documentos",
      "Recebi em dinheiro" e "Pedir nova assinatura" não executa nada; mostra
      o texto do efeito, o botão da ação e "Voltar".
- [ ] "Voltar" fecha sem chamada à API; confirmar chama uma vez.
- [ ] A linha do Caixa pede a mesma confirmação para a cobrança.
- [ ] "Novo agendamento" abre em "Política da clínica" e mostra, ao vivo, a
      razão e o valor que a política decide; muda ao trocar áreas ou paciente.
- [ ] Salvar com "Política da clínica" grava o mesmo que o bot gravaria para a
      mesma paciente e carrinho (teste com `decide`).
- [ ] "Sem desconto" grava `discount_pct 0` e `discount_reason 'none'`;
      nenhum desconto da política entra.
- [ ] Paciente com combinado: a política mostra e grava o combinado.
- [ ] Estreia marcada no painel vale na política (1ª sessão aplicada mesmo que
      o banco diga que não é a primeira, e vice-versa).
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
- [ ] Spec gerada: `spec/053-popup-da-agenda-confirmacao-e-politica-de-desconto.md`
- [ ] Implementado em dev: (data)
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
