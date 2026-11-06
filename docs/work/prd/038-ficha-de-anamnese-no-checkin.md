# PRD - 038 Ficha de anamnese no check-in, compilada no modelo do termo

> Gerado na fase **Research** em 05/11/2026. Decisão final do mesmo dia:
> **um modelo compilado** (as páginas do TCLE exatamente como estão em
> produção, seguidas da ficha de anamnese Versão 03), um documento, uma
> assinatura. Use como input para a fase Spec. Substitui o PRD 014 (ficha por
> link no WhatsApp, app próprio, ZapSign), desenhado antes do check-in no iPad
> e da ClickSign (PRD 036).

---

## 1. Objetivo

Coletar a **Ficha de Anamnese - Epilação a Laser** (Versão 02, revisão
09/2026, `Documentos Laser/finha anamnese 2026.pdf`) no mesmo lugar e no mesmo
gesto em que hoje se assina o termo de consentimento: o check-in no iPad.
Quem ainda não tem o documento vigente responde as perguntas em telas curtas,
e a mesma assinatura de hoje (token no WhatsApp + manuscrita) fecha um PDF só,
que é o **TCLE atual, sem nenhuma frase alterada, seguido da ficha** com as
respostas. As respostas ficam gravadas e legíveis no painel, com os alertas
que mudam a conduta em destaque, e o PDF assinado vai para a pasta de
Documentos.

Perguntas que motivaram o PRD, respondidas em 05/11/2026:

1. A ficha pode estar no fluxo do check-in? **Sim**: mesmo gatilho, mesmas
   telas de dados, mesmo provedor do termo.
2. Pode ser a mesma assinatura? **Sim.** Três caminhos foram avaliados
   (seção 2.5) e o escolhido é o mais simples: **compilar os dois textos num
   único modelo da ClickSign**. É o pipeline de produção sem mudança
   estrutural, só com um modelo maior.

---

## 2. Contexto

### 2.1 O que já existe e o que este PRD aproveita

O PRD 036 (em produção desde 05/11/2026) entregou o provedor de assinatura
(`SignatureProvider`, ClickSign v3 por modelo `.docx` com variáveis, simulado
em dev), o bucket privado `-documentos` com URL assinada, o webhook com HMAC,
a Lambda `Consentimento` (lista, dispensa por sessão, registro em papel,
URLs), as telas de dados e de assinatura no iPad (`ConsentDataStep`,
`ConsentSignStep` em viewport cheio), responsável técnica e cidade por
clínica, selo na agenda, linha no popover e aba em Documentos.

Este PRD **não cria** app, link, domínio, provedor, bucket, Lambda nem
documento novo na ClickSign. Ele troca o modelo por um maior, acrescenta as
telas da anamnese no iPad e a leitura das respostas no painel.

### 2.2 A ficha, lida de ponta a ponta

Onze seções. Contagem sobre o PDF:

| Seção | Conteúdo | Sim/Não | Textos condicionais |
|---|---|---|---|
| Cabeçalho | nome, CPF, nascimento, telefone, e-mail | - | já vêm do check-in |
| 1 Queixa principal | o que motivou | - | 1 |
| 2 Histórico médico | gestante, amamentando, hormonal, pele, controlada, autoimune, imunossupressão, epilepsia, câncer, diabetes (+controlada), alergia | 12 | 6 |
| 3 Medicamentos | em uso, isotretinoína (+data), fotossensibilizantes, minoxidil | 4 | 4 |
| 4 Dermatológicas | tatuagem, peeling 30 d, cera/pinça 30 d, foliculite, herpes na área, silicone, procedimentos 30 d, queloide, ácidos, lesões ativas | 10 | 4 |
| 5 Hábitos | atividade física, fuma, álcool, acompanhamento médico | 4 | 2 |
| 6 Outras | já fez laser, reação, sessões/equipamento | 1 | 2 |
| 7 Observações | opcional | - | 1 |
| 8 Exposição solar e pele hoje | sol 2 semanas, bronzeada, sensibilizada | 3 | - |
| 9 Fototipo | autodeclaração I a VI | 1 escolha | - |
| 10 Declarações | 10.1 a 10.9 | - | - |
| 11 Assinaturas | cliente, responsável legal, profissional | - | - |

**Versão 03 da ficha = Versão 02 com três cortes, nada reescrito:**

