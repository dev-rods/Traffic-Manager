# PRD - 038 Ficha de anamnese no check-in, na mesma assinatura do termo

> Gerado na fase **Research** em 05/11/2026. Use como input para a fase Spec.
> Substitui o PRD 014 (ficha por link no WhatsApp, app próprio, ZapSign), que
> foi desenhado antes de existir o check-in no iPad e a ClickSign (PRD 036).

---

## 1. Objetivo

Coletar a **Ficha de Anamnese - Epilação a Laser** (Versão 02, revisão
09/2026, `Documentos Laser/finha anamnese 2026.pdf`) no mesmo lugar e no mesmo
gesto em que hoje se assina o termo de consentimento: o check-in no iPad.
Quem ainda não tem ficha vigente responde as perguntas em telas curtas, e
**uma única assinatura** (token no WhatsApp + manuscrita, como hoje) fecha o
termo e a ficha de uma vez. As respostas ficam gravadas e legíveis no painel,
com os alertas que mudam a conduta da profissional em destaque, e o PDF
assinado vai para a pasta de Documentos da paciente.

Duas perguntas motivaram este PRD, e as duas têm resposta "sim", provada no
sandbox em 05/11/2026 (seção 2.3):

1. A ficha pode estar no mesmo fluxo do check-in? **Sim.** É o mesmo gatilho
   do termo (paciente sem documento vigente), as mesmas telas de dados, o mesmo
   provedor.
2. Pode fazer parte da mesma assinatura? **Sim.** Um envelope da ClickSign
   aceita vários documentos e o widget embedded assina todos num fluxo só:
   um token, uma manuscrita, "Assinar todos (2)".

---

## 2. Contexto

### 2.1 O que já existe e o que a ficha aproveita

O PRD 036 (em produção desde 05/11/2026) entregou tudo o que o PRD 014 listava
como infraestrutura: provedor de assinatura (`SignatureProvider`, ClickSign v3
por modelo `.docx` com variáveis, simulado em dev), bucket privado
`-documentos` com URL assinada de 5 min, webhook com HMAC, Lambda
`Consentimento` (lista, dispensa por sessão, registro em papel, URLs), telas
de dados e de assinatura no iPad (`ConsentDataStep`, `ConsentSignStep` em
viewport cheio), responsável técnica e cidade por clínica, selo na agenda,
linha no popover e aba em Documentos.

A ficha entra **por cima disso**, sem app novo, sem link por WhatsApp, sem
domínio novo e sem segundo provedor. É a razão de o 014 ficar para trás: ele
previa criar do zero o que a 036 já criou, e previa uma jornada (link em casa,
ZapSign) que não é mais a da clínica.

### 2.2 A ficha, lida de ponta a ponta

Onze seções. Contagem feita sobre o PDF:

| Seção | Conteúdo | Perguntas Sim/Não | Campos de texto |
|---|---|---|---|
| Cabeçalho | nome, CPF, nascimento, telefone, e-mail | - | já vêm do check-in |
| 1 Queixa principal | o que motivou | - | 1 |
| 2 Histórico médico | gestante, amamentando, hormonal, pele, controlada, autoimune, imunossupressão, epilepsia, câncer, diabetes (+controlada), alergia | 12 | 6 ("se sim, qual") |
| 3 Medicamentos | em uso, isotretinoína (+data), fotossensibilizantes, minoxidil | 4 | 4 |
| 4 Dermatológicas | tatuagem, peeling 30 d, cera/pinça 30 d, foliculite, herpes na área, silicone, procedimentos 30 d, queloide, ácidos, lesões ativas | 10 | 4 |
| 5 Hábitos | atividade física, fuma, álcool, acompanhamento médico | 4 | 2 |
| 6 Outras | já fez laser, reação, sessões/equipamento | 1 | 2 |
| 7 Observações | opcional | - | 1 |
| 8 Exposição solar e pele hoje | sol/bronzeamento 2 semanas, bronzeada, sensibilizada | 3 | - |
| 9 Fototipo | autodeclaração I a VI | 1 escolha | - |
| 10 Declarações | 10.1 a 10.9 | - | - |
| 11 Assinaturas | cliente, responsável legal, profissional | - | - |

Total: **34 Sim/Não, 1 escolha, ~20 textos condicionais**. No iPad, com os
textos aparecendo só quando a resposta é "Sim", são 5 telas de 6 a 12 toques
cada. Estimativa de 3 a 5 minutos para quem responde "Não" na maioria, que é a
maioria.

