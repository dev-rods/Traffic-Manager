# Configuração
Arquivo .aws/credentials

```
[default]
aws_access_key_id = sua_access_key_id
aws_secret_access_key = sua_secret_access_key
```


# Deploy

serverless deploy --stage dev --aws-profile traffic-manager

# Instalar plugins
serverless plugin install -n serverless-step-functions
serverless plugin install -n serverless-iam-roles-per-function

## Info
serverless info --verbose --aws-profile traffic-manager
serverless print

# Start
serverless invoke stepf --name CampaignOptimizationFlow -s dev --aws-profile traffic-manager 