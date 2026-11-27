# PRD - 067 Seletor de país (DDI) em todos os campos de celular

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Todo campo onde alguém digita um celular passa a ter o mesmo seletor de país
do link de documentos (25/11, PR #276): Brasil por padrão, lista fixa dos
países prováveis e "Outro país" com o código digitado à mão. Brasil mantém a
máscara e a regra do nono dígito; fora do Brasil aceita só dígitos e o número
vai à API como `+DDI` + número. O padrão "comece com +" do PRD 033, que
ninguém descobre sozinho, sai de todos os lugares.

---

## 2. Contexto

Em 25/11 uma paciente da Essência com número dos EUA não passou da etapa do
celular no link de documentos. Lá o problema foi resolvido com o seletor; a
pendência registrada era repetir nos outros lugares. Inventário feito em
27/11 (só leitura):

| App | Tela | Hoje | Defeito |
|---|---|---|---|
| booking-site | Etapa do celular (`PhoneStep`, PRD 061) | campo único; estrangeiro precisa começar com `+` | dica escondida; quem digita sem `+` vira brasileiro inválido |
| booking-site | Dados da pessoa (`CustomerInfoForm`) | idem | idem |
| booking-site | "Meus agendamentos" (`MyAppointmentsModal`) | idem | idem |
| checkin | Celular no iPad (`PhoneStep`, keypad) | só 11 dígitos brasileiros | estrangeiro não faz check-in no balcão |
| checkin | Celular do responsável (`ConsentDataStep`) | só celular brasileiro (`isValidMobile`) | responsável estrangeiro trava o termo de menor |
| checkin | Link de documentos (`PhoneStep` nativo) | seletor de país (PR #276) | nenhum: é o modelo |
| frontend | Cadastrar paciente / Editar paciente | texto livre, `normalizePhone` | **corrompe número estrangeiro**: acrescenta `55` a tudo que não começa com 55 (`+1 202...` vira `551202...`) |
| frontend | Novo agendamento, paciente nova | texto livre, vai cru ao backend | funciona só se a recepção souber digitar `+` |

O backend já aceita os dois formatos desde o PRD 033: `normalize_phone` deixa
como veio o que começa com `+` e acrescenta `55` ao que parece brasileiro.
Nenhuma rota muda.

Fora dos campos, um risco achado no caminho: o termo pela ClickSign manda o
celular da signatária como `phone_number` "DDD + número" (`_celular_nacional`),
e a ClickSign envia por ele o código de assinatura no WhatsApp. Para número
estrangeiro, não sabemos se a ClickSign aceita nem se o código chega.

---

## 3. Escopo

### Dentro do escopo

- **Componente de celular com país** em cada app (três pacotes separados, sem
  biblioteca comum): seletor "País" (lista fixa igual à do checkin: Brasil,
  EUA / Canadá, Portugal, Argentina, Uruguai, Paraguai, Chile, Colômbia, Peru,
  México, Espanha, Itália, França, Alemanha, Reino Unido, Japão, e "Outro
  país" com "Código do país"), campo do número com máscara brasileira ou só
  dígitos (6 a 14), sem emoji de bandeira.
- **booking-site:** as três telas acima usam o componente. Ele emite a mesma
  string que o resto do site já entende (`(11) 99999-0000` ou `+12025550147`),
  então `toApiPhone`, `isValidPhone`, a sessão verificada e a memória do
  código não mudam de contrato. Sai a dica "comece com +". A faixa de
  validação internacional passa a 7 a 17 dígitos totais (DDI de 1 a 3 mais
  número de 6 a 14), igual ao checkin.
- **checkin:** keypad do iPad ganha o seletor de país acima do visor (o keypad
  continua para os dígitos; o limite de dígitos segue o país). Celular do
  responsável ganha o mesmo seletor. O link de documentos não muda.
- **frontend (painel):** Cadastrar paciente, Editar paciente e a paciente nova
  do Novo agendamento usam o componente. `normalizePhone` deixa de corromper
  número com `+` (mesma regra do backend). Editar paciente abre com o país
  deduzido do número gravado (55 + 10/11 dígitos = Brasil; senão o prefixo
  mais longo da lista; sem casamento, "Outro país" com o número inteiro) e só
  manda o telefone se a recepção o alterou.
- Testes por app com os mesmos vetores (Brasil, EUA, Portugal, "Outro",
  inválidos) para as três cópias não divergirem.

### Fora do escopo

- ClickSign com signatária estrangeira (risco acima): verificar na
  documentação e, se preciso, PRD próprio. Não muda nada aqui.
- Telefone da clínica em Configurações (é fixo da clínica, brasileiro).
- Exibição de números em listas e conversas (já trata `+`/estrangeiro pelo
  PRD 033).
- Backend e banco: nenhuma mudança; nenhum número gravado é migrado.
- Lista de países editável ou com busca.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `booking-site/src/utils/ddi.ts` | criar | lista, validação, montagem da string (cópia do checkin) |
| `booking-site/src/components/CelularComPais.tsx` | criar | seletor + número, emite a string do site |
| `booking-site/src/components/PhoneStep.tsx`, `CustomerInfoForm.tsx`, `MyAppointmentsModal.tsx` | modificar | usam o componente; sai a dica do `+` |
| `booking-site/src/utils/format.ts` | modificar | faixa internacional 7 a 17 dígitos |
| `checkin/src/components/PaisDoCelular.tsx` | criar | seletor + "Código do país", extraído do `PhoneStep` |
| `checkin/src/steps/PhoneStep.tsx` | modificar | keypad com país; nativo usa o componente extraído |
| `checkin/src/steps/ConsentDataStep.tsx` | modificar | celular do responsável com país |
| `checkin/src/utils/ddi.ts` | modificar | `paisDoNumero` (deduz o país de um número gravado) |
| `frontend/src/utils/ddi.ts` | criar | cópia + `paisDoNumero` |
| `frontend/src/components/CelularComPais.tsx` | criar | seletor + número para formulários do painel |
| `frontend/src/utils/normalizePhone.ts` | modificar | não acrescenta 55 a número com `+` |
| `frontend/src/pages/pacientes/components/CreatePatientModal.tsx`, `EditPatientModal.tsx` | modificar | usam o componente |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | modificar | paciente nova usa o componente |
| testes dos três apps | modificar/criar | vetores iguais; telas com o seletor |

---

## 5. Dependências e riscos

- **Três cópias da lista:** os apps não compartilham código. Aceito por
  simplicidade; os testes com vetores iguais seguram a divergência. Mudar a
  lista é mudar nos três (comentário em cada cópia aponta as outras).
- **Contrato com o backend:** inalterado (`55...` ou `+DDI...`). Por isso o
  deploy é só de front.
- **iPad:** o `select` nativo abre o seletor do iPadOS; conferir na largura do
  iPad deitado que o keypad continua inteiro na tela.
- **Dev manda WhatsApp de verdade:** teste de envio de código só com o número
  do André; número estrangeiro testado só até o botão habilitar e o payload
  montado (nada de enviar código para número inventado).
- **Deploy em dev:** site e painel pelo preview da Vercel do PR (host
  `*-git-*` reescreve para a API de dev; preview tem SSO, conferir logado);
  checkin pelo `checkin-dev` via CLI.

---

## 6. Critérios de aceite

- [ ] Nenhuma tela de celular dos três apps pede para "começar com +".
- [ ] Em todas as telas do inventário, Brasil é o padrão e a regra do nono
      dígito continua; EUA com `(202) 555-0147` habilita e monta
      `+12025550147`; "Outro país" exige código de 1 a 3 dígitos.
- [ ] Painel: cadastrar paciente com EUA grava `12025550147` (não
      `5512025550147`); editar uma paciente estrangeira abre com o país certo
      e salvar sem mexer no telefone não o altera.
- [ ] iPad: check-in com número estrangeiro chega ao envio do código; keypad
      inteiro visível com o seletor.
- [ ] Testes, lint e build verdes nos três apps; publicado em dev
      (previews do site e do painel, `checkin-dev`).

---

## 7. Referências

- PR #276 e #278 (seletor no link de documentos), PRD 033 (telefone
  estrangeiro), PRD 061 (celular antes das datas).
- `scheduler/src/utils/phone.py` (`normalize_phone`).
- Memória `project_checkin_numero_estrangeiro`.

---

## Decisões (assumidas, André pediu PRD + spec + dev sem rodada de perguntas)

- Mesma lista fixa do checkin nos três apps.
- Uma cópia por app, com testes de vetores iguais, em vez de pacote comum.
- O componente do site emite a string que o site já usa, para não mexer no
  fluxo de sessão e código.
- Editar paciente só envia o telefone se ele foi alterado.

---

## Status (preencher após conclusão)

- [x] Pendente
- [x] Spec gerada: `spec/067-seletor-de-pais-nos-campos-de-celular.md`
- [x] Implementado em: 2026-11-27, em DEV (PR #283: previews do site e do painel, `checkin-dev`). Em PROD no mesmo dia: PR #283 mergeado (`f579a90`), site e painel pela Vercel, `checkin-prod` pela CLI. Pendente: verificar a ClickSign com signatária estrangeira.
- [x] Registrado em `TASKS_LOG.md`