**Duas cadências dentro do mesmo papel** (já apontado no 014): as seções 2 a
7 e 9 quase não mudam; a seção 8 muda a cada sessão, e a cláusula 10.9 obriga
a paciente a avisar mudanças antes de cada sessão. Este PRD trata a ficha
inteira como documento **por paciente e por versão**, igual ao termo, e deixa a
seção 8 recorrente como fase 2 (seção 3).

**Redundância com o termo.** A seção 10 da ficha repete o que o TCLE já diz:
10.1 (veracidade) é a seção 10 do termo; 10.2 e 10.3 (intercorrências e riscos)
são as 3, 5 e 11; 10.5 (LGPD) é a 9; 10.6 (sessões avulsas) é a 17; 10.9
(avisar mudanças) é a 13. Não é problema: os dois documentos são assinados
juntos e cada um se sustenta sozinho no arquivo. O que **precisa mudar** é o
item 10.8, que cita ZapSign® nominalmente. Como o PDF da ficha passa a ser
gerado por nós a partir de um modelo, a frase vira "plataformas digitais
legalmente reconhecidas", sem marca, e a ficha ganha **Versão 03**. Texto a
revisar com quem assina pela clínica antes de subir o modelo.

### 2.3 O que foi provado no sandbox da ClickSign (05/11/2026)

Envelope `d0ecd5ae` criado pela API v3 com **dois documentos** do mesmo modelo
(`TCLE.docx` e `FICHA.docx`), **uma signatária**, requisitos `agree` +
`whatsapp` + `handwritten` em cada documento, ativado. O widget embedded,
aberto com o `signerId` num Chromium headless, mostrou:

- "2 documentos para assinar", lista com os dois nomes, botão **"Assinar
  todos (2)"**.
- `GET /notarial/widget/signatures/{id}/steps` devolve `federal_data, agree,
  handwritten, whatsapp`: **os mesmos quatro passos de um documento só**. O
  token e a manuscrita são colhidos uma vez.
- `steps/agree` lista um requisito `agree` por documento (`document_key`
  diferente), preenchidos no mesmo passo.
- Na assinatura real em prod do dia 05/11 o webhook mandou `document_closed`
  **por documento** e `auto_close` do envelope; com dois documentos virão dois
  `document_closed`. O código de hoje já trata os dois nomes como "fechado",
  mas localiza o termo pelo `document_key`, o que serve exatamente para fechar
  cada documento do envelope separadamente.

Limites documentados: 10 MB por arquivo e 100 MB por envelope; os requisitos
são por par documento+signatário. Fontes: `developers.clicksign.com/docs/envelope`,
`/docs/documentos`, `/docs/docs-modelos`.

**A confirmar antes da spec** (seção 10): o custo de crédito da ClickSign por
envelope com dois documentos (um ou dois créditos), e se um modelo aceita as
~70 variáveis da ficha (o do termo tem 17; não há limite documentado).

### 2.4 Por que não "ficha em casa, pelo link"

O 014 mandava o link por WhatsApp para preencher antes. A objeção continua
válida: link `.vercel.app` pedindo dado de saúde parece golpe, exige domínio
novo, app novo e token próprio. Com o check-in no iPad a paciente já está
identificada (telefone + código), já confere os dados e já assina ali. A ficha
no iPad custa os minutos no balcão da **primeira** visita de cada paciente e
nada depois. Preencher em casa pelo site (que já tem "Meus agendamentos" com
a mesma sessão) fica como evolução, com a assinatura continuando no iPad ou
no celular; o backend deste PRD já nasce pronto para isso porque as respostas
são gravadas antes da assinatura.

---

## 3. Escopo

### Dentro

- **Gatilho**: paciente sem ficha vigente nesta clínica (`ANAMNESE_VERSION`
  no SSM, igual a `TCLE_VERSION`). Sem a versão configurada, o check-in não
  pede a ficha e nada muda.
- **Telas no iPad**, entre `consent-data` e a assinatura: Queixa + Histórico
  médico, Medicamentos, Dermatológicas, Hábitos + Outras informações +
  Observações, Exposição solar + Fototipo. Toques grandes, "Sim"/"Não"
  obrigatórios (sem default), textos só quando "Sim", progresso "3 de 5".
- **Uma assinatura** para o que estiver pendente: termo e ficha, só a ficha, ou
  só o termo. Um envelope, um documento por item pendente, um widget.
- **Respostas gravadas antes de assinar**, em JSONB versionado por
  `form_version`, e PDF gerado por **modelo da ClickSign com variáveis**
  (`ANAMNESE_TEMPLATE_KEY`), uma por resposta e por texto condicional.
