# PRD - 038 Anamnese e consentimento num documento único, no check-in

> Gerado na fase **Research** em 05/11/2026; revisado no mesmo dia com a
> decisão de **documento único**. Use como input para a fase Spec.
> Substitui o PRD 014 (ficha por link no WhatsApp, app próprio, ZapSign).

---

## 1. Objetivo

Trocar o termo de consentimento de hoje (PRD 036, em produção) por **um
documento único**, de 7 a 9 páginas, que reúne a **ficha de anamnese**, o
**consentimento livre e esclarecido** e a **autorização de uso de imagem**,
com uma assinatura principal e as três finalidades individualizadas no texto.
A paciente responde a anamnese em telas curtas no check-in do iPad, e a mesma
assinatura de hoje (token no WhatsApp + manuscrita) fecha tudo. As respostas
ficam gravadas e legíveis no painel, com os alertas que mudam a conduta em
destaque, e o PDF assinado vai para a pasta de Documentos.

Perguntas que motivaram o PRD, respondidas em 05/11/2026:

1. A ficha pode estar no fluxo do check-in? **Sim**: mesmo gatilho, mesmas
   telas de dados, mesmo provedor do termo.
2. Pode ser a mesma assinatura? **Sim**, e melhor que isso: é o **mesmo
   documento**. O sandbox provou que um envelope assina vários documentos num
   fluxo só (seção 2.3), mas a ClickSign cobra **por documento finalizado**
   (seção 2.4), e a ficha repetia as declarações do termo. Um documento custa
   um crédito, tem uma versão e um PDF.

---

## 2. Contexto

### 2.1 O que já existe e o que este PRD aproveita

O PRD 036 entregou o provedor de assinatura (`SignatureProvider`, ClickSign v3
por modelo `.docx` com variáveis, simulado em dev), o bucket privado
`-documentos` com URL assinada, o webhook com HMAC, a Lambda `Consentimento`
(lista, dispensa por sessão, registro em papel, URLs), as telas de dados e de
assinatura no iPad, responsável técnica e cidade por clínica, selo na agenda,
linha no popover e aba em Documentos. Ligado em prod em 05/11/2026, com uma
assinatura real (de teste).

Este PRD **não cria** app, link, domínio, provedor, bucket nem Lambda. Ele
troca o conteúdo do documento, acrescenta as telas da anamnese no iPad e a
leitura das respostas no painel.

### 2.2 A ficha, lida de ponta a ponta

Ficha de Anamnese - Epilação a Laser, Versão 02, revisão 09/2026
(`Documentos Laser/finha anamnese 2026.pdf`). Contagem sobre o PDF:

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

**O que sai no documento único** (decisões de 05/11):

- **Seção 8 sai.** Ela muda a cada sessão; a ficha fica só com o que é
  estável. Vira a triagem por sessão, fase 2 (seção 3).
- **Seção 10 some como seção**: 10.1 (veracidade), 10.2 e 10.3
  (intercorrências e riscos), 10.5 (LGPD), 10.6 (sessões avulsas) e 10.9
  (avisar mudanças) já são cláusulas do termo. O editor unifica.
- **10.8 perde a marca** (ZapSign®): "plataformas digitais legalmente
  reconhecidas".
- **Assinatura da profissional sai** (decisão do 014: a RT é identificada,
  não assina).

O que fica: **31 Sim/Não, 1 escolha de fototipo e ~20 textos condicionais**,
em 4 telas no iPad, com os textos aparecendo só quando a resposta é "Sim".
Estimativa de 3 a 4 minutos para quem responde "Não" na maioria.

### 2.3 O que foi provado no sandbox da ClickSign (05/11/2026)

Envelope `d0ecd5ae` com dois documentos do mesmo modelo, uma signatária,
requisitos `agree` + `whatsapp` + `handwritten` nos dois: o widget mostrou "2
documentos para assinar" e "Assinar todos (2)", e `steps` devolveu os mesmos
`federal_data, agree, handwritten, whatsapp` de um documento só. Fica
registrado porque é o caminho de volta caso um dia os documentos precisem
voltar a ser dois. Com o documento único, o fluxo é literalmente o de hoje.

### 2.4 Custo

A ClickSign cobra **por documento finalizado**; o envelope não é cobrado à
parte (fontes: página "Envio de múltiplos documentos", página "Envelope" e
FAQ da API em `developers.clicksign.com`). Documento único = 1 crédito por
paciente nova, em vez de 2.

### 2.5 O que se aceita em troca do documento único

- **Qualquer revisão do texto obriga a assinar o documento inteiro de novo**,
  anamnese incluída. Com dois documentos, mudar o termo não refazia a ficha.
  Hoje só há uma assinatura real em prod (a de teste), então a transição é
  de graça; depois, cada revisão custa uma rodada de assinaturas e créditos.
