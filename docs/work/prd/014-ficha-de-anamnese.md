# PRD - 014 Ficha de anamnese digital

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Substituir a ficha de anamnese em papel por um formulário web que a paciente
preenche no celular e assina eletronicamente, com validade jurídica, antes da
sessão de epilação a laser.

Serve a dois propósitos que hoje dependem de a paciente lembrar de avisar:
**informar o profissional** sobre condições que mudam a conduta, e
**resguardar o profissional** com uma declaração assinada e datada.

O documento de origem é `ficha de anamnese epilação a laser 2025 - atualizada.pdf`,
**Versão 02, revisão 09/2026**, com 11 seções.

---

## 2. Contexto

### A ficha já contém o termo de consentimento

As seções **10 (Declarações e Ciência)** e **11 (Assinaturas)** são exatamente o
termo de consentimento que estava previsto como projeto separado. O item 10.8 já
cita **ZapSign®** nominalmente.

Por isso o PRD 014 original, sobre o termo, foi **absorvido por este**. Não são
duas entregas. O que travava aquele PRD era não existir texto revisado; o texto
existe e é este.

### A mensagem que a ficha substitui já existe

`src/services/orientacoes_pos_sessao.py` dispara na confirmação de todo
agendamento e diz:

> 🚫 Nos avise antes de vir caso: esteja gestante ou amamentando; esteja usando
> Roacutan; tenha feridas, herpes ativa; tenha tatuagem na área; tenha realizado
> peeling nas últimas 2 semanas.

São as mesmas condições da anamnese, pedidas como **auto-relato voluntário**. A
ficha promove isso a **resposta registrada e assinada**. O aviso continua onde
está: ele orienta o preparo (raspar, evitar sol, suspender ácidos), que a ficha
não cobre.

### Duas cadências dentro do mesmo documento

| Seções | Muda quando | Exemplo |
|---|---|---|
| 2 a 7, 9 | Quase nunca | alergia, queloide, autoimune, fototipo |
| **8** | **Toda sessão** | sol nas últimas 2 semanas, pele bronzeada, pele sensibilizada |

O item 10.9 obriga a paciente a informar mudanças **antes de cada sessão**.

Mandar 4 páginas antes de toda sessão faz a adesão despencar por volta da
terceira, e aí sobra um sistema com cara de proteção e sem conteúdo. **Ficha
completa é v1; triagem curta por sessão é fase 2.**

---

## 3. Decisões do André (20/09/2026)

| Pergunta | Decisão |
|---|---|
| Onde a paciente preenche | **App web próprio**, não PDF preenchível, não pelo bot |
| Domínio | **Domínio da gestora**, neutro; `.vercel.app` no v1 para não travar |
| Identidade na página | Dados da clínica e da **responsável técnica**, vindos do token |
| Disparo | **Clique manual na tela de agenda**, pelo profissional |
| Assinatura | Ao final do preenchimento, via **ZapSign** |
| Quem assina | **Só a paciente.** A RT sai identificada, sem assinar |

### Por que domínio genérico, e não da clínica

Consideramos `anamnese.clinicaessencia.com.br`. O argumento a favor era confiança:
link de domínio desconhecido no WhatsApp parece golpe.

Esse argumento **não se sustenta**, porque a paciente cai num domínio
desconhecido de qualquer forma na hora de assinar (`zapsign.com.br`). O que gera
confiança, em ordem: a mensagem vir **do WhatsApp da própria clínica** (já é
assim, instância z-api por clínica), a página abrir com **nome e logo da
clínica**, e a profissional ter avisado.

E o domínio genérico ganha em duas coisas:

- **Clínica que sai leva o domínio junto.** Se a Nobre Laser encerrar o
  contrato, `anamnese.nobrelaser.com.br` deixa de ser nosso, e ele estará dentro
  de fichas assinadas e arquivadas. Mesmo raciocínio que põe a conta do ZapSign
  no CNPJ da gestora.
- **Uma superfície para proteger.** Um certificado, uma zona DNS, um alvo.

**E simplifica o código:** a clínica vem do **token**, não do hostname.
Multi-tenant por hostname deixa de existir.

O domínio deve ser registrado **no CNPJ da gestora**, não em CPF pessoal, pelo
mesmo motivo de continuidade e responsabilidade.

