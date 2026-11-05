# PRD - 036 Termo de consentimento (TCLE) assinado no check-in

> Gerado na fase **Research** em 03/11/2026. Use como input para a fase Spec.
> Origem: sessão de desenho André + Claude. Decisões de produto fechadas uma a
> uma (§3); o que resta é implementação.

---

## 1. Objetivo

Toda paciente sem termo de consentimento vigente assina o **TCLE de epilação
a laser (Soprano Ice Platinum)** no iPad da recepção, dentro do check-in que já
existe (PRD 026), por assinatura eletrônica da **ClickSign**, antes do
pagamento. O PDF assinado e o log de auditoria ficam guardados no nosso S3 e
aparecem na pasta de Documentos da paciente no painel.

O documento de origem é `TCLE_atualizado(2).pdf` (5 páginas, 21 cláusulas).
Ele vira um modelo `.docx` na ClickSign, preenchido por variáveis com os dados
da paciente e da profissional responsável.

---

## 2. Contexto

### O que existe

- **Check-in no iPad** (PRD 026/028, em prod): OTP pelo WhatsApp, confirmar o
  agendamento, CPF se faltar, pagamento Asaas. "Documentos no check-in" ficou
  explicitamente fora de escopo da 026. Este PRD é esse passo.
- **PRD 014 (ficha de anamnese)**, pendente, previa ZapSign e um app próprio
  por link no WhatsApp. Ele já desenhou tabelas, S3 privado, trilha de
  auditoria e a regra de menor de idade.
- **Padrão de integração**: o provedor de pagamento (`PaymentProvider`,
  Asaas + simulado em dev, webhook com `compare_digest`, segredo em SSM) é o
  molde para o provedor de assinatura.
- **App `checkin/`**: Vite separado, passos
  `start → phone → code → appointment → method → cpf → payment → done`.
- **Banco**: `patients` tem `name`, `phone`, `cpf`, `birth_date`, `email`,
  mas CPF, nascimento e e-mail costumam estar vazios. Não existe tabela de
  termo, de responsável legal, nem bucket privado (o `clinic-assets` é
  público, só para logo e favicon).

### Relação com o PRD 014

**O TCLE é uma entrega própria e vem primeiro.** A anamnese fica para depois
e, quando vier, reaproveita o provedor e a infraestrutura daqui. A 014 será
revisada para trocar ZapSign por ClickSign e remover as seções de consentimento
que agora vivem no TCLE. **A ClickSign substitui a ZapSign em tudo** daqui em
diante.

### O que a ClickSign oferece (conferido na documentação em 03/11/2026)

- **API v3 por envelopes**: documento (PDF ou **modelo `.docx`** com
  variáveis preenchidas por JSON em `template.data`), signatário (`name`,
  `email`, `phone_number`, `documentation`, `birthday`), requisitos de
  autenticação (`email`, `sms`, `whatsapp`, `pix`, `selfie`, `handwritten`,
  entre outros), ativação, webhook com HMAC no header
  `x-clicksign-signature`, download do PDF assinado e do log ao fechar.
- **Widget embedded**: script oficial que monta a tela de assinatura dentro
  do nosso app a partir do ID do signatário, com eventos `loaded`, `signed` e
  `resized`, `endpoint` sandbox ou produção, HTTPS obrigatório em produção.
- **Limites**: 50 req/conta/10 s em produção, 20 em sandbox. O modelo não
  pode ser editado; muda-se apagando e criando outro.

Fontes: envelope v3, documento via modelo, requisito de autenticação, widget
embedded, signatário v3, eventos e cadastro de webhooks em
`developers.clicksign.com`.

---

## 3. Decisões (03/11/2026)

