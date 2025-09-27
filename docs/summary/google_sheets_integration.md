# Google Sheets Integration

## Para inserir um novo cliente:
Personalizamos o arquivo em tests/mocks/scripts/manager/create_client.json
serverless invoke local -s dev -f ScriptManager -p tests/mocks/scripts/manager/create_client.json --aws-profile traffic-manager

## Agora devemos associar esse novo cliente ao nosso MCC


## Summary

parse_form_data() no handler.py é quem parseia os dados do formulário do Google Sheets. Qualquer modificação no google sheets deve ser refletida nesse método.