- **Seção 8 sai.** Muda a cada sessão; vira a triagem por sessão, fase 2.
- **Item 10.8 sem marca**: "ZapSign®" vira "plataformas digitais legalmente
  reconhecidas".
- **Linha de assinatura da profissional sai** (decisão do 014: a RT é
  identificada, não assina). A linha da cliente e a do responsável legal
  também saem do corpo, porque a assinatura é a do documento inteiro, na
  última página, como já é no termo.

A seção 10 da ficha repete o que o TCLE já diz (veracidade, intercorrências,
LGPD, sessões avulsas, avisar mudanças). **Fica como está**: cada parte se
sustenta sozinha e a decisão é não editar texto.

O que resta para o iPad: **31 Sim/Não, 1 escolha de fototipo e ~20 textos
condicionais**, em 4 telas, com os textos aparecendo só quando a resposta é
"Sim". Estimativa de 3 a 4 minutos para quem responde "Não" na maioria.

### 2.3 O modelo compilado

Um único `.docx` gerado por script (como `docs/work/assets/036-tcle/gera_modelo.js`),
com duas partes:

1. **TCLE**: as 21 cláusulas e as 17 variáveis do modelo em produção,
   byte a byte. A cláusula 21 (assinaturas) passa para o fim do documento.
2. **Ficha de anamnese Versão 03**: cabeçalho com as mesmas variáveis de
   identificação, seções 1 a 7 e 9 com uma variável por resposta
   (`Sim`/`Não`) e por texto condicional (`-` quando vazio), seção 10 como
   está, e a identificação da responsável técnica.

Cerca de **80 variáveis** no total. O PDF é renderizado pela ClickSign a
partir do modelo, como hoje; nós não montamos PDF em lugar nenhum.

### 2.4 O que foi provado no sandbox da ClickSign (05/11/2026)

Envelope `d0ecd5ae` com dois documentos do mesmo modelo e uma signatária: o
widget mostrou "2 documentos para assinar" e "Assinar todos (2)", com os
mesmos quatro passos (`federal_data, agree, handwritten, whatsapp`). Fica
registrado como **caminho de volta** se um dia for preciso separar os
documentos. Com o modelo compilado, o fluxo é literalmente o de hoje.

Custo (confirmado nas páginas da ClickSign): cobrança **por documento
finalizado**, envelope não é cobrado. Compilado = 1 crédito por paciente
nova.

### 2.5 Os três caminhos avaliados em 05/11

| Caminho | Créditos | Texto | Versões | Código |
|---|---|---|---|---|
| Dois documentos no envelope | 2 | intacto | independentes | fechar por documento, `kind`, envelope multi-doc |
| Documento único redigido (anamnese + consentimento unificados) | 1 | **reescrito** (descartado por isso) | uma só | igual a hoje |
| **Compilado no modelo** (escolhido) | 1 | intacto | uma só | igual a hoje, mais variáveis |

O que o compilado aceita em troca da simplicidade, e que foi aceito:

- **Revisar qualquer uma das partes obriga todo mundo a assinar o documento
  inteiro de novo**, anamnese incluída. Hoje só há uma assinatura real em
  prod (de teste), então a transição é de graça; depois, cada revisão é uma
  rodada de assinaturas e créditos. Revisar com parcimônia e versionar.
- **"Pedir nova ficha" é "assinar de novo"**, termo junto.
- **Dispensar é dispensar tudo.**
- **PDF de 7 a 9 páginas no widget**: lê-se rolando, em tela cheia (já existe).

### 2.6 Por que não "ficha em casa, pelo link"

Mesma objeção do 014: link pedindo dado de saúde no WhatsApp parece golpe e
exige domínio, app e token próprios. No iPad a paciente já está identificada
e já assina ali. Preencher em casa pelo site (que já tem "Meus agendamentos"
com a mesma sessão) fica como evolução; as respostas gravadas antes da
assinatura deixam o backend pronto para isso.

---

## 3. Escopo

### Dentro

- **Modelo compilado** (seção 2.3) criado pela API nas contas de sandbox e
  produção; `CLICKSIGN_TCLE_TEMPLATE_KEY` trocada e `TCLE_VERSION` nova
  (ex.: `2026-12`). Sem versão, o check-in não pede nada, como hoje.
- **Telas da anamnese no iPad**, entre `consent-data` e a assinatura: (1)
  Queixa + Histórico médico, (2) Medicamentos, (3) Dermatológicas, (4)
  Hábitos + Outras + Observações + Fototipo. Toques grandes, "Sim"/"Não"
  obrigatórios sem default, textos só quando "Sim", progresso "2 de 4",
  gravação ao avançar.
