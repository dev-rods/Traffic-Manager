## How to run a script

# Generate a refresh token
C:/Users/Rodri/AppData/Local/Programs/Python/Python311/python.exe "c:/Users/Rodri/Documents/Gestao de Trafego Automatizada/projects/infra/src/scripts/generate_refresh_token.py" -c "C:\Users\Rodri\Documents\Gestao de Trafego Automatizada\Nova pasta\client_secret.json"

Acessar o link:
https://us-east-1.console.aws.amazon.com/systems-manager/parameters/%252Fdev%252FGOOGLE_ADS_REFRESH_TOKEN/description?region=us-east-1&tab=Table

Adicionar lá a variavel gerada pelo primeiro passo

# Test postgres
serverless invoke -f ScriptManager --aws-profile traffic-manager -s dev -p .\tests\mocks\postgres\health_check.json

