# Guia Rápido: Docker Images SEM AWS CLI

## ✅ Resposta Rápida

**NÃO, você não precisa do AWS CLI!** O Serverless Framework pode fazer build e push automaticamente.

Você só precisa:
- ✅ Docker instalado
- ✅ Credenciais AWS (já configuradas para o Serverless)
- ✅ Executar `serverless deploy`

---

## 🚀 Como Funciona

O Serverless Framework tem suporte nativo para Docker images. Quando você configura `provider.ecr.images`, ele:
1. Cria o repositório ECR automaticamente
2. Faz build da imagem Docker
3. Faz push para o ECR
4. Deploy das funções Lambda

**Tudo em um comando!**

---

## 📝 Configuração (5 minutos)

### 1. Atualize `serverless.yml`

Adicione a seção `ecr.images` no provider:

```yaml
provider:
  name: aws
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}
  
  # NOVO: Build automático de Docker image
  ecr:
    images:
      lambdaImage:
        path: .
```

### 2. Atualize as funções

Mude de `uri:` para `name:` nas funções:

**Antes:**
```yaml
CampaignOrchestrator:
  image:
    uri: ${self:custom.ecrImageUri}
    command: ["src.functions.campaign.orchestrator.handler"]
```

**Depois:**
```yaml
CampaignOrchestrator:
  image:
    name: lambdaImage  # Referencia a imagem em provider.ecr.images
    command: ["src.functions.campaign.orchestrator.handler"]
```

### 3. Remova o recurso ECR manual (opcional)

Se quiser que o Serverless gerencie o repositório, remova do `resources`:
```yaml
resources:
  # Remova esta linha se quiser que Serverless crie o repositório:
  # - ${file(sls/resources/ecr/lambda-repository.yml)}
```

---

## 🎯 Deploy

Agora é só executar:

```bash
serverless deploy --stage dev --aws-profile traffic-manager
```

O Serverless Framework irá:
1. ✅ Fazer build da imagem Docker
2. ✅ Fazer push para ECR (cria repositório se não existir)
3. ✅ Deploy das funções Lambda

**Pronto! Sem scripts, sem AWS CLI!**

---

## 🔄 Atualizando

Quando você mudar o código ou dependências:

```bash
# Apenas isso! O Serverless faz build e push automaticamente
serverless deploy --stage dev
```

---

## ⚠️ Diferença Importante

### Abordagem Atual (com scripts)
```powershell
# Passo 1: Precisa AWS CLI para login no ECR
.\scripts\build-and-push-image.ps1 -stage dev

# Passo 2: Deploy
serverless deploy --stage dev
```

### Abordagem Automática (recomendada)
```bash
# Apenas um comando! Usa as credenciais AWS que já tem
serverless deploy --stage dev
```

---

## 📚 Documentação Completa

Para mais detalhes e comparação das opções, veja:
- [ECR_OPTIONS.md](./ECR_OPTIONS.md) - Comparação detalhada
- [DOCKER_MIGRATION.md](./DOCKER_MIGRATION.md) - Guia completo de migração

---

## ❓ FAQ

**P: Mas eu quero controlar o repositório ECR (lifecycle policies, etc.)**
R: Você pode manter o recurso ECR manual no CloudFormation e ainda usar `provider.ecr.images`. O Serverless tentará usar o repositório existente ou criar um novo.

**P: Posso fazer build sem fazer deploy?**
R: Com a abordagem automática, não. O build acontece durante o deploy. Se precisar build separado, mantenha os scripts.

**P: E se eu já tenho AWS CLI instalado?**
R: Pode manter a abordagem atual (scripts). A automática é apenas mais conveniente.

**P: Qual é melhor?**
R: Para simplicidade → Automática. Para controle total → Scripts manuais.