- **Respostas gravadas antes de assinar** (JSONB `answers` no registro do
  documento, status `FILLING`), e só então o envelope.
- **Alertas** no painel, lista fixa de respostas que mudam a conduta:
  gestante, amamentando, isotretinoína, fotossensibilizantes, herpes na área,
  lesão ativa, tatuagem na área, peeling 30 d, cera/pinça 30 d, câncer,
  imunossupressão, queloide, epilepsia, diabetes não controlada. Exibidos,
  nunca interpretados.
- **Painel**: a linha "Termo" do popover vira "Documento", com os mesmos
  estados e ações e os alertas abaixo; a aba de Documentos mostra respostas
  por seção, alertas no topo, fototipo declarado com nota, PDF e trilha;
  botão "Pedir nova assinatura"; selo **DOCS** na agenda no lugar de TERMO.
- **Papel e dispensa**: como hoje, para o documento inteiro.
- **Menor de idade**: o responsável legal responde e assina, como hoje.
- `patients.skin_type` **não é escrito** pelo fototipo declarado.
- **Transição**: a assinatura de teste de prod na versão `2026-11` fica como
  histórico; a versão nova exige assinatura de todo mundo.

### Fora

- **Triagem por sessão** (a seção 8: sol ou bronzeamento nas últimas 2
  semanas, pele bronzeada, pele sensibilizada), a cada check-in, sem
  assinatura. Fase 2, PRD próprio. O prontuário já tem `tanned_skin`.
- Preencher em casa pelo site.
- Assinatura da profissional responsável.
- Bloquear sessão ou pagamento por alerta.
- O bot ler ou escrever qualquer coisa da anamnese.
- Migrar fichas de papel antigas.
- Qualquer edição no texto do TCLE ou da ficha além dos três cortes da
  seção 2.2.

---

## 4. Decisões (05/11/2026)

| # | Pergunta | Decisão | Por quê |
|---|---|---|---|
| 1 | Como juntar termo e ficha | **Compilado num único modelo**, textos intactos | 1 crédito; pipeline de hoje; sem edição de texto (seção 2.5) |
| 2 | Mesma assinatura | Sim: um documento, um widget, um token, uma manuscrita | É o fluxo de produção |
| 3 | Seção 8 da ficha | Sai da Versão 03; vira triagem por sessão (fase 2) | Cadência diferente do resto |
| 4 | Selo na agenda | **DOCS**, no lugar de TERMO | Um gesto, um selo |
| 5 | Quando pede | Sem documento vigente (versão) ou pedido pela profissional ("Pedir nova assinatura"). Sem validade automática | Com a seção 8 fora, o que resta quase não muda; renovar é decisão clínica |
| 6 | PDF | Modelo da ClickSign com variáveis, como hoje | Zero biblioteca de PDF; carimbo e trilha iguais |
| 7 | Ordem no iPad | Dados → anamnese (4 telas) → assinatura → pagamento | As respostas alimentam o PDF |
| 8 | Respostas sem assinatura | Ficam gravadas e os alertas já aparecem | Valor clínico não refém da etapa jurídica (014) |
| 9 | Onde os alertas aparecem | Popover e aba de Documentos; sem selo por alerta | A agenda já tem DOCS, CONFIRMADO e PENDENTE |
| 10 | Divergência com o cadastro | Nome atualiza; CPF, nascimento e e-mail só em campo vazio | Regra já em prod |
| 11 | Quem vê as respostas | Permissão `prontuario.ler` | Dado de saúde |
| 12 | Dispensa | Do documento inteiro, mesmos motivos | Não existe metade |

Todas as 12 linhas fechadas pelo André em 05/11/2026 (1 a 4 na decisão do
modelo compilado; 5 a 12 aprovadas como recomendadas). Também aprovados: a
lista de alertas da seção 3 e a renumeração das seções 9 e 10 da ficha para
8 e 9 no documento compilado.

---

## 5. Fluxo no iPad

```
appointment ─confirmar─▶ backend responde consentRequired (como hoje)
     │
     ├─ false ─────────────────────────────────────────────────▶ method
     │
     └─ true ─▶ consent-data ─▶ anamnese 1..4 ─▶ consent-sign ─▶ method
```