| # | Pergunta | Decisão | Por quê |
|---|---|---|---|
| 1 | Relação com a 014 | TCLE sozinho, primeiro; ClickSign substitui ZapSign em tudo | Entrega menor, infraestrutura reaproveitada pela anamnese |
| 2 | Onde assina | **No iPad, pelo widget embedded**, token da ClickSign pelo WhatsApp da signatária e **assinatura manuscrita na tela** | Quiosque não quebra; o token da ClickSign é o que dá peso à trilha, independente do nosso OTP; a manuscrita se parece com o papel |
| 3 | Quem assina | **Paciente sem TCLE vigente nesta clínica** (versão atual do termo), não a marca de primeira visita | Cobre a nova, a antiga sem termo digital e a volta depois de revisão do texto. Quem assinou em papel é registrado no painel |
| 4 | Falha ou desistência | **Sem pular no iPad; a recepção dispensa no painel** por sessão, com motivo | Ninguém perde sessão por software, mas pular é decisão humana e fica registrado. Pagamento no iPad só depois de assinar |
| 5 | Dados coletados | **Nome completo, CPF, nascimento e e-mail obrigatórios**; uso de imagem é escolha obrigatória | A ClickSign exige nome com sobrenome, CPF e nascimento; com e-mail ela entrega a cópia sozinha |
| 6 | Menor de idade | **Só o responsável legal assina**, presente no iPad, com token no celular dele; a menor é citada na cláusula 7. **A profissional responsável não assina**, só é identificada | Mesma decisão da 014 |
| 7 | Conta e modelo | **Uma conta da gestora, um modelo**; clínica e profissional entram por variável | Um plano, um webhook, documentos ficam com a gestora se a clínica sair |
| 8 | Cópia da paciente | **Só pela ClickSign, por e-mail** | Zero código; o envio pelo WhatsApp fica como evolução |
| 9 | Dados da clínica no termo | **Sem CNPJ nem razão social.** Só a profissional responsável (nome, título, registro) e a cidade | O termo não cita a clínica como parte; dado sem finalidade não se guarda |
| 10 | Motivo da dispensa | Lista fechada: `SEM_CELULAR`, `RECUSOU`, `SISTEMA_FORA`, `OUTRO` (com texto) | Dá para medir |

---

## 4. Fluxo no iPad

```
appointment ─confirmar─▶ backend grava check-in e responde consentRequired
     │
     ├─ false ─────────────────────────────────────▶ method (como hoje)
     │
     └─ true ─▶ consent-data ─▶ consent-sign ─▶ method
```

1. **`consent-data`**: dados já conhecidos preenchidos (nome, CPF,
   nascimento, celular, e-mail) para confirmar ou completar; a escolha de uso
   de imagem (autorizo / não autorizo); se menor na data da sessão, o bloco
   do responsável (nome, CPF, nascimento, celular, e-mail), pré-preenchido se
   já houver responsável gravado. Teclado numérico próprio para CPF e data,
   como o `Keypad` atual.
2. **`consent-sign`**: o widget da ClickSign montado na tela, `endpoint`
   vindo do backend. A signatária recebe o token no WhatsApp, digita, desenha
   a assinatura e conclui. O evento `signed` avança a tela, mas **quem decide
   "assinado" é o backend**, consultado por polling de 3 s.
3. **Falha** (token não chega, ClickSign fora, desistência, 5 min sem toque):
   tela "Chame a recepção" e volta ao início. O check-in continua gravado; o
   termo fica `SIGNING` e a agenda mostra o selo. **Sem botão de pular.**
4. Quem já tem termo vigente, termo em papel registrado ou dispensa nesta
   sessão não vê os passos novos.
5. Clínica sem profissional responsável ou cidade cadastradas: o iPad mostra
   "Chame a recepção" e o painel mostra o motivo em Configurações.

---

## 5. Backend e provedor

Espelha o pagamento, peça por peça.

- **Provedor** `scheduler/src/providers/signature_provider.py`: interface
  `SignatureProvider` (`cria_termo`, `consulta`, `baixa_pdf`, `baixa_log`,
  `cancela`, `simula`, flag `pode_simular`), exceções
  `AssinaturaIndisponivel` e `ErroDoProvedor`, e `provedor_ativo()`:
  `CLICKSIGN_API_KEY` presente usa a ClickSign (sandbox em dev, produção em
  prod); ausente em dev usa o simulado; ausente em prod levanta
  `AssinaturaIndisponivel` (503).
- **`clicksign_provider.py`** (API v3): cria envelope → documento via modelo
  com `template.data` → signatário (`has_documentation: true`,
  `communicate_events` sem e-mail de convite, porque a assinatura é no iPad)
  → requisitos `agree` (qualificação `sign`) + `provide_evidence` com
  `whatsapp` e `handwritten` → ativa. `consulta` lê o estado do envelope;
  `baixa_pdf` e `baixa_log` baixam o assinado e a trilha; `cancela` encerra
  um envelope abandonado. Header de autenticação e base URL por stage.
- **`simulated_signature_provider.py`**: só dev, sem chave. Devolve um id de
  signatário falso; o iPad mostra "Simular assinatura (teste)" no lugar do
  widget; `simula` marca como assinado e gera um PDF de teste.