- **"Pedir nova ficha" é "assinar de novo"**, consentimento junto. Coerente:
  a paciente reafirma tudo com o estado de saúde atual.
- **Dispensar é dispensar tudo.** Não há como dispensar a anamnese e manter
  o consentimento.
- **7 a 9 páginas no widget**: lê-se rolando, em tela cheia (já existe).

### 2.6 Por que não "ficha em casa, pelo link"

Mesma objeção do 014: link pedindo dado de saúde no WhatsApp parece golpe e
exige domínio, app e token próprios. No iPad a paciente já está identificada
e já assina ali. Preencher em casa pelo site (que já tem "Meus agendamentos"
com a mesma sessão) fica como evolução; as respostas gravadas antes da
assinatura deixam o backend pronto para isso.

---

## 3. Escopo

### Dentro

- **Documento único**, versão nova no SSM (`TCLE_VERSION`, que passa a
  identificar o documento inteiro) e modelo novo na ClickSign
  (`CLICKSIGN_TCLE_TEMPLATE_KEY` trocada). Sem versão, o check-in não pede.
- **Telas da anamnese no iPad**, entre `consent-data` e a assinatura:
  (1) Queixa + Histórico médico, (2) Medicamentos, (3) Dermatológicas, (4)
  Hábitos + Outras + Observações + Fototipo. Toques grandes, "Sim"/"Não"
  obrigatórios sem default, textos só quando "Sim", progresso "2 de 4",
  gravação ao avançar.
- **Respostas gravadas antes de assinar** (JSONB `answers` no registro do
  documento), PDF gerado por **modelo com variáveis**: uma por resposta e por
  texto condicional, além das 17 de hoje.
- **Alertas** no painel: lista fixa de respostas que mudam a conduta
  (gestante, amamentando, isotretinoína, fotossensibilizantes, herpes na
  área, lesão ativa, tatuagem na área, peeling 30 d, cera/pinça 30 d, câncer,
  imunossupressão, queloide, epilepsia, diabetes não controlada). Exibidos,
  nunca interpretados.
- **Painel**: a linha "Termo" do popover vira "Documento" com os mesmos
  estados e ações, mais os alertas; a aba de Documentos mostra as respostas
  por seção, os alertas no topo, o fototipo declarado com nota, o PDF e a
  trilha; botão "Pedir nova assinatura" (invalida a vigente para aquela
  paciente); selo **DOCS** na agenda no lugar de TERMO.
- **Papel e dispensa**: como hoje, para o documento inteiro.
- **Menor de idade**: o responsável legal responde e assina, como hoje.
- `patients.skin_type` **não é escrito** pelo fototipo declarado.
- **Transição**: a assinatura de teste de prod na versão `2026-11` fica como
  histórico; a versão nova exige assinatura de todo mundo, como qualquer
  revisão.

### Fora

- **Triagem por sessão** (sol, bronzeada, sensibilizada a cada check-in,
  sem assinatura). Fase 2, PRD próprio. O prontuário já tem `tanned_skin`
  por sessão.
- Preencher em casa pelo site.
- Assinatura da profissional responsável.
- Bloquear sessão ou pagamento por alerta.
- O bot ler ou escrever qualquer coisa da anamnese.
- Migrar fichas de papel antigas.
- Dois documentos por envelope (registrado na seção 2.3 como caminho de
  volta).

---

## 4. Decisões (05/11/2026)

| # | Pergunta | Decisão | Por quê |
|---|---|---|---|
| 1 | Um documento ou dois | **Um**, anamnese + consentimento + imagem, com uma assinatura e finalidades individualizadas no texto | 1 crédito; uma versão, um PDF, um selo; a ficha já repetia o termo |
| 2 | Quando pede | **Sem documento vigente** (versão) **ou pedido pela profissional** ("Pedir nova assinatura"). Sem validade automática | A seção 8 saiu, então o que resta quase não muda; renovar é decisão clínica, não de calendário |
| 3 | PDF | Modelo da ClickSign com variáveis, como hoje | Zero biblioteca de PDF; carimbo e trilha iguais |
| 4 | Ordem no iPad | Dados → anamnese (4 telas) → assinatura → pagamento | As respostas alimentam o PDF |
| 5 | Respostas sem assinatura | Ficam gravadas e os alertas já aparecem | Valor clínico não refém da etapa jurídica (014) |
| 6 | Onde os alertas aparecem | Popover e aba de Documentos; sem selo por alerta | A agenda já tem DOCS, CONFIRMADO e PENDENTE |
| 7 | Selo na agenda | **DOCS**, no lugar de TERMO | Um gesto, um selo |
| 8 | Divergência com o cadastro | Nome atualiza; CPF, nascimento e e-mail só em campo vazio | Regra já em prod |
| 9 | Quem vê as respostas | Permissão `prontuario.ler` | Dado de saúde |
| 10 | Dispensa | Do documento inteiro, mesmos motivos | Não existe metade |
| 11 | Seção 8 | Sai da ficha; vira triagem por sessão (fase 2) | Cadência diferente |
| 12 | Ordem do texto | Identificação → anamnese → consentimento → imagem → declarações → assinatura | As telas do iPad seguem a ordem do PDF |

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
   completas: cria o envelope com **um documento**, grava `SIGNING` e devolve
   o `signerId`. A tela de assinatura é a de hoje.