1. `consent-data` continua igual: identificação da signatária (ou do
   responsável) e escolha de uso de imagem.
2. Quatro telas da anamnese. Cada "Continuar" grava as respostas daquela
   tela (`PATCH` parcial num registro `FILLING`), para queda de rede ou
   "Recomeçar" não perder nada. Voltar é permitido até a assinatura.
3. Na última tela, `POST .../consent` como hoje, agora com as respostas
   completas: cria o envelope com o documento compilado, grava `SIGNING` e
   devolve o `signerId`. A tela de assinatura é a de hoje.
4. Assinado: `document_closed`/`auto_close` fecham como hoje (PDF no S3,
   hash). O polling confirma para o iPad.
5. Falha, desistência ou 5 min sem toque: "Chame a recepção"; o registro fica
   `SIGNING` com as respostas; a agenda mostra DOCS. Sem pular.
6. Reaproveitamento: `SIGNING` de até 24 h é reaproveitado se dados **e
   respostas** forem iguais; mudou algo, descarta e cria outro (regra atual,
   estendida às respostas).

---

## 6. Backend e dados

| Mudança | Detalhe |
|---|---|
| `patient_consents.answers` | JSONB com as respostas por chave estável (`gestante`, `isotretinoina_ultima_dose`, `fototipo`...). Vazio nas linhas antigas |
| `patient_consents.status` | ganha `FILLING` (respondendo, sem envelope) antes de `SIGNING` |
| Índice único em andamento | passa a cobrir `FILLING` e `SIGNING` |
| SSM | mesmas chaves de hoje: `TCLE_VERSION` nova e `CLICKSIGN_TCLE_TEMPLATE_KEY` do modelo compilado |
| `consentimento.py` | `inicia` recebe `answers` completas; rota de gravação parcial; validação por tela; `_mesmos_dados` compara respostas; alertas calculados de `answers` por lista fixa; `para_o_painel` devolve `answers` e `alertas` só com `prontuario.ler`; `renew` |
| `anamnese.py` (novo) | catálogo das perguntas (chave, texto, seção, tela, condicional, alerta), validação, variáveis do modelo |
| `clicksign_provider.py` | sem mudança estrutural; `_dados_do_modelo` ganha as variáveis da ficha |
| Rotas | `PATCH public/.../checkin/appointments/{id}/consent/answers` (parcial); `POST .../consent` como hoje; painel: `POST consents/{id}/renew` |
| Lambdas | nenhuma nova: `PublicBooking` e `Consentimento`. Stacks em 482/500 |

`answers` é a fonte para o painel e os alertas; o PDF é a prova, gerado a
partir de `answers`. Divergir é impossível.

---

## 7. Painel

- **Popover**: linha "Documento" (hoje "Termo") com estados e ações; abaixo,
  os alertas em vermelho, um por linha, só os "Sim" relevantes.
- **Documentos**: a aba "Termo de consentimento" vira "Termo e anamnese":
  alertas no topo, respostas por seção, fototipo declarado com a nota
  "autodeclarado; o tipo de pele do prontuário é o da profissional", PDF e
  trilha, botão "Pedir nova assinatura".
- **Agenda**: selo DOCS.
- **Configurações**: a seção "Responsável técnica e termo" mostra a versão
  vigente do documento.

---

## 8. Áreas e arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `docs/work/assets/038-modelo-compilado/` | criar | `gera_modelo.js` (TCLE intacto + ficha V03) e o `.docx` |
| `scheduler/src/services/anamnese.py` | criar | catálogo, validação, alertas, variáveis |
| `scheduler/src/services/consentimento.py` | modificar | `answers`, `FILLING`, comparação, alertas, renew |
| `scheduler/src/functions/public_booking/checkin.py` | modificar | rota de gravação parcial |
| `scheduler/src/functions/consent/router.py` | modificar | `answers`/alertas na resposta, `renew` |
| `scheduler/src/scripts/setup_database.py` | modificar | migrations idempotentes da seção 6 |
| `checkin/src/steps/Anamnese*.tsx` | criar | 4 telas |
| `checkin/src/pages/CheckinPage.tsx` | modificar | estados novos |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx`, `TermoPendenteBadge.tsx` | modificar | "Documento", alertas, DOCS |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.tsx` | modificar | respostas, alertas, renew |
| testes nos três apps | criar | cobertura dos fluxos |

---

## 9. Dependências e riscos

**Dependências**