- **Serviço** `scheduler/src/services/consentimento.py`:
  - `precisa_assinar(db, clinic_id, patient_id, appointment_id)`: sem termo
    `SIGNED` ou `PAPER` na versão vigente **e** sem `consent_waived_at` na
    sessão.
  - `inicia(db, ...)`: valida CPF (`cpf_valido`), idade na data da sessão
    (`idade.e_menor_de_idade`), exige responsável quando menor, grava no
    cadastro só o que estiver vazio, grava ou atualiza o responsável, congela
    `responsible_snapshot` e `patient_snapshot`, cria o envelope, grava
    `SIGNING`. Um `SIGNING` aberto de até 24 h é reaproveitado; mais velho é
    cancelado no provedor e marcado `EXPIRED`.
  - `status(db, consent_id)`: devolve o estado; se ainda `SIGNING`, consulta
    o provedor como reserva do webhook e aplica o fechamento se já houver.
  - `aplica_evento(db, payload)`: deduplica por `event_id`, no fechamento
    baixa PDF e log, grava no S3 com SHA-256, marca `SIGNED` e `signed_at`.
  - `dispensa`, `registra_papel`, `url_do_pdf`, `url_do_log`: usados pelo
    painel.
- **Sub-rotas** na coringa `public/clinics/{clinicId}/checkin/{proxy+}`, sem
  recurso novo no CloudFormation:
  - `GET appointments`: cada item ganha `consentRequired` e `consentPrefill`
    (nome, CPF mascarado, nascimento, e-mail, `isMinor`, responsável se
    houver).
  - `POST appointments/{id}/consent`: corpo com os dados confirmados, a
    escolha de imagem e o responsável; devolve `consent` (`id`, `status`,
    `signerId`, `widgetEndpoint`, `test`).
  - `GET consents/{id}`: status.
  - `POST consents/{id}/simulate`: só quando `pode_simular`.
- **Webhook** `POST public/clicksign/webhook`, rota nova na Lambda
  `PublicBooking` (cerca de 4 recursos; a stack está em 466/500): HMAC do
  corpo cru com `compare_digest`, segredo vazio recusa tudo, 200 só depois
  de gravar, 500 para a ClickSign reenviar.
- **Versão do termo**: `TCLE_VERSION` e `CLICKSIGN_TCLE_TEMPLATE_KEY` em SSM,
  lidos no deploy. Mudar o termo é subir o novo `.docx`, trocar os dois
  parâmetros e redeployar; todo mundo assina de novo na próxima vinda.
- **Variáveis do modelo** (`template.data`): `nome_completo`, `cpf`,
  `data_nascimento`, `telefone`, `email`, `autoriza_imagem` ("Autorizo" /
  "Não autorizo"), `menor_nome` (vazio se maior), `responsavel_nome`,
  `responsavel_cpf` (vazios se maior), `signatario_nome`, `signatario_cpf`
  (a paciente ou o responsável, quem de fato assina), `profissional_nome`,
  `profissional_titulo`, `profissional_registro`, `clinica_nome`, `cidade`,
  `data`. A assinatura posiciona-se pela tag `{{~position_sign_1}}`.
  Rubrica por página e a linha da profissional deixam de existir: a
  ClickSign anexa a própria página de assinaturas e o log. O modelo e o
  script que o gera estão em `docs/work/assets/036-tcle/`.

---

## 6. Dados

Migrations idempotentes em `scheduler/src/scripts/setup_database.py`, com os
`CREATE TABLE` atualizados.

**`scheduler.patient_consents`** - um registro por tentativa de termo

| Coluna | Observação |
|---|---|
| `id`, `clinic_id`, `patient_id`, `appointment_id` | chaves; `appointment_id` é a sessão que motivou |
| `term_version` | ex. `"2026-11"`, a versão do `.docx` |
| `status` | `SIGNING` / `SIGNED` / `CANCELLED` / `EXPIRED` / `PAPER` |
| `signer_kind` | `PATIENT` / `GUARDIAN` |
| `signer_name`, `signer_cpf`, `signer_birth_date`, `signer_phone`, `signer_email` | quem assinou, congelado |
| `patient_snapshot` | JSONB: dados da paciente como foram ao documento |
| `image_authorized` | boolean, cláusula 8 |
| `responsible_snapshot` | JSONB: nome, título e registro da profissional, cidade e nome da clínica, na data |
| `provider`, `provider_envelope_id`, `provider_document_id`, `provider_signer_id` | `clicksign` / `simulado` |
| `pdf_s3_key`, `pdf_sha256`, `audit_s3_key` | preenchidos no fechamento |
| `signed_at`, `created_at`, `updated_at` | |
| `paper_signed_at`, `paper_registered_by` | só para `PAPER` |