### Por que só a paciente assina

A seção 11 prevê assinatura do profissional responsável. No v1 o documento sai
**identificando** a responsável técnica (nome e registro), e só a paciente
assina.

A declaração que protege o profissional é a **10.1**, em que a paciente afirma
que as informações são verdadeiras. Essa é dela. Pôr a RT para assinar ficha a
ficha cria trabalho diário sem ganho proporcional.

**Efeito colateral bom:** isso desbloqueia a dívida de auth por usuário. Como a
assinatura da clínica não existe, não é preciso provar quem está logado no
painel. A dívida continua valendo para o prontuário, mas **deixa de travar esta
entrega**.

---

## 4. Escopo

### Dentro

- **App web novo**, público, mobile-first, em domínio próprio.
- Formulário fiel às seções 1 a 11 da Versão 02, com `form_version` gravada.
- **Token de acesso** por paciente, com validade, que morre após a assinatura.
- **Data de nascimento para abrir** a ficha, como segundo fator leve.
- Botão **Enviar ficha** na tela de agenda, com envio por WhatsApp.
- **Selo de pendência na agenda do dia**, para o disparo manual não depender de memória.
- Geração do PDF preenchido, envio ao ZapSign e **redirecionamento direto para assinatura**.
- Webhook de conclusão: PDF assinado **e trilha de auditoria** para o S3.
- Aba **Ficha de anamnese** na pasta de Documentos (PRD 012).
- **Painel de alertas** para o profissional, com as respostas que mudam a conduta.
- `clinics`: CNPJ, razão social, e dados da responsável técnica.

### Fora

- **Triagem curta por sessão** (seção 8 recorrente). Fase 2.
- **Disparo automático.** Decisão do André: manual, na agenda.
- **O bot coletar anamnese.** Nenhuma tool do agente lê ou escreve estas tabelas,
  pela mesma razão do prontuário.
- **Bloquear a sessão** por ficha pendente ou por alerta. Ver seção 6.
- **gov.br** e assinatura qualificada (ICP-Brasil). Não exigidas aqui.
- **Preencher `patients.skin_type` a partir da ficha.** Ver seção 6.
- Subdomínio por clínica. Os DNS estão sob controle do André e podem virar
  redirecionamento depois, se houver motivo.

---

## 5. Modelo de dados (proposto)

**`scheduler.professionals`** - coluna nova

`registro_conselho` (ex.: `"CRBM-SP 44657"`). O `role` já existe e guarda o
título (`"Biomédica Esteta"`).

**`scheduler.clinics`** - colunas novas

`cnpj`, `razao_social`, `responsible_professional_id` (FK para `professionals`).

A RT **não** vira colunas soltas em `clinics`. Ela já é uma pessoa em
`professionals`, para onde `availability_rules` e `patient_session_records` já
apontam; repetir nome e registro num segundo lugar é a receita de divergirem.

**Sem CPF da RT.** A versão anterior deste PRD previa `rt_cpf` para o ZapSign
verificar a assinatura dela. Como ficou decidido que **a RT não assina**, esse
CPF não tem finalidade, e guardar dado pessoal sem finalidade é o contrário do
que a LGPD pede.

**`scheduler.anamnesis_forms`** - a ficha de cada paciente

| Coluna | Observação |
|---|---|
| `clinic_id`, `patient_id` | chaves |
| `appointment_id` | nullable. Qual atendimento motivou o envio |
| `form_version` | `"02"`. O rodapé do PDF já se versiona |
| `status` | `ENVIADA` / `PREENCHIDA` / `ASSINADA` / `EXPIRADA` |
| `answers` | JSONB com as respostas das seções 1 a 9 |
| `declared_phototype` | I a VI, **autodeclarado**. Ver seção 6 |
| `rt_snapshot` | nome, título e registro da RT **na data**, congelados |
| `sent_by_name`, `sent_at` | quem disparou |
| `filled_at`, `signed_at` | os dois momentos, separados |
| `provider`, `provider_document_id` | o documento no ZapSign |
| `pdf_s3_key`, `pdf_sha256`, `audit_s3_key` | arquivo, hash e trilha |
| `signer_name`, `signer_cpf` | quem assinou, como o provedor apurou |