- **Alertas** no painel: lista fixa de respostas que mudam a conduta
  (gestante, amamentando, isotretinoína, fotossensibilizantes, herpes na
  área, lesão ativa, tatuagem na área, peeling 30 d, cera/pinça 30 d, câncer,
  imunossupressão, queloide, epilepsia, diabetes não controlada, sol 2
  semanas, bronzeada, sensibilizada). Exibidos, nunca interpretados.
- **Painel**: linha "Ficha" no popover (pendente / assinada / papel /
  dispensar, como a do termo), aba **Ficha de anamnese** em Documentos
  (respostas legíveis, alertas no topo, PDF e trilha), selo na agenda.
- **Papel e dispensa**: mesmos mecanismos do termo, por documento.
- **Menor de idade**: o responsável legal responde e assina, como no termo.
- `patients.skin_type` **não é escrito** pelo fototipo declarado (regra do
  PRD 012, mantida do 014).
- Versão 03 da ficha (item 10.8 sem marca) como modelo na ClickSign, dev e
  prod.

### Fora

- **Triagem curta por sessão** (seção 8 recorrente a cada check-in, sem
  assinatura). Fase 2, com PRD próprio: o prontuário já tem `tanned_skin` por
  sessão, preenchido pela profissional.
- Preencher em casa pelo site. Evolução, não v1.
- Assinatura da profissional responsável (decisão do 014: a RT é identificada,
  não assina).
- Bloquear sessão ou pagamento por alerta. Quem decide contraindicação é a
  profissional.
- O bot ler ou escrever qualquer coisa da ficha.
- Migrar fichas de papel antigas.

---

## 4. Decisões a tomar (com a recomendação)

| # | Pergunta | Recomendação | Por quê |
|---|---|---|---|
| 1 | Mesma assinatura do termo? | **Sim**, um envelope com os documentos pendentes | Provado no sandbox; um token e uma manuscrita; menos tempo no balcão |
| 2 | Quando pede a ficha | **Sem ficha vigente** (versão) **ou vencida há 12 meses**, mais botão "Pedir nova ficha" no painel | Mesmo gatilho do termo; a validade cobre a mudança de estado de saúde que a 10.9 pede sem virar triagem por sessão |
| 3 | PDF: modelo com variáveis ou arquivo gerado por nós | **Modelo com variáveis** (`Sim`/`Não`/`-` e os textos) | Zero biblioteca de PDF na Lambda, mesmo mecanismo do termo, carimbo e trilha da ClickSign iguais |
| 4 | Ordem no iPad | Dados → **ficha** → assinatura → pagamento | A ficha alimenta o PDF; assinar antes de responder não existe |
| 5 | Respostas sem assinatura | **Ficam gravadas** (`PREENCHIDA`) e os alertas já aparecem | Valor clínico não refém da etapa jurídica (014) |
| 6 | Onde os alertas aparecem | Popover do agendamento e aba da ficha; **sem selo novo** na agenda além do "pendente" | A agenda já tem TERMO, CONFIRMADO e PENDENTE; mais um selo por alerta vira ruído |
| 7 | Selo na agenda | **Um selo só, "DOCS"**, quando falta termo ou ficha, no lugar de TERMO | Dois selos para o mesmo gesto (assinar no iPad) confundem; o popover detalha qual falta |
| 8 | Divergência de dados com o cadastro | Nome confirmado atualiza (como já faz); CPF, nascimento e e-mail só em campo vazio | Regra já em produção na 036 |
| 9 | Quem vê as respostas | Permissão `prontuario.ler`, como o prontuário; ADMIN e STAFF com ela | Dado de saúde; a dívida de auth por usuário fica mais cara, não bloqueia |
| 10 | Dispensa | Por documento, com os mesmos motivos do termo | A recepção pode dispensar a ficha e manter o termo |

---

## 5. Fluxo no iPad

```
appointment ─confirmar─▶ backend responde documentsRequired: ['TCLE','ANAMNESE'] (0, 1 ou 2)
     │
     ├─ nenhum ───────────────────────────────────────────────────▶ method
     │
     └─ algum ─▶ consent-data ─▶ [anamnese 1..5, se pendente] ─▶ sign (1 widget) ─▶ method
```

1. `consent-data` continua igual: é a identificação da signatária (ou do
   responsável) e vale para os dois documentos.
2. Telas da ficha, só se `ANAMNESE` estiver pendente. Cada tela grava ao
   avançar (`PATCH` parcial), para uma queda de rede ou um "Recomeçar" não
   perder tudo. Voltar é permitido até a assinatura.