Índice único parcial: **um termo `SIGNED` ou `PAPER` por paciente, clínica e
versão**. Índice único parcial para **um `SIGNING` por paciente e clínica**.

**`scheduler.patient_guardians`**: `patient_id` (único), `name`, `cpf`,
`birth_date`, `phone`, `email`, timestamps.

**`scheduler.appointments`**: `consent_waived_at`, `consent_waived_by`,
`consent_waived_reason` (enum acima), `consent_waived_note`. Dispensa é por
sessão, de propósito.

**`scheduler.consent_webhook_events`**: `event_id` único, `payload`,
`received_at`.

**`scheduler.clinics`**: `responsible_professional_id` (FK para
`professionals`), `cidade`.

**`scheduler.professionals`**: `registro_conselho` (ex. `"CRBM-SP 44657"`).
Nome e título já existem (`name`, `role`).

**Regra de escrita no cadastro**: nome, CPF, nascimento e e-mail digitados no
iPad só preenchem `patients` quando o campo estiver vazio. Divergência não
sobrescreve; o que foi ao documento está no snapshot.

---

## 7. Painel

- **Agenda do dia**: selo "Termo pendente" no card quando a paciente não tem
  termo vigente e não foi dispensada. No detalhe: o estado ("Assinado em
  03/11 pela ClickSign", "Assinando", "Pendente", "Dispensado por Ana: sem
  celular") e, para `agenda.escrever`, **Dispensar nesta sessão** (motivo da
  lista) e **Assinado em papel** (data obrigatória, vale para a versão
  vigente).
- **Documentos da paciente**: aba "Termo de consentimento" ao lado de
  "Histórico por sessão", com as versões, data, signatário, quem registrou e
  os botões "Abrir PDF" e "Log de auditoria" por URL assinada de 5 minutos.
- **Configurações da clínica**: select da profissional responsável, cidade
  e, na mesma tela, o registro no conselho de cada profissional. O painel
  hoje só lista profissionais (`professionals.service.ts`), sem tela de
  edição; o registro é a única coisa editável que entra, e entra aqui.
- **Rotas**: Lambda nova `Consentimento` com coringa
  `clinics/{clinicId}/consents/{proxy+}`: `GET ?patientId=`,
  `POST appointments/{id}/waive`, `POST patients/{id}/paper`,
  `GET {id}/pdf-url`, `GET {id}/zip-url`. Ler segue `prontuario.ler` (é
  documento da paciente, como o histórico); dispensar e papel seguem
  `agenda.escrever`. As permissões são impostas no servidor
  (`src/utils/acesso.py`); o painel não checa no cliente, como no caixa.
- **Registro no conselho**: não existe endpoint de atualização de
  profissional. Entra a Lambda `UpdateProfessional`
  (`PUT clinics/{clinicId}/professionals/{id}`).

---

## 8. Armazenamento e segurança

- **Bucket novo** `${resourcePrefix}-documentos`, privado: bloqueio total de
  acesso público, SSE-S3, versionamento ligado. Chave
  `clinics/{clinicId}/patients/{patientId}/consents/{consentId}/{termo.pdf|log.pdf}`.
  O `clinic-assets` continua só para logo e favicon.
- **Acesso** só por URL assinada de 5 minutos, gerada pela Lambda
  `Consentimento` depois de conferir permissão e clínica.
- **Integridade**: SHA-256 gravado ao baixar; a aba de Documentos avisa se
  divergir.
- **Segredos** (SSM, lidos no deploy): `/{stage}/CLICKSIGN_API_KEY`,
  `/{stage}/CLICKSIGN_WEBHOOK_SECRET`, `/{stage}/CLICKSIGN_TCLE_TEMPLATE_KEY`,
  `/{stage}/TCLE_VERSION`. Base URL por stage no `serverless.yml`.
- **O token e a assinatura ficam na ClickSign**; nosso backend nunca vê o
  token. O iPad apaga tudo ao voltar ao início.
- **O bot** não lê nem escreve nenhuma dessas tabelas.

---

## 9. Escopo

### Dentro