4. Assinado: `document_closed`/`auto_close` fecham como hoje (PDF no S3,
   hash). O polling confirma para o iPad.
5. Falha, desistência ou 5 min sem toque: "Chame a recepção"; registro fica
   `SIGNING` com as respostas; agenda mostra DOCS. Sem pular.
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
| SSM | mesmas chaves de hoje; `TCLE_VERSION` nova (ex.: `2026-12`) e `CLICKSIGN_TCLE_TEMPLATE_KEY` do modelo novo |
| `consentimento.py` | `inicia` recebe `answers` completas; rota nova de gravação parcial; validação por tela; `_mesmos_dados` compara respostas; alertas calculados de `answers` por lista fixa; `para_o_painel` devolve `answers` e `alertas` só com `prontuario.ler` |
| `anamnese.py` (novo) | catálogo das perguntas (chave, texto, seção, tela, condicional, alerta), validação, variáveis do modelo |
| `clicksign_provider.py` | sem mudança estrutural; só mais variáveis |
| Rotas | `PATCH public/.../checkin/appointments/{id}/consent/answers` (parcial); `POST .../consent` como hoje; painel: `POST consents/{id}/renew` ("pedir nova assinatura") |
| Lambdas | nenhuma nova: `PublicBooking` e `Consentimento`. Stacks em 482/500 |

`answers` é a fonte para o painel e os alertas; o PDF é a prova, gerado a
partir de `answers`. Divergir é impossível.

---

## 7. Painel

- **Popover**: linha "Documento" (hoje "Termo") com estados e ações; abaixo,
  os alertas em vermelho, um por linha, só os "Sim" relevantes.
- **Documentos**: a aba "Termo de consentimento" vira "Anamnese e
  consentimento": alertas no topo, respostas por seção, fototipo declarado com
  a nota "autodeclarado; o tipo de pele do prontuário é o da profissional",
  PDF e trilha, botão "Pedir nova assinatura".
- **Agenda**: selo DOCS.
- **Configurações**: a seção "Responsável técnica e termo" mostra a versão
  vigente do documento.

---

## 8. Áreas e arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `docs/work/assets/038-documento-unico/` | criar | `gera_modelo.js` e o `.docx` do documento único com variáveis |
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

- **Texto final do documento único**, aprovado por quem assina pela clínica:
  revisão jurídica (inclusive a cláusula 18 do termo atual, que tenta afastar
  responsabilidade por omissão do cliente e não elimina o dever profissional
  de avaliação), sem seção 8, sem marca de plataforma, sem assinatura da
  profissional, com versão e data no rodapé e na ordem da decisão 12. **É o
  bloqueio de entrada**: o modelo é gerado a partir dele.
- Modelo criado nas contas de sandbox e produção (script do 036).

**Riscos**

| Risco | Mitigação |
|---|---|
| Tempo no balcão na primeira visita (3 a 4 min a mais) | Só na primeira visita; condicionais; grava por tela; a recepção dispensa se precisar. Medir pelo tempo entre telas |
| Modelo com ~90 variáveis | Confirmar no sandbox com o `.docx` real **antes da spec**; se houver limite, cair para upload de PDF gerado (`content_base64`) |
| Revisão de texto obriga todo mundo a assinar de novo | Aceito (seção 2.5); revisar o texto com parcimônia e versionar |
| Dado de saúde sob a auth de hoje | `prontuario.ler`; nada no bot; bucket privado; dívida de auth por usuário sobe de prioridade |
| "Não" por pressa | Sem default, um toque por pergunta; a declaração de veracidade responsabiliza |
| Fototipo declarado virar parâmetro | Só em `answers`; nunca escreve `skin_type` (teste garante) |
| Documento longo no widget | Tela cheia já existe; manter o texto enxuto |

---

## 10. Antes da spec

1. Texto final do documento único aprovado (bloqueio de entrada).
2. Montar o `.docx` com todas as variáveis, criar o modelo no sandbox e
   **assinar de verdade** um documento de teste pelo widget, para ver o PDF
   renderizado com ~90 campos.
3. Confirmar a lista de alertas com a responsável técnica.

---

## 11. Critérios de aceite

- [ ] Paciente sem documento vigente responde as 4 telas e assina com um
      token e uma manuscrita; o PDF traz respostas, consentimento e imagem.
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

- [x] Pendente (aguardando o texto final do documento único)
- [ ] Spec gerada: `spec/038-ficha-de-anamnese-no-checkin.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
