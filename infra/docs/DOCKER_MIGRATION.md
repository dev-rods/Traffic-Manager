# Guia de Migração para Docker Images

Este documento descreve a migração das funções Lambda de layers para Docker images hospedadas no ECR.

## Por que Docker Images?

As dependências Python do projeto (especialmente `google-ads`, `cryptography`, etc.) excedem o limite de 250MB para Lambda layers. A solução é usar Docker images, que não têm essa limitação.

## O que foi alterado?

### 1. Dockerfile
- Criado `Dockerfile` baseado na imagem oficial AWS Lambda Python 3.8
- Instala todas as dependências do `requirements.txt`
- Copia o código fonte para a imagem

### 2. ECR Repository
- Criado recurso CloudFormation para o repositório ECR
- Configurado com lifecycle policy (mantém últimas 10 imagens)
- Habilitado scan automático de imagens

### 3. Configuração Serverless
- Removido `runtime: python3.8` do provider (não necessário com Docker)
- Adicionada configuração `provider.ecr.images` para build automático
- Todas as funções Lambda agora usam `image.name: lambdaImage` e `image.command`
- O Serverless Framework gerencia build, push e repositório ECR automaticamente

### 4. Funções Lambda
- Todas as funções foram atualizadas para usar Docker images
- Formato do comando: `src.functions.<module>.<file>.handler` (formato Python)
- Removidas referências a layers

## Estrutura de Arquivos

```
infra/
├── Dockerfile                    # Imagem Docker para Lambda
├── .dockerignore                 # Arquivos ignorados no build
├── serverless.yml                # Configuração atualizada
├── scripts/
│   ├── build-and-push-image.ps1  # Script PowerShell (Windows)
│   └── build-and-push-image.sh   # Script Bash (Linux/Mac)
└── sls/
    ├── resources/
    │   └── ecr/
    │       └── lambda-repository.yml  # Recurso ECR
    └── functions/
        └── [todas as funções atualizadas]
```

## Como Usar

### Passo 1: Build e Push da Imagem

**Windows:**
```powershell
.\scripts\build-and-push-image.ps1 -stage dev -region us-east-1
```

**Linux/Mac:**
```bash
chmod +x scripts/build-and-push-image.sh
./scripts/build-and-push-image.sh dev us-east-1
```

O script irá:
1. Verificar Docker e AWS CLI
2. Fazer login no ECR
3. Construir a imagem Docker
4. Fazer push para o ECR

### Passo 2: Deploy da Infraestrutura

```bash
serverless deploy --stage dev --aws-profile traffic-manager
```

**Nota**: Na primeira vez, o Serverless Framework criará o repositório ECR. Se você já executou o build antes, certifique-se de que o repositório existe.

### Passo 3: Testar

```bash
# Testar uma função
serverless invoke -f CampaignOrchestrator --stage dev --aws-profile traffic-manager

# Ver logs
serverless logs -f CampaignOrchestrator --stage dev --aws-profile traffic-manager
```

## Atualizando a Imagem

Sempre que você atualizar código ou dependências:

1. **Atualize `requirements.txt`** (se necessário)
2. **Deploy (build e push automáticos):**
   ```bash
   serverless deploy --stage dev
   ```

**Pronto!** O Serverless Framework detecta mudanças e faz build/push automaticamente. Não precisa executar scripts separados.

## Formato dos Handlers

Os handlers agora usam o formato de módulo Python:

**Antes (com layers):**
```yaml
handler: src/functions/campaign/orchestrator.handler
```

**Agora (com Docker - automático):**
```yaml
image:
  name: lambdaImage  # Referencia provider.ecr.images.lambdaImage
  command: ["src.functions.campaign.orchestrator.handler"]
```

## Troubleshooting

### Erro: "Repository does not exist"
- Execute o deploy primeiro: `serverless deploy --stage dev`
- Ou crie o repositório manualmente no console AWS

### Erro: "Image not found"
- Verifique se o build e push foram executados com sucesso
- Verifique se a tag da imagem está correta (default: `latest`)
- Verifique se o repositório ECR existe

### Erro: "Handler not found"
- Verifique se o formato do comando está correto (formato Python: `module.function`)
- Verifique se os arquivos `__init__.py` existem nas pastas necessárias

### Imagem muito grande
- Verifique o `.dockerignore` para excluir arquivos desnecessários
- Considere usar multi-stage builds se necessário

## Tamanho da Imagem

A imagem Docker resultante deve ter aproximadamente 300-400MB, o que está dentro dos limites da AWS Lambda (até 10GB para imagens).

## Benefícios

✅ Sem limitação de tamanho de dependências
✅ Controle total do ambiente de execução
✅ Facilita testes locais (mesmo ambiente)
✅ Melhor isolamento e segurança
✅ Suporte a dependências nativas complexas

## Próximos Passos

- [ ] Testar todas as funções após o deploy
- [ ] Configurar CI/CD para build automático
- [ ] Considerar tags versionadas em vez de `latest`
- [ ] Monitorar custos do ECR