`rt_snapshot` congelado porque a RT muda com o tempo, e uma ficha de 2026 tem de
continuar dizendo quem era a RT em 2026.

**`scheduler.anamnesis_access_tokens`**

`token_hash` (nunca o token cru), `form_id`, `expires_at`, `used_at`,
`attempts`. A data de nascimento confere contra `patients.birth_date`, com
limite de tentativas.

**`anamnesis_form_events`** - trilha nossa

Append por transição, com o payload do webhook. Mesmo princípio do prontuário:
registro que não se reescreve.

---

## 6. Regras que não podem ser violadas

### O fototipo da ficha não escreve `patients.skin_type`

A seção 9 é **autodeclaração** da paciente (I a VI). No PRD 012 ficou decidido
que tipo de pele é escolhido **exclusivamente pelo profissional, de forma
manual, e nunca pelo bot**.

Autodeclaração de fototipo erra com frequência, e esse valor decide **parâmetro
de laser**. Gravar em `declared_phototype`, exibir como sugestão, **jamais
escrever em `patients.skin_type`**.

### O software não decide clinicamente

Os alertas (gestante, Roacutan, herpes ativa, lesão ativa, tatuagem na área,
peeling recente, câncer ativo, imunossupressão, queloide, epilepsia, pele
sensibilizada) são **exibidos**, não interpretados. Nada é bloqueado
automaticamente. Quem decide contraindicação é a profissional.

### Gravar as respostas antes de assinar

O `SUBMIT` persiste as respostas **antes** de chamar o ZapSign. Se a assinatura
falhar ou a paciente desistir, a profissional ainda vê "GESTANTE: SIM". O valor
clínico não pode ficar refém da etapa jurídica. Daí `PREENCHIDA` e `ASSINADA`
serem estados distintos.

### A ficha não sobrescreve o cadastro

Nome, CPF, e-mail e nascimento vêm na ficha e podem divergir de `patients`.
Preencher apenas o que estiver **vazio**; divergência é **mostrada**, não
resolvida sozinha.

### Menor de idade

A seção 11 prevê responsável legal. Se `birth_date` indicar menor, o link vai ao
telefone do responsável e o signatário no ZapSign é **ele**. O bot já tem a
regra do menor; aqui precisa da equivalente.

---

## 7. Fluxo

```
  profissional clica ENVIAR FICHA na agenda
        |
  token gerado, WhatsApp da clinica manda UMA mensagem com o link
        |
  paciente abre e confirma a data de nascimento
        |
  preenche (marca da clinica + RT no topo)
        |
  SUBMIT -> respostas gravadas AQUI -> status PREENCHIDA
        |
  PDF montado e enviado ao ZapSign
        |
  redireciona DIRETO para assinatura, na mesma sessao
        |
  webhook -> PDF assinado + trilha -> S3 -> pasta de Documentos
        |
  status ASSINADA, alertas visiveis na agenda
```

**Uma mensagem só.** Se a assinatura virasse um segundo link por WhatsApp, a
perda entre preencher e assinar seria grande. O ZapSign suporta redirecionar o
signatário ao final.

---

## 8. Áreas e arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `anamnese/` | criar | App Vite público, projeto Vercel próprio |
| `scheduler/src/functions/anamnesis/` | criar | Endpoints públicos por token, envio, webhook |
| `scheduler/src/services/anamnese/` | criar | Regras, montagem do PDF, alertas |
| `scheduler/src/services/assinatura/` | criar | Abstração de provedor, como `providers/whatsapp_provider.py` |
| `scheduler/src/scripts/setup_database.py` | modificar | Tabelas novas e colunas de `clinics` |
| `scheduler/sls/functions/anamnesis/` | criar | Interface das funções |
| `frontend/src/pages/agenda/` | modificar | Botão de envio e selo de pendência |
| `frontend/src/pages/documentos/` | modificar | Aba da ficha |

**App separado, e não rota pública dentro de `frontend/`.** O painel é
autenticado; abrir uma rota pública nele faria o bundle do painel viajar até a
paciente e misturaria as duas superfícies. Separado também mantém a ficha longe
de qualquer pixel de marketing.

