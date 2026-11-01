# PRD - 033 Telefone internacional e nono dígito: uma só identidade por pessoa

> Gerado na fase **Research** em 01/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Uma pessoa tem UM cadastro por clínica, seja qual for o jeito que o telefone
dela chegou: pelo WhatsApp (como o z-api entrega), pelo site (como ela digitou)
ou pelo painel. Isso vale para número de outro país e para celular brasileiro
escrito com ou sem o nono dígito.

---

## 2. Contexto

Dois casos reais da Essência em outubro de 2026:

- **Isadora de Oliveira Pires** fala pelo WhatsApp `31617223202` (Holanda).
  `normalize_phone` prefixa `55` em tudo que não começa com `55`, então o bot
  gravou o cadastro como `5531617223202`. O site recusa número que não seja
  brasileiro (`isValidBrPhone` no front, `is_valid_br_phone` em `send_otp` e
  `create_appointment`); ela usou o número da mãe e nasceu um segundo cadastro,
  com um agendamento de "primeira visita" e a confirmação indo para a mãe.
  Shanka Ahmed (Alemanha) está gravada como `55491735425685` pelo mesmo motivo.
- **Paula Schimmelpfeng** (DDD 35) existe como `553591328559`, como o WhatsApp
  entrega. No site ela digitou o número com o 9. A cotação a reconheceu, porque
  `carrinho.paciente_do_telefone` compara por `variantes_do_numero`; a criação
  do agendamento, em `AppointmentService._get_or_create_patient`, compara o
  telefone exato e criou `5535991328559`, sem CPF nem e-mail e com
  `is_first_visit = True`. Todos os reagendamentos seguintes caíram no duplicado.

Raízes: (1) a normalização assume Brasil; (2) existem duas regras para "é o mesmo
telefone" (exata e por variantes) espalhadas em nove consultas; (3) o site só
aceita formato nacional.

O "não recebi e-mail de confirmação" não é defeito: o sistema não envia e-mail.

---

## 3. Escopo

### Dentro do escopo
- `normalize_phone` só prefixa `55` quando o número tem cara de brasileiro
  (DDD de 11 a 99 e 8 ou 9 dígitos, celular começando por 9). Número com `+`
  ou sem cara de brasileiro é mantido como veio, só dígitos.
- `is_valid_phone`: brasileiro válido OU internacional com `+` e 8 a 15 dígitos.
  Substitui `is_valid_br_phone` no site (OTP e criação).
- `variantes_do_numero` não inventa variante para número que não é brasileiro.
- Toda leitura de paciente por telefone casa por variantes (`phone = ANY(%s)`):
  `_get_or_create_patient`, `get_active_appointment_by_phone`,
  `_nascimento_do_cadastro` e o UPDATE de cadastro em `ai_tools`,
  `conversation_agent` (nome na campanha), `desconto_personalizado`,
  `menor_de_idade`, `primeira_visita`, `send/handler` (last_message_at) e
  `patient/create` (409 de duplicidade).
- Site: o campo de celular aceita `+` seguido do código do país; a máscara
  nacional continua para quem não digita `+`.
- Testes unitários dos três pontos.
- Script de limpeza dos cadastros duplicados da Paula e da Isadora (rodado à
  parte, em prod, com aprovação).

### Fora do escopo
- Envio de e-mail de confirmação (não existe e não é pedido).
- OTP e confirmação do site registrados no MessageEvents (hoje aparecem como
  fala humana no painel). Fica para PRD próprio.
- Migração em massa de telefones já gravados com `55` indevido (só os dois
  casos conhecidos).

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/utils/phone.py` | modificar | `normalize_phone`, `is_valid_phone`, `variantes_do_numero`, `format_phone_display` |
| `scheduler/src/services/appointment_service.py` | modificar | lookups por variantes |
| `scheduler/src/services/{ai_tools,conversation_agent,desconto_personalizado,menor_de_idade,primeira_visita}.py` | modificar | lookups por variantes |
| `scheduler/src/functions/send/handler.py`, `scheduler/src/functions/patient/create.py` | modificar | lookups por variantes |
| `scheduler/src/functions/public_booking/{send_otp,create_appointment}.py` | modificar | `is_valid_phone` |
| `scheduler/tests/unit/test_nono_digito.py`, novo `test_telefone_internacional.py` | modificar/criar | testes |
| `booking-site/src/utils/format.ts` (+ test), `CustomerInfoForm.tsx`, `MyAppointmentsModal.tsx` | modificar | aceitar `+` |
| `scheduler/src/scripts/une_cadastros_duplicados_033.py` | criar | limpeza dos dois casos |

---

## 5. Dependências e riscos

- **Risco:** afrouxar o casamento por variantes faz dois cadastros distintos
  casarem? Não em 11-28 (nono dígito obrigatório, variantes não existem). Fora
  dessa faixa já é a regra da identificação do bot desde setembro.
- **Risco:** número estrangeiro de 10 ou 11 dígitos sem `+` vindo do site. O
  site sempre manda `+`; sem `+`, 10/11 dígitos é tratado como brasileiro, como
  hoje.
- Sem migration de banco. Deploy do `scheduler/` (zip) e do `booking-site/`.

---

## 6. Critérios de aceite

- [ ] `normalize_phone("31617223202") == "31617223202"` e `normalize_phone("+31 6 1722 3202") == "31617223202"`.
- [ ] `normalize_phone("11999990000") == "5511999990000"` (nada muda para o Brasil).
- [ ] Site aceita `+31 617223202` no agendamento e em "Meus agendamentos"; OTP chega.
- [ ] Agendar pelo site com `5535991328559` quando existe `553591328559` NÃO cria paciente.
- [ ] Testes unitários passando; lint do site sem warning.

---

## Status

- [ ] Pendente
- [x] Spec gerada: `spec/033-telefone-internacional-e-nono-digito.md`
- [x] Implementado em: 01/11/2026
- [x] Registrado em `TASKS_LOG.md`