- Passos `consent-data` e `consent-sign` no `checkin/`, com o widget
  embedded e o modo simulado.
- Provedor de assinatura (interface, ClickSign v3, simulado), serviço, sub-
  rotas do check-in e webhook.
- Tabelas e colunas da §6; bucket privado.
- Painel: selo e ações na agenda, aba em Documentos, campos em Configurações
  e Profissionais, Lambda `Consentimento`.
- `.docx` do TCLE com variáveis, gerado a partir do PDF (a subida na
  ClickSign é manual).
- Testes, documentação de integração e Postman.

### Fora

- Ficha de anamnese (PRD 014, a revisar depois).
- Cópia do termo pelo WhatsApp da clínica.
- Revogação do termo pelo sistema (cláusula 14): é manual, pelo painel da
  ClickSign e registro em papel.
- Conta ClickSign por clínica.
- A profissional assinar.
- Preencher o termo pelo celular na véspera.

---

## 10. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/providers/signature_provider.py` | criar | Interface, exceções, `provedor_ativo()` |
| `scheduler/src/providers/clicksign_provider.py` | criar | API v3 |
| `scheduler/src/providers/simulated_signature_provider.py` | criar | Dev sem chave |
| `scheduler/src/services/consentimento.py` | criar | Regras, snapshot, S3, webhook |
| `scheduler/src/functions/public_booking/checkin.py` | modificar | Sub-rotas de consentimento, `consentRequired` na lista |
| `scheduler/src/functions/public_booking/clicksign_webhook.py` | criar | HMAC, dedup, fechamento |
| `scheduler/src/functions/public_booking/router.py` | modificar | Rota do webhook |
| `scheduler/src/functions/consent/` | criar | Lambda `Consentimento` (painel) |
| `scheduler/src/functions/professional/update.py` | criar | Lambda `UpdateProfessional` (registro no conselho) |
| `scheduler/sls/functions/public_booking/interface.yml` | modificar | Rota do webhook, IAM do bucket |
| `scheduler/sls/functions/consent/interface.yml` | criar | Lambda e coringa |
| `scheduler/sls/resources/s3/documentos-bucket.yml` | criar | Bucket privado |
| `scheduler/serverless.yml` | modificar | Env vars, SSM, base URL por stage, bucket |
| `scheduler/src/scripts/setup_database.py` | modificar | Tabelas e colunas da §6 |
| `checkin/src/steps/ConsentDataStep.tsx`, `ConsentSignStep.tsx` | criar | Passos novos |
| `checkin/src/pages/CheckinPage.tsx` | modificar | Estado e transição |
| `checkin/src/services/checkin.service.ts`, `types/index.ts` | modificar | Chamadas e tipos |
| `frontend/src/pages/agenda/` | modificar | Selo, estado, dispensar, papel |
| `frontend/src/pages/documentos/` | modificar | Aba do termo |
| `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx` | modificar | Select da profissional responsável, cidade e o registro no conselho de cada profissional (o painel só lista profissionais, não os edita; o registro entra aqui, por profissional) |
| `frontend/src/services/consents.service.ts`, `types/index.ts` | criar / modificar | HTTP e tipos |
| `docs/work/prd/014-ficha-de-anamnese.md` | modificar (depois) | ZapSign → ClickSign, tirar consentimento |

---

## 11. Dev, testes e deploy

- **pytest**: gatilho (sem termo, versão antiga, papel, dispensa por sessão,
  menor sem nascimento, clínica sem responsável), snapshot congelado, escrita
  só em campo vazio, reaproveitamento e expiração do `SIGNING`, webhook
  duplicado, HMAC errado, fechamento com download e hash. Provedor falso em
  memória.
- **Vitest** no `checkin` e no `frontend`; `npm run build` e `npm run lint`
  zero warnings nos dois.
- **E2E em dev** com a conta sandbox da ClickSign, do iPad ao PDF no S3,
  registrado em `scheduler/tests/integration/036-termo-de-consentimento.md`.
- **Deploy**: migrations, `serverless deploy` dev → prod (nunca em
  paralelo), `checkin-dev` e `checkin-prod` pela CLI, painel pela Vercel no
  merge. Em prod sem chave da ClickSign, o iPad segue sem o passo e a agenda
  mostra o selo, para a recepção usar o papel até ligar.

---

## 12. Dependências e riscos

**Antes de implementar (não é código):**

1. **Conta ClickSign**: sandbox para dev e a conta do plano para prod, com
   widget embedded, token por WhatsApp e assinatura manuscrita habilitados.
