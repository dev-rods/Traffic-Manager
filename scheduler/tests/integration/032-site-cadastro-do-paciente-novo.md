# Site pede o cadastro de quem ainda não é paciente (PRD/Spec `032`)

A pergunta: **quem agenda pelo site com um número novo nasce com CPF, nascimento
e e-mail, e quem já tem cadastro completo não vê nada diferente?**

```bash
cd scheduler && source .env
BASE="https://SEU_API_GATEWAY.execute-api.us-east-1.amazonaws.com/dev"
H=(-H "x-api-key: $BOOKING_API_KEY" -H "Content-Type: application/json")
CLINIC="clinicadorods-da7b62"; SVC="<serviceId>"; AREA="<areaId>"
NOVO="5511999990001"       # sem paciente
COMPLETO="5511999990002"   # paciente com os quatro dados
```

## 1. Cotação diz o que falta

```bash
curl -s -X POST "${H[@]}" -d "{\"serviceIds\":[\"$SVC\"],\"serviceAreaPairs\":[{\"serviceId\":\"$SVC\",\"areaId\":\"$AREA\"}],\"phone\":\"$NOVO\"}" "$BASE/public/clinics/$CLINIC/quote"
```

**Esperado:** `quote.cadastro = {"completo": false, "faltam": ["birth_date", "cpf", "email"]}`.
Com `$COMPLETO`: `{"completo": true, "faltam": []}`. Sem `phone`: `cadastro: null`.
Nunca aparece CPF, e-mail ou data de ninguém na resposta.

## 2. Criação sem o cadastro, número novo

```bash
curl -s -X POST "${H[@]}" -d "{\"phone\":\"$NOVO\",\"fullName\":\"Teste 032\",\"serviceIds\":[\"$SVC\"],\"date\":\"<data oferecida>\",\"time\":\"<hora>\",\"serviceAreaPairs\":[{\"serviceId\":\"$SVC\",\"areaId\":\"$AREA\"}]}" "$BASE/public/clinics/$CLINIC/appointments"
```

**Esperado:** `400`, `code: CADASTRO_INCOMPLETO`, `faltam: ["birth_date","cpf","email"]`. Nenhum paciente criado.

## 3. Criação com o cadastro

Mesmo corpo mais `"cpf":"529.982.247-25","birthDate":"31/10/1990","email":" Teste@X.com "`.

**Esperado:** `201`. Em `GET /clinics/$CLINIC/patients` (chave de admin) o paciente
do `$NOVO` tem `cpf = 52998224725`, `birth_date = 1990-10-31`, `email = teste@x.com`.

## 4. Validação

- `cpf: 11111111111` -> `400 faltam: ["cpf"]`
- `birthDate: 2099-01-01` -> `400 faltam: ["birth_date"]`
- `email: teste` -> `400 faltam: ["email"]`

## 5. CPF de outro paciente

Repetir o passo 3 com outro número novo e o mesmo CPF: `409`, `code: CPF_EM_USO`.

## 6. Paciente completo não é tocado

Criar com `$COMPLETO` sem os campos: `201`. Criar com `$COMPLETO` e um e-mail
diferente: `201` e o e-mail do cadastro **não muda** (só vazio é preenchido).

## 7. Parcial

Paciente com CPF e nascimento mas sem e-mail: a cotação devolve `faltam: ["email"]`;
criar sem e-mail -> `400 faltam: ["email"]`; com e-mail -> `201` e o e-mail gravado.

## 8. Painel

`POST /clinics/$CLINIC/patients` com `email: "ana@"` -> `400 "E-mail inválido"`
(até aqui qualquer texto era aceito).