3. Ao terminar a última tela: `POST .../documents` cria o envelope com os
   documentos pendentes, grava a ficha como `PREENCHIDA` e devolve o
   `signerId`. A tela de assinatura é a de hoje, com "2 documentos" na barra.
4. Assinado: cada `document_closed` fecha o seu documento (PDF para o S3,
   hash); o `auto_close` não precisa fazer nada. O polling continua sendo quem
   confirma para o iPad.
5. Falha, desistência ou 5 min sem toque: "Chame a recepção", documentos ficam
   `SIGNING`/`PREENCHIDA`, agenda mostra o selo. Sem pular.
6. Reaproveitamento: envelope `SIGNING` de até 24 h é reaproveitado se os
   dados **e as respostas** forem os mesmos; mudou algo, descarta e cria outro
   (regra já existente no termo, estendida à ficha).

---

## 6. Backend e dados

**Unidade = documento, agrupamento = envelope.** `patient_consents` passa a
ser a tabela dos documentos assinados no check-in, com uma linha por documento
e o `provider_envelope_id` compartilhado entre termo e ficha do mesmo gesto.

| Mudança | Detalhe |
|---|---|
| `patient_consents.kind` | `TCLE` (default, linhas existentes) ou `ANAMNESE` |
| `patient_consents.answers` | JSONB, só para `ANAMNESE`: respostas das seções 1 a 9 por chave estável (`gestante`, `isotretinoina_ultima_dose`, `fototipo`...) |
| `patient_consents.status` | ganha `FILLED` (preenchida, sem envelope ainda) além de `SIGNING`/`SIGNED`/`CANCELLED`/`EXPIRED`/`PAPER` |
| Índices únicos | `(clinic_id, patient_id, kind, term_version)` vigente e `(clinic_id, patient_id, kind)` em andamento |
| `appointments.consent_waived_*` | passa a guardar o `kind` dispensado (ou os dois) |
| SSM | `/{stage}/CLICKSIGN_ANAMNESE_TEMPLATE_KEY`, `/{stage}/ANAMNESE_VERSION` |
| `consentimento.py` | `precisa_assinar` vira por `kind`; `inicia` monta o envelope com os documentos pendentes; `_fecha` por `document_key`; alertas calculados de `answers` por lista fixa |
| Rotas | `public/.../checkin/appointments/{id}/anamnesis` (PATCH parcial), `.../documents` (cria envelope); painel: `GET consents/patients/{id}` devolve os dois tipos, `POST .../paper`, `.../waive` com `kind` |
| Nada de Lambda nova | tudo dentro de `PublicBooking` e `Consentimento`: o stack está em 482/500 em dev e prod |

O PDF da ficha nasce do modelo com variáveis; o `answers` é a fonte para o
painel e para os alertas, o PDF é a prova. Os dois são gravados; divergir é
impossível porque o PDF é gerado a partir do `answers`.

---

## 7. Painel

- **Popover**: linha "Ficha de anamnese" abaixo de "Termo", mesmos estados e
  ações (ver PDF, registrar papel, dispensar). Alertas em vermelho logo abaixo,
  um por linha, só os "Sim" relevantes.
- **Documentos**: terceira aba `?doc=ficha`. Respostas agrupadas por seção,
  alertas no topo, fototipo declarado com a nota "autodeclarado; o tipo de
  pele do prontuário é o da profissional", botão "Pedir nova ficha".
- **Agenda**: selo DOCS (decisão 7).
- **Configurações**: a seção "Responsável técnica e termo" passa a listar os
  dois documentos e a versão vigente de cada um.

---

