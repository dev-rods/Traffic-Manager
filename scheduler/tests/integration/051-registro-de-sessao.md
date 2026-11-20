# 051 - Registro de sessão: áreas com o nome certo e nenhum registro incompleto

Roteiro em **dev**, depois prod. Sem migration. Rota nova no API Gateway:
conferir por curl antes do smoke no painel (demora a propagar).

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
STAGE=dev; API_KEY=$(get /$STAGE/SCHEDULER_API_KEY)
URL=$(aws cloudformation describe-stacks --stack-name clinic-scheduler-infra-$STAGE \
  --query "Stacks[0].Outputs[?contains(OutputKey,'ServiceEndpoint')].OutputValue" --output text)
H=(-H "x-api-key: $API_KEY" -H "Content-Type: application/json")
C=clinicadepilacaopremium-3fbce9; S=<service_id>; D=2026-11-27
```

## Fixture

Agendamento `A` com **Perna Completa**, **Costeleta** e **Virilha Completa + ânus**
(ids das áreas em `GET $URL/services/$S/areas`). `P` = `patient_id` de A.

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | `GET $URL/clinics/$C/appointments/$A/session-applications` | 200; 4 aplicações: `Perna Completa`/`meia_perna`/"Meia perna"/SHR com sugestão; `Costeleta`/`costeleta`/método null; `Virilha Completa + ânus` ×2 (`virilha_completa` SHR; `regiao_perianal` Stacking) |
| 2 | mesmo GET com `clinicId` de outra clínica | 404 |
| 3 | `POST $URL/clinics/$C/patients/$P/session-records {"appointmentId": A}` sem `applications` | 400 "Informe applications" |
| 4 | `POST ... {"appointmentId": A, "applications": []}` | 400 "Informe ao menos uma área aplicada." |
| 5 | `POST ... applications: [{"areaName":"Costeleta"}]` | 400 "Costeleta: escolha o método." |
| 6 | `POST ... [{"areaName":"Axilas","method":"SHR","fluenceJ":8}]` | 400 "Axilas: informe Energia (kJ)." |
| 7 | `POST ... [{"areaName":"Perna Completa","protocolAreaKey":"meia_perna","method":"SHR","fluenceJ":8,"energyKj":8}]` | 201; `area_name` = "Perna Completa" |
| 8 | `PUT $URL/clinics/$C/session-records/$R {"applications": []}` | 400 |
| 9 | Painel (dev): Novo registro → escolher A → blocos "Perna Completa" com "parâmetros de Meia perna"; Costeleta sem método; Salvar → "Costeleta: escolha o método." com seletor em vermelho; apagar Energia da perna e Salvar → dois destaques e "Faltam 2 campos"; Remover Costeleta e preencher → salva | ok |

## Costeleta (investigação, prod, só leitura)

```sql
-- áreas ativas sem mapa, por clínica
SELECT a.clinic_id, a.name FROM scheduler.areas a
LEFT JOIN scheduler.area_protocol_map m ON m.area_id = a.id
WHERE a.active AND m.id IS NULL ORDER BY 1, 2;
-- a Costeleta nas duas tabelas
SELECT a.id, a.clinic_id, a.name, a.active, m.protocol_area_key
FROM scheduler.areas a LEFT JOIN scheduler.area_protocol_map m ON m.area_id = a.id
WHERE a.name ILIKE '%costel%';
```

## Resultado

Preencher ao rodar: data, stage, códigos por caso, resultado das consultas.
