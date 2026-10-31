# PRD - 032 Site pede o cadastro de quem ainda não é paciente

> Gerado na fase **Research** em 31/10/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Quando alguém agenda pelo site público com um número que ainda não é paciente
da clínica (ou é paciente com cadastro incompleto), o site passa a pedir os
dados básicos do cadastro antes de confirmar: **CPF, data de nascimento e
e-mail**, além do nome e celular que já pede. O agendamento nasce com o
paciente completo, como nasce pelo bot e pelo painel.

Quem já é paciente com cadastro completo continua agendando só com nome e
celular, sem ver os campos extras.

---

## 2. Contexto

Em 31/10/2026 o André agendou pelo site da Nobre Laser (`agendar.nobrelaser.com.br`)
às 10h, com o nome "André Felipe", num número que não era paciente. O
agendamento foi criado e o paciente também, mas só com nome e telefone.

O que acontece hoje, por caminho:

| Caminho | Dados do paciente novo |
|---|---|
| Bot de WhatsApp | Nome, data de nascimento, CPF e e-mail. O prompt tem o passo de cadastro e `identificacao_de_paciente.cadastro_completo` retira o passo quando os quatro já existem (PRD 020 §7). |
| Painel | Modal de novo paciente com nome, telefone, sexo e os campos de `cadastroSchema` (CPF, nascimento, e-mail). |
| **Site público** | **Só nome e celular.** `CustomerInfoForm` tem dois campos; `POST /public/.../appointments` aceita só `fullName` e `phone`; `AppointmentService._get_or_create_patient` insere `clinic_id, phone, name`. |

Por que isso importa: o check-in e a cobrança pelo Asaas precisam do CPF (o
iPad pergunta na hora quando não sabe, PRD 026/028), a regra de menor de idade
precisa da data de nascimento (`menor_de_idade.py`, hoje só no bot), e a
clínica usa o e-mail no prontuário e na anamnese. Paciente que nasce pelo site
chega à clínica com três buracos que alguém preenche à mão depois.

A régua de "cadastro completo" já existe e é uma só: `CAMPOS_DO_CADASTRO =
("name", "birth_date", "cpf", "email")` em `identificacao_de_paciente.py`. O
site passa a usar a mesma.

---

## 3. Escopo

### Dentro do escopo

**A. O site descobre se precisa pedir.**

- `POST /public/clinics/{clinicId}/quote` já recebe o celular (para desconto
  de primeira sessão e personalizado) e já é chamado assim que o celular fica
  válido. A resposta ganha `cadastro: {"completo": bool, "faltam": ["cpf",
  "birth_date", "email"]}`. Só nomes de campos, nunca valores: criar
  agendamento não exige posse do número, e a resposta não pode entregar dado
  de ninguém. Saber que um número "tem cadastro" é informação do mesmo
  tamanho do que o `/quote` já revela com "primeira sessão".
- Fonte da régua: `identificacao_de_paciente.cadastro_completo` e uma nova
  `campos_faltantes(paciente)` ao lado dela, para a lista.

**B. O formulário pede o que falta.**

- `CustomerInfoForm` ganha os três campos, exibidos só quando `faltam` não
  está vazio, e só os que faltam. Enquanto o `/quote` com o celular não
  respondeu, o botão "Finalizar" espera (mesmo estado de carregando que o
  resumo de preço já usa).
- Validação no front: CPF pelos dígitos verificadores (há `isValidCpf` no
  `checkin/`; copiar para `booking-site/src/utils/format.ts`), data válida e
  no passado, e-mail com formato básico. Máscaras: `000.000.000-00` e
  `DD/MM/AAAA`, teclado numérico no celular.
- Texto curto acima dos campos: "Primeira vez aqui? Completamos seu cadastro."
  Sem explicar LGPD no formulário; o rodapé do site já tem o aviso de
  privacidade (PRD 025).

**C. A criação grava, valida e exige no servidor.**

- `POST /public/clinics/{clinicId}/appointments` aceita `cpf`, `birthDate`
  (`YYYY-MM-DD` ou `DD/MM/YYYY`) e `email`, opcionais no contrato.
- Regra no servidor, não só na tela: se o paciente do número não existe ou
  está incompleto, os campos que faltam são **obrigatórios**; ausentes ou
  inválidos, `400` com `code: CADASTRO_INCOMPLETO` e `faltam: [...]`. É a
  mesma lógica do `/quote`, pela mesma função, para a tela e a criação não
  divergirem (como já é com preço e duração, PRD 023).
- Normalização e validação pelas funções que o painel já usa:
  `utils/cadastro.normaliza_cpf`, `cpf_valido`, `normaliza_data_nascimento`;
  e-mail pela mesma regra de `patient/update.py`.
- `AppointmentService.create_appointment` passa `cpf`, `birth_date` e `email`
  a `_get_or_create_patient`, que grava no INSERT e, para paciente existente,
  preenche **só o que está vazio** (`COALESCE(existente, novo)`). Dado já
  cadastrado nunca é sobrescrito pelo site, pela mesma razão que o nome não é:
  o que a clínica corrigiu à mão vale mais que o que a pessoa digitou.
- O bot e o painel chamam o mesmo `create_appointment` sem os campos novos e
  continuam iguais.

**D. CPF duplicado.**

- Se o CPF informado já pertence a outro paciente da clínica (outro
  telefone), a criação recusa com `409 CPF_EM_USO` e o site mostra "Este CPF
  já está cadastrado com outro celular. Fale com a clínica." Sem isso, uma
  pessoa com dois números viraria dois pacientes com o mesmo CPF, e o
  check-in cobraria no cadastro errado.