**Atenção ao limite do CloudFormation.** A stack do scheduler está em 440/500
após o PR #60. Funções novas custam recursos; se apertar, os 74 log groups são o
próximo ganho disponível.

---

## 9. Dependências e riscos

**Dependências**

- **Domínio novo**, no CNPJ da gestora. Não bloqueia o desenvolvimento: o v1
  sobe em `.vercel.app`. Mas **nenhuma paciente real recebe link `.vercel.app`**
  - link assim pedindo dado de saúde no WhatsApp é o que golpe parece.
- **Conta ZapSign**, no CNPJ da gestora, com marca por documento.
- **Bucket S3 novo.** Hoje não há storage de arquivo no scheduler. Acesso só por
  URL assinada de curta duração.
- Dados da RT de cada clínica, e **o aceite dela** em constar como responsável
  identificada em toda ficha. Essência: **Clara Santos Dourado, CRBM-SP 44657,
  Biomédica Esteta**. Nobre Laser e Depilação Premium pendentes.
- Revisão jurídica do texto antes de ir ao ar.

**Riscos**

| Risco | Mitigação |
|---|---|
| **Dado sensível sob a auth fraca de hoje** | O painel devolve a `SCHEDULER_API_KEY` compartilhada. A ficha traz CPF, gestação e histórico oncológico, então a dívida fica mais cara. Não bloqueia a entrega, mas sobe de prioridade |
| **Endpoint público novo** | Autenticado pelo próprio token, sem api key. Token com hash no banco, validade curta, tentativas limitadas, rate limit |
| Link encaminhado ou vazado | Data de nascimento para abrir; token morre após assinar |
| Paciente preenche e não assina | Estado `PREENCHIDA` visível. Os alertas já servem |
| Disparo manual esquecido | Selo de pendência na agenda do dia |
| Pixel de marketing capturando dado de saúde | App próprio, sem tag de anúncio. Não negociável |
| Fototipo autodeclarado virar parâmetro | Campo separado, nunca escreve `skin_type` |
| Trocar de provedor | Abstração desde o primeiro dia |
| Provedor sumir em 3 anos | A trilha é guardada junto com o PDF, no nosso S3 |

---

## 10. Critérios de aceite

- [ ] A ficha abre com nome, logo e RT **da clínica certa**, vindos do token.
- [ ] Sem a data de nascimento correta, a ficha não abre.
- [ ] As respostas ficam gravadas mesmo que a assinatura não conclua.
- [ ] Ao terminar, a paciente vai **direto** para a assinatura, sem segundo link.
- [ ] Assinada, o PDF **e a trilha** aparecem na pasta de Documentos dela.
- [ ] O hash do PDF é gravado e confere com o arquivo guardado.
- [ ] Os alertas aparecem na agenda, e **nada é bloqueado** automaticamente.
- [ ] O fototipo declarado **não** altera `patients.skin_type`.
- [ ] Menor de idade envia ao responsável, que é o signatário.
- [ ] Token expirado ou já usado não abre.
- [ ] Nenhuma tool do bot lê ou escreve estas tabelas.
- [ ] O PDF não é acessível por URL pública.
- [ ] `pytest`, `npm run build`, `npm run lint` e `npm run test` verdes nos dois apps.

---

## 11. Antes de implementar

Três coisas travam o começo, e nenhuma é código:

1. **Comprar o domínio**, no CNPJ da gestora. Pode ser feito em paralelo ao
   desenvolvimento, mas precisa estar pronto antes da primeira paciente.
   Descartado usar `depilacaopremium.com.br`: é o domínio de uma das clínicas,
   e a paciente da Essência veria o endereço de outra clínica ao preencher
   ficha médica.
2. **Abrir a conta ZapSign** e confirmar: marca por documento, redirecionamento
   do signatário ao final, `externalId` no webhook, trilha pela API.
3. **Coletar os dados da RT** de cada clínica e o aceite dela.

E a recomendação que fez o PRD 012 sair certo de primeira: **rodar uma ficha
manualmente pelo painel do ZapSign antes de integrar**, para o desenho vir do
material real e não de suposição.

---

## Status

- [x] Pendente
- [ ] Spec gerada
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`

> **Histórico:** absorve o PRD 014 original sobre termo de consentimento, que
> era, na verdade, as seções 10 e 11 desta ficha.
