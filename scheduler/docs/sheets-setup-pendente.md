# Google Sheets Setup - Próximos Passos

## Problema atual

A service account recebe **403 "The caller does not have permission"** ao tentar criar spreadsheets via Google Sheets API. Já tentamos:

- [x] Ativar Google Sheets API e Google Drive API no projeto
- [x] Atribuir role Editor à service account no IAM
- [x] Confirmar que a key JSON bate com a service account
- [x] Criar novo projeto fora de organização (scheduler-sheets-487501)
- [x] Criar nova service account com key nova

## O que investigar

1. **Confirmar que o `.env` aponta para a key nova** — rodar:
   ```bash
   python -c "import json,os; from dotenv import load_dotenv; load_dotenv(); sa=json.loads(os.environ['GOOGLE_SHEETS_SERVICE_ACCOUNT']); print(sa.get('client_email'), sa.get('project_id'))"
   ```
   Deve mostrar o projeto novo (`scheduler-sheets-487501`), não o antigo.

2. **Verificar se o `.env` tem parsing correto** — o JSON deve estar em UMA linha, entre aspas simples:
   ```
   GOOGLE_SHEETS_SERVICE_ACCOUNT='{"type":"service_account","project_id":"scheduler-sheets-487501",...}'
   ```
   Se tiver quebra de linha, o dotenv não parseia corretamente e pode usar uma variável de ambiente do sistema em vez do `.env`.

3. **Verificar variável de ambiente do sistema** — pode existir um `GOOGLE_SHEETS_SERVICE_ACCOUNT` nas variáveis de ambiente do Windows (que tem prioridade sobre o `.env`):
   ```bash
   echo %GOOGLE_SHEETS_SERVICE_ACCOUNT%
   ```
   Se retornar algo, remover das variáveis de ambiente do sistema.

4. **Testar com credenciais diretamente do arquivo** (sem dotenv):
   ```bash
   python -c "import json; from google.oauth2.service_account import Credentials; from googleapiclient.discovery import build; sa=json.load(open('sa.json')); creds=Credentials.from_service_account_info(sa, scopes=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']); svc=build('sheets','v4',credentials=creds); r=svc.spreadsheets().create(body={'properties':{'title':'Teste'}},fields='spreadsheetId').execute(); print('OK:',r)"
   ```
   Se isso funcionar, o problema é no parsing do `.env`. Se falhar igual, é configuração do Google Cloud.

5. **Verificar no Google Cloud Console** que as APIs estão ativas no projeto correto:
   - Ir em https://console.cloud.google.com/apis/dashboard?project=scheduler-sheets-487501
   - Confirmar que Google Sheets API e Google Drive API aparecem em "Enabled APIs"

## Após resolver o 403

1. Rodar o script para criar planilhas das clínicas existentes:
   ```bash
   cd scheduler && python -m src.scripts.create_spreadsheets
   ```

2. Atualizar o SSM na AWS com a nova service account key:
   ```bash
   aws ssm put-parameter --name "/prod/GOOGLE_SHEETS_SERVICE_ACCOUNT" --type SecureString --value '$(cat sa.json | python -c "import json,sys; print(json.dumps(json.load(sys.stdin)))")' --overwrite --profile traffic-manager
   ```

3. Criar o token do webhook no SSM:
   ```bash
   aws ssm put-parameter --name "/prod/SHEETS_WEBHOOK_TOKEN" --type SecureString --value "GERAR_UM_TOKEN_SEGURO_AQUI" --overwrite --profile traffic-manager
   ```

4. Deploy:
   ```bash
   cd scheduler && serverless deploy --stage prod --aws-profile traffic-manager
   ```

5. Configurar Apps Script na planilha criada — seguir `scheduler/docs/apps-script-setup.md`

## Arquivos relevantes

- `scheduler/src/scripts/create_spreadsheets.py` — script bulk para criar planilhas
- `scheduler/src/services/sheets_sync.py` — serviço de sync
- `scheduler/docs/apps-script-setup.md` — código do Apps Script
- `scheduler/src/functions/sheets/webhook.py` — endpoint bidirecional