2. **O `.docx` do TCLE** com as variáveis da §5, subido como modelo nas duas
   contas; as chaves dos modelos e o segredo do webhook em SSM.
3. **Revisão do texto**: cláusula 12 sem citar ZapSign; bloco de assinaturas
   sem a linha da profissional e sem rubrica por página.
4. **Cadastro** da profissional responsável (nome completo como no registro),
   registro e cidade nas clínicas que vão usar.

**Riscos**

| Risco | Mitigação |
|---|---|
| ClickSign fora ou token que não chega | Check-in já gravado; selo na agenda; dispensa pelo painel com motivo |
| Webhook perdido | Polling consulta o provedor e aplica o fechamento |
| Dado sensível (CPF, nascimento, menor) sob a auth compartilhada do painel | Não bloqueia; a dívida de auth por usuário sobe de prioridade |
| PDF exposto | Bucket privado, URL assinada de 5 min, nunca o `clinic-assets` |
| Provedor sumir | PDF e log guardados no nosso S3 com hash |
| Texto do termo mudar | `term_version` desde o início; nova versão pede assinatura nova |
| Limite de recursos do CloudFormation | Rota do webhook ~4 recursos e Lambda `Consentimento` ~6; stack em 466/500 |
| Nome da profissional como apelido de agenda | Conferir os cadastros antes de ligar |

---

## 13. Critérios de aceite

- [ ] Paciente sem termo vigente vê `consent-data` e `consent-sign` depois de confirmar; com termo vigente, em papel ou dispensada, vai direto ao pagamento.
- [ ] O check-in fica gravado mesmo que a assinatura não conclua; o termo fica `SIGNING` e a agenda mostra o selo.
- [ ] Não existe botão de pular no iPad.
- [ ] Nome, CPF, nascimento e e-mail são obrigatórios e validados; a escolha de imagem é obrigatória.
- [ ] Menor na data da sessão exige responsável, que é o signatário e recebe o token.
- [ ] Dados digitados só preenchem campos vazios do cadastro.
- [ ] O documento sai com a profissional responsável, registro, cidade e nome da clínica congelados no snapshot.
- [ ] Webhook com HMAC errado é recusado; repetido não muda nada.
- [ ] Ao fechar, PDF e log estão no bucket privado, o hash confere, e a aba de Documentos abre os dois por URL assinada.
- [ ] Dispensar e "assinado em papel" exigem `agenda.escrever` e ficam registrados com autor.
- [ ] Clínica sem responsável ou cidade: iPad manda à recepção e o painel mostra o motivo.
- [ ] Em dev sem chave, o modo simulado funciona de ponta a ponta; em prod sem chave, o passo não aparece.
- [ ] Nenhuma tool do bot lê ou escreve as tabelas novas.
- [ ] `pytest`, `npm run build`, `npm run lint` e `npm run test` verdes no `scheduler`, no `checkin` e no `frontend`.

---

## 14. Referências

- PRD 026 e 028 (check-in), PRD 014 (anamnese), PRD 012 (Documentos).
- `scheduler/src/providers/payment_provider.py`, `asaas_provider.py`,
  `scheduler/src/functions/public_booking/asaas_webhook.py`.
- `checkin/CLAUDE.md`, `checkin/src/pages/CheckinPage.tsx`.
- ClickSign: `developers.clicksign.com` (envelope v3, modelos, requisitos,
  widget embedded, eventos, webhooks).

---

## Status

- [x] Pendente
- [x] Spec gerada: `spec/036-termo-de-consentimento.md` (03/11/2026)
- [x] Implementado em: 04/11/2026 (PR #167, mergeado em 05/11/2026)
- [x] E2E em dev em 05/11/2026: assinatura real pelo iPad, webhook `auto_close`, PDF no S3, painel (achados em `scheduler/tests/integration/036-termo-de-consentimento.md`)
- [x] Prod em 05/11/2026, com o termo DESLIGADO: migrations, scheduler (482/500, Lambda `Consentimento`, bucket `-documentos`), painel e `checkin-prod`. Para ligar: `/prod/CLICKSIGN_TCLE_TEMPLATE_KEY`, webhook + `/prod/CLICKSIGN_WEBHOOK_SECRET`, cidade e responsável técnica por clínica, redeploy do scheduler e, por último, `/prod/TCLE_VERSION`
- [x] Registrado em `TASKS_LOG.md`