- Aprovação da **Versão 03 da ficha** (os três cortes da seção 2.2) por quem
  assina pela clínica. Nada é redigido.
- Modelo compilado criado nas contas de sandbox e produção (script do 036).

**Riscos**

| Risco | Mitigação |
|---|---|
| Tempo no balcão na primeira visita (3 a 4 min a mais) | Só na primeira visita; condicionais; grava por tela; a recepção dispensa se precisar. Medir pelo tempo entre telas |
| Modelo com ~80 variáveis | Confirmado no sandbox em 05/11: 68 variáveis distintas aceitas e substituídas (seção 10) |
| Revisão de texto obriga todo mundo a assinar de novo | Aceito (seção 2.5); revisar com parcimônia e versionar |
| Dado de saúde sob a auth de hoje | `prontuario.ler`; nada no bot; bucket privado; dívida de auth por usuário sobe de prioridade |
| "Não" por pressa | Sem default, um toque por pergunta; a declaração de veracidade responsabiliza |
| Fototipo declarado virar parâmetro | Só em `answers`; nunca escreve `skin_type` (teste garante) |
| Documento longo no widget | Tela cheia já existe |

---

## 10. Antes da spec

1. ~~Aprovar a Versão 03 da ficha~~ Aprovada pelo André em 05/11/2026.
2. ~~Montar o `.docx` compilado e criar o modelo no sandbox~~ Feito em
   05/11/2026: `docs/work/assets/038-modelo-compilado/gera_modelo.js` gera
   `TCLE_anamnese_modelo_clicksign_2026-12.docx` (TCLE byte a byte, provado
   por assert no script de montagem, + ficha V03). Modelo no sandbox
   `1d2b35f6-e9a1-4657-8f76-248ac228ad95`, **68 variáveis distintas (80
   ocorrências)**, aceito sem erro. Envelope de teste `74a1dcd2` com todas as
   variáveis preenchidas: documento processado em ~1 s, widget abre normal,
   PDF de **8 páginas** (TCLE nas 5 primeiras, ficha da 6 à 8, assinatura no
   fim) com todas as variáveis substituídas. Consequência dos cortes: as
   seções 9 e 10 da ficha viraram 8 e 9. Falta só a **assinatura real** de
   um documento compilado, que fica para o E2E da implementação.
3. ~~Confirmar a lista de alertas e as linhas 5 a 12 da seção 4~~ Aprovadas
   pelo André em 05/11/2026.

---

## 11. Critérios de aceite

- [ ] Paciente sem documento vigente responde as 4 telas e assina com um
      token e uma manuscrita; o PDF traz o TCLE intacto e a ficha com as
      respostas.
- [ ] Sem `TCLE_VERSION`, o check-in não muda.
- [ ] As respostas ficam gravadas ao avançar cada tela e sobrevivem a
      "Recomeçar" dentro de 24 h; mudar uma resposta gera documento novo.
- [ ] Assinada, a aba de Documentos mostra respostas, alertas, PDF e hash; o
      PDF não tem URL pública.
- [ ] Os alertas aparecem no popover e na aba; nada é bloqueado.
- [ ] `skin_type` não muda com o fototipo declarado.
- [ ] Menor de idade: o responsável responde e assina.
- [ ] "Pedir nova assinatura" invalida a vigente e o próximo check-in pede de
      novo.
- [ ] Nenhuma tool do bot lê ou escreve as respostas.
- [ ] `pytest`, `npm run build`, `npm run lint` e `npm run test` verdes nos
      três apps; stacks abaixo de 500 recursos.

---

## 12. Referências

- PRD 036 e `scheduler/tests/integration/036-termo-de-consentimento.md`.
- PRD 014 (regras herdadas: alertas exibidos e não interpretados, respostas
  antes da assinatura, fototipo não escreve `skin_type`, RT não assina).
- PRD 012 (pasta de Documentos, `skin_type` só pela profissional).
- `docs/work/assets/036-tcle/gera_modelo.js` (como gerar o `.docx`).
- Sondagem de dois documentos: envelope `d0ecd5ae` no sandbox, 05/11/2026.
- Custo por documento: `pages.clicksign.com/funcionalidade-envios-multiplos`.

---

## Status

- [x] Pendente: decisões fechadas, ficha V03 aprovada e modelo compilado validado no sandbox em 05/11/2026
- [ ] Spec gerada: `spec/038-ficha-de-anamnese-no-checkin.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