### Fora do escopo

- Pedir sexo (o painel pede, o bot não; fica como está).
- Aviso de menor de idade no site (hoje só no bot). Com a data de nascimento
  gravada, vira um PRD pequeno depois.
- Verificar a posse do número antes de agendar (decisão do PRD 009 mantida).
- Preencher o cadastro de quem já agendou pelo site antes deste PRD. O
  agendamento do André de 31/10 se completa pelo painel, em Pacientes.
- Unificar pacientes com dois telefones.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/identificacao_de_paciente.py` | modificar | `campos_faltantes(paciente) -> list[str]` ao lado de `cadastro_completo` |
| `scheduler/src/functions/public_booking/quote.py` | modificar | Resposta ganha `cadastro: {completo, faltam}` quando há celular |
| `scheduler/src/functions/public_booking/create_appointment.py` | modificar | Lê `cpf`, `birthDate`, `email`; exige os que faltam (`400 CADASTRO_INCOMPLETO`); CPF de outro paciente (`409 CPF_EM_USO`); repassa ao serviço |
| `scheduler/src/services/appointment_service.py` | modificar | `create_appointment(..., cpf=None, birth_date=None, email=None)`; `_get_or_create_patient` grava no INSERT e completa vazios no UPDATE |
| `scheduler/src/utils/cadastro.py` | modificar | `email_valido(valor)` se ainda não existir fora de `patient/update.py` (mover para cá e usar nos dois) |
| `booking-site/src/components/CustomerInfoForm.tsx` | modificar | Campos condicionais de CPF, nascimento e e-mail; máscaras; validação |
| `booking-site/src/utils/format.ts` | modificar | `formatCpf`, `isValidCpf`, `formatDateInput`, `toISODateFromBr` |
| `booking-site/src/pages/Booking.tsx` | modificar | Passa `quote.data.cadastro.faltam` ao formulário; trata `CADASTRO_INCOMPLETO` e `CPF_EM_USO` |
| `booking-site/src/types/index.ts` | modificar | `Quote.cadastro`, `CreateAppointmentPayload` com os três campos |
| `booking-site/src/services/booking.service.ts` | modificar | Envia os campos novos |
| `scheduler/tests/unit/` | criar/modificar | `test_identificacao_de_paciente` (campos faltantes), `test_carrinho_do_site` (quote com cadastro; criação exigindo, gravando e recusando CPF em uso), `test_appointment_service` (COALESCE) |
| `booking-site/src/components/CustomerInfoForm.test.tsx`, `Booking.test.tsx` | modificar | Campos aparecem só quando faltam; validação; envio |
| `scheduler/tests/integration/032-*.md`, `tests/postman/032-*.json` | criar | Casos: número novo, paciente completo, paciente incompleto, CPF em uso |

---

## 5. Dependências e riscos

- **Privacidade:** `faltam` revela que um número tem (ou não) cadastro
  completo. É do mesmo tamanho do que o `/quote` já revela ("primeira sessão"
  ou "desconto personalizado"), e nunca inclui valores. Registrado como
  decisão, não como descoberta.
- **Compatibilidade durante o deploy:** front novo manda campos que o backend
  antigo ignora; backend novo com front antigo recusa paciente novo com
  `400 CADASTRO_INCOMPLETO` e o site antigo mostra a mensagem genérica de
  erro. Subir o backend e mergear em seguida, como no PRD 030.
- **Formulário mais longo:** três campos a mais só para quem é novo. Quem
  volta não vê nada diferente. Risco de abandono aceito pelo André (dados
  são necessários para o check-in e a cobrança).
- **Sem migration.** As colunas `cpf`, `birth_date`, `email` já existem.
- **Telefone compartilhado:** mãe agenda para a filha no mesmo número. O
  cadastro é do número; o CPF informado será o de quem agenda. O check-in já
  trata "CPF do cadastro pode ser de outra pessoa" perguntando de novo na hora
  (PRD 026); nada muda aí.

---

## 6. Critérios de aceite

- [ ] Número sem paciente: o site mostra CPF, nascimento e e-mail; não
      finaliza sem os três válidos; o paciente nasce com os quatro dados.
- [ ] Paciente com cadastro completo: o site mostra só nome e celular; nada
      é sobrescrito no cadastro.
- [ ] Paciente com cadastro parcial (por exemplo, sem e-mail): o site pede só
      o que falta e grava só isso.
- [ ] Requisição direta sem os campos, para número novo: `400
      CADASTRO_INCOMPLETO` com a lista.
- [ ] CPF de outro paciente da clínica: `409 CPF_EM_USO`, mensagem na tela.
- [ ] Bot e painel criam agendamentos como antes (suites intactas).
- [ ] Suites do scheduler e do booking-site verdes; lint zero.

---

## 7. Referências

- `scheduler/src/services/identificacao_de_paciente.py` (`CAMPOS_DO_CADASTRO`, `cadastro_completo`)
- `scheduler/src/utils/cadastro.py` (`normaliza_cpf`, `cpf_valido`, `normaliza_data_nascimento`)
- `scheduler/src/functions/patient/update.py` (validação de e-mail)
- `checkin/src/utils/format.ts` (`isValidCpf`, `formatCpf`)
- PRD 009 (site público), PRD 020 §7 (identificação do paciente no bot), PRD 023 (preço e duração do backend), PRD 026/028 (CPF no check-in)

---

## Status

- [x] Pendente
- [x] Spec gerada: `spec/032-site-cadastro-do-paciente-novo.md` (31/10/2026)
- [ ] Implementado em:
- [ ] Registrado em `TASKS_LOG.md`