## 8. Áreas e arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `docs/work/assets/038-anamnese/` | criar | `gera_modelo.js` e o `.docx` da ficha v03 com variáveis |
| `scheduler/src/services/consentimento.py` | modificar | `kind`, envelope multi-documento, `answers`, alertas |
| `scheduler/src/services/anamnese.py` | criar | perguntas, chaves, validação por tela, lista de alertas, variáveis do modelo |
| `scheduler/src/providers/signature_provider.py`, `clicksign_provider.py`, `simulated_signature_provider.py` | modificar | `cria_envelope(documentos=[...])` no lugar de `cria_termo`; espera de todos os documentos |
| `scheduler/src/functions/public_booking/checkin.py` | modificar | rotas da ficha e do envelope |
| `scheduler/src/functions/consent/router.py` | modificar | `kind` nas rotas do painel |
| `scheduler/src/functions/appointment/list.py` | modificar | `anamnesis_status` ao lado de `consent_status` |
| `scheduler/src/scripts/setup_database.py` | modificar | migrations idempotentes da seção 6 |
| `scheduler/serverless.yml` | modificar | duas env vars novas |
| `checkin/src/steps/Anamnese*.tsx` | criar | as 5 telas |
| `checkin/src/pages/CheckinPage.tsx`, `ConsentSignStep.tsx` | modificar | estados novos; "N documentos" na barra |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` | modificar | vira "DocumentosDoAgendamento" com as duas linhas |
| `frontend/src/pages/documentos/` | modificar | aba da ficha |
| `scheduler/tests/`, `checkin/src/**/*.test.tsx`, `frontend/src/**/*.test.tsx` | criar | cobertura dos fluxos acima |

---

## 9. Dependências e riscos

**Dependências**

- Ficha **Versão 03** aprovada (item 10.8 sem marca). Sem isso, o PDF gerado
  cita ZapSign num documento assinado pela ClickSign.
- Modelo da ficha criado pela API nas contas de sandbox e produção (o script
  do 036 já faz isso).
- Confirmação do custo por documento na ClickSign.

**Riscos**

| Risco | Mitigação |
|---|---|
| Tempo no balcão na primeira visita (3 a 5 min a mais) | Só na primeira visita; textos condicionais; grava por tela; a recepção pode dispensar a ficha e manter o termo. Medir pelo `created_at` das telas |
| Variáveis demais para o modelo | Confirmar no sandbox com o `.docx` real antes da spec; se houver limite, cair para upload de PDF gerado (a API aceita `content_base64`) |
| Dado de saúde sob a auth de hoje | Permissão `prontuario.ler`; nada no bot; bucket privado; a dívida de auth por usuário sobe de prioridade |
| Resposta "Não" por pressa | Sem default: cada pergunta exige um toque; 10.1 e 18 do termo responsabilizam pela omissão |
| Dois `document_closed` e um `auto_close` | Fechar por `document_key`; o envelope só é "concluído" quando todos os documentos forem `SIGNED` |
| Fototipo declarado virar parâmetro | Campo só em `answers`; nunca escreve `skin_type` (teste garante) |

---

## 10. Antes da spec

1. Revisar o texto da ficha (10.8) e aprovar a Versão 03.
2. Montar o `.docx` com todas as variáveis e criar o modelo no sandbox; abrir
   um envelope de teste com termo + ficha e **assinar de verdade** no widget,
   para ver os dois PDFs, os dois `document_closed` e o `auto_close`.
3. Confirmar com a ClickSign o custo por documento num envelope.
4. Decidir a tabela da seção 4.

---

## 11. Critérios de aceite

- [ ] Paciente sem ficha vigente responde as 5 telas no iPad e assina termo e
      ficha com um token e uma manuscrita; quem já tem termo assina só a ficha.
- [ ] Sem `ANAMNESE_VERSION`, o check-in não muda.
- [ ] As respostas ficam gravadas ao avançar cada tela e sobrevivem a
      "Recomeçar" dentro de 24 h.
- [ ] Assinada, a aba Ficha mostra respostas, alertas, PDF e hash; o PDF não
      tem URL pública.
- [ ] Os alertas aparecem no popover e na aba; nada é bloqueado.
- [ ] `skin_type` não muda com o fototipo declarado.
- [ ] Menor de idade: o responsável responde e assina.
- [ ] Dispensa e papel funcionam por documento, com motivo.
- [ ] Nenhuma tool do bot lê ou escreve a ficha.
- [ ] `pytest`, `npm run build`, `npm run lint` e `npm run test` verdes nos
      três apps; stack dev e prod abaixo de 500 recursos.

---

## 12. Referências

- PRD 036 e `scheduler/tests/integration/036-termo-de-consentimento.md`
  (provedor, widget, webhook, achados).
- PRD 014 (decisões herdadas: alertas exibidos e não interpretados, respostas
  antes da assinatura, fototipo não escreve `skin_type`, RT não assina).
- PRD 012 (pasta de Documentos, `skin_type` só pela profissional).
- `docs/work/assets/036-tcle/gera_modelo.js` (como gerar o `.docx` do modelo).
- Sondagem de dois documentos: envelope `d0ecd5ae` no sandbox, script
  `dois_docs.py` da sessão de 05/11/2026.

---

## Status

- [x] Pendente
- [ ] Spec gerada: `spec/038-ficha-de-anamnese-no-checkin.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
