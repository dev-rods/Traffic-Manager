# Opções para Build e Push de Imagens Docker para ECR

Existem duas abordagens principais para fazer build e push de imagens Docker para o ECR. Esta documentação explica ambas e quando usar cada uma.

## Resumo Rápido

| Característica | Opção 1: Serverless Auto | Opção 2: Script Manual |
|----------------|-------------------------|------------------------|
| **AWS CLI necessário?** | ❌ Não | ✅ Sim (para login no ECR) |
| **Docker necessário?** | ✅ Sim | ✅ Sim |
| **Build automático?** | ✅ Sim, no deploy | ❌ Manual (via script) |
| **Controle do repositório ECR** | ⚠️ Serverless gerencia | ✅ Você controla (via CloudFormation) |
| **Complexidade** | 🟢 Baixa | 🟡 Média |

---

## Opção 1: Serverless Framework Automático (RECOMENDADO)

O Serverless Framework pode fazer build e push automaticamente usando `provider.ecr.images`. Você **não precisa do AWS CLI**, apenas do Docker.

### Vantagens
- ✅ Tudo automático no `serverless deploy`
- ✅ Não precisa de scripts separados
- ✅ Não precisa do AWS CLI
- ✅ Integração completa com o workflow do Serverless

### Desvantagens
- ⚠️ O Serverless Framework cria seu próprio repositório ECR
- ⚠️ Menos controle sobre a configuração do repositório ECR

### Como Configurar

1. **Atualize o `serverless.yml`:**

```yaml
provider:
  name: aws
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}
  
  # Adicione esta seção
  ecr:
    images:
      lambdaImage:
        path: .
```

2. **Atualize as funções para usar o nome da imagem:**

```yaml
functions:
  CampaignOrchestrator:
    image:
      name: lambdaImage  # Referencia a imagem definida em provider.ecr.images
      command: ["src.functions.campaign.orchestrator.handler"]
```

3. **Deploy (build e push automáticos):**

```bash
serverless deploy --stage dev
```

O Serverless Framework irá:
- Criar o repositório ECR automaticamente
- Fazer build da imagem Docker
- Fazer push para o ECR
- Deploy das funções Lambda

**Pronto!** Não precisa de mais nada.

---

## Opção 2: Script Manual (Atual)

Usa scripts para build e push manual antes do deploy. Requer AWS CLI para login no ECR.

### Vantagens
- ✅ Controle total sobre o repositório ECR (via CloudFormation)
- ✅ Você define lifecycle policies, scan settings, etc.
- ✅ Pode fazer build sem fazer deploy

### Desvantagens
- ❌ Precisa do AWS CLI instalado
- ❌ Processo em duas etapas (build → deploy)
- ❌ Mais scripts para manter

### Como Funciona Atualmente

1. **Build e push manual:**
   ```powershell
   .\scripts\build-and-push-image.ps1 -stage dev
   ```

2. **Deploy:**
   ```bash
   serverless deploy --stage dev
   ```

---

## Opção 3: Script Sem AWS CLI (Híbrida)

Você pode modificar o script para usar apenas Docker e as credenciais AWS que o Serverless Framework já usa (via variáveis de ambiente ou AWS profile).

### Como Funcionaria

O script usaria apenas:
- Docker (para build e push)
- Credenciais AWS via variáveis de ambiente ou `--aws-profile`

Mas ainda precisaria fazer login no ECR, que normalmente requer o AWS CLI. Uma alternativa seria usar o AWS SDK para Python/Node.js, mas isso adiciona complexidade.

**Recomendação:** Não vale a pena. Use a Opção 1 (Serverless automático) se não quer AWS CLI, ou mantenha a Opção 2 (atual) se quer controle total.

---

## Qual Escolher?

### Use **Opção 1 (Serverless Automático)** se:
- ✅ Você quer simplicidade
- ✅ Não quer instalar AWS CLI
- ✅ Quer tudo integrado no workflow do Serverless
- ⚠️ Não precisa de controle fino sobre o repositório ECR

### Use **Opção 2 (Script Manual)** se:
- ✅ Você quer controle total sobre o repositório ECR
- ✅ Já tem AWS CLI instalado
- ✅ Prefere processos separados (build e deploy)
- ✅ Quer lifecycle policies customizadas no ECR

---

## Migrando para Opção 1 (Serverless Automático)

Se quiser migrar para a abordagem automática:

1. **Remova o recurso ECR manual** do `serverless.yml`:
   ```yaml
   resources:
     # Remova esta linha:
     # - ${file(sls/resources/ecr/lambda-repository.yml)}
   ```

2. **Adicione `provider.ecr.images`**:
   ```yaml
   provider:
     ecr:
       images:
         lambdaImage:
           path: .
   ```

3. **Atualize todas as funções** para usar `name: lambdaImage` em vez de `uri: ...`

4. **Remova os scripts** (ou mantenha como backup)

5. **Deploy:**
   ```bash
   serverless deploy --stage dev
   ```

---

## Comparação de Comandos

### Opção 1 (Automático)
```bash
# Tudo em um comando!
serverless deploy --stage dev
```

### Opção 2 (Manual)
```powershell
# Passo 1: Build e push
.\scripts\build-and-push-image.ps1 -stage dev

# Passo 2: Deploy
serverless deploy --stage dev
```

---

## Conclusão

Para a maioria dos casos, **recomendo a Opção 1 (Serverless Automático)** pela simplicidade. Você só precisa:
- Docker instalado
- Credenciais AWS configuradas (como já tem para o Serverless)
- Executar `serverless deploy`

Sem necessidade de AWS CLI ou scripts extras!
