# PRD-002: Leads Registration System

**Status:** Implemented
**Created:** 2025-01-24
**Author:** Claude

---

## 1. Problema / Objetivo

O frontend (Lovable) atualmente envia dados de leads apenas para Google Sheets. Precisamos:
- Armazenar leads no nosso sistema para processamento posterior
- Agrupar leads por cliente (`clientId`)
- Ter um endpoint publico que aceite requisicoes do frontend com CORS
- Manter registro de todos os leads capturados por cada cliente

### Requisitos do Usuario
1. Endpoint para receber dados de leads do frontend
2. Armazenar: `name`, `email`, `phone`, `location`, `timestamp`, `clientId`
3. Agrupar leads por cliente para consultas futuras
4. Endpoint para listar leads de um cliente especifico
5. Suportar CORS para chamadas do frontend

---

## 2. Solucao Proposta

### 2.1 Nova Tabela DynamoDB: Leads

**Estrutura:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `leadId` (PK) | String | UUID unico do lead |
| `clientId` | String | ID do cliente que capturou o lead |
| `name` | String | Nome do lead |
| `email` | String | Email do lead |
| `phone` | String | Telefone do lead |
| `location` | String | Localizacao do lead |
| `source` | String | Origem do lead (ex: landing-page, form, etc.) |
| `createdAt` | String | ISO timestamp da captura |
| `metadata` | Map | Dados adicionais opcionais |

**Indices:**
- **GSI `clientId-createdAt-index`**: Para query por clientId ordenado por data
  - Partition Key: `clientId`
  - Sort Key: `createdAt`

### 2.2 Novo Handler: `create_lead.py`

**Endpoint:** `POST /leads`

**Body:**
```json
{
  "clientId": "string (required)",
  "name": "string (required)",
  "email": "string (required)",
  "phone": "string (optional)",
  "location": "string (optional)",
  "source": "string (optional, default: 'web-form')",
  "metadata": { } (optional)
}
```

**Fluxo:**
1. Validar campos obrigatorios (`clientId`, `name`, `email`)
2. Gerar `leadId` unico (UUID)
3. Adicionar `createdAt` com timestamp atual
4. Salvar na tabela Leads
5. Retornar `leadId` e dados salvos

**Respostas:**
- `201 Created`: Lead registrado com sucesso
- `400 Bad Request`: Campos obrigatorios ausentes
- `401 Unauthorized`: API key invalida

### 2.3 Novo Handler: `list_leads.py`

**Endpoint:** `GET /leads?clientId={clientId}`

**Query Params:**
- `clientId` (required): ID do cliente
- `startDate` (optional): Filtrar leads a partir desta data (ISO)
- `endDate` (optional): Filtrar leads ate esta data (ISO)
- `limit` (optional): Limite de resultados (default: 100)

**Resposta:**
```json
{
  "status": "SUCCESS",
  "leads": [
    {
      "leadId": "uuid",
      "clientId": "client-123",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+55 11 99999-9999",
      "location": "Sao Paulo",
      "source": "web-form",
      "createdAt": "2025-01-24T10:00:00Z"
    }
  ],
  "count": 1
}
```

### 2.4 Novo Handler: `get_lead.py`

**Endpoint:** `GET /leads/{leadId}`

**Path Params:**
- `leadId` (required): ID unico do lead

**Fluxo:**
1. Validar API key
2. Extrair `leadId` do path
3. Buscar lead na tabela pelo `leadId`
4. Retornar dados do lead ou 404 se nao encontrado

**Resposta:**
```json
{
  "status": "SUCCESS",
  "lead": {
    "leadId": "uuid",
    "clientId": "client-123",
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+55 11 99999-9999",
    "location": "Sao Paulo",
    "source": "web-form",
    "createdAt": "2025-01-24T10:00:00Z",
    "metadata": {}
  }
}
```

**Respostas:**
- `200 OK`: Lead encontrado
- `400 Bad Request`: leadId nao fornecido
- `401 Unauthorized`: API key invalida
- `404 Not Found`: Lead nao existe

---

## 3. Arquivos Afetados

### Novos Arquivos
- `sls/resources/dynamodb/leads-table.yml` - Definicao da tabela DynamoDB
- `sls/functions/leads/interface.yml` - Configuracao das funcoes Lambda
- `src/functions/leads/__init__.py` - Modulo Python
- `src/functions/leads/create.py` - Handler para criar lead
- `src/functions/leads/list.py` - Handler para listar leads por clientId
- `src/functions/leads/get.py` - Handler para buscar lead por leadId

### Arquivos Modificados
- `serverless.yml` - Importar novas funcoes e tabela

### Arquivos Potencialmente Removidos
- Nenhum

---

## 4. Dependencias

- UUID library (ja disponivel via `uuid` do Python stdlib)
- Boto3 para DynamoDB (ja instalado)
- Reutilizar `src/utils/http.py` para handlers
- Reutilizar `src/utils/decimal_utils.py` para conversoes

---

## 5. Consideracoes

### Frontend Integration
```javascript
// Exemplo de integracao no Lovable
const sendToTrafficManager = async (data) => {
  const payload = {
    clientId: "meu-client-id",
    name: data.name,
    email: data.email,
    phone: data.phone,
    location: data.location,
    source: "landing-page"
  };

  const response = await fetch("https://api.traffic-manager.com/leads", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": "API_KEY"
    },
    body: JSON.stringify(payload)
  });

  return response.json();
};
```

### Performance
- GSI permite queries eficientes por clientId ordenadas por data
- PAY_PER_REQUEST para billing on-demand

### Seguranca
- Validar API key em todos os endpoints
- Validar que clientId existe antes de salvar (opcional - pode ser relaxado para performance)

### CORS
- Habilitar CORS em todos os endpoints para permitir chamadas do frontend

---

## 6. Decisoes a Tomar

1. **Validacao de clientId**: Validar se o clientId existe na tabela Clients antes de salvar o lead?
   - Pro: Garante integridade dos dados
   - Contra: Adiciona latencia e dependencia da tabela Clients

2. **Rate Limiting**: Implementar rate limiting por clientId para evitar abusos?
   - Pode ser implementado posteriormente via API Gateway

3. **Duplicatas**: Verificar se email ja existe para o mesmo clientId?
   - Pode ser implementado posteriormente conforme necessidade

---

## Historico

| Data | Status | Notas |
|------|--------|-------|
| 2025-01-24 | Draft | PRD criado |
| 2025-01-24 | Spec Generated | Spec criada em docs/work/spec/002-leads-registration.md |
| 2025-01-24 | Implemented | Codigo implementado |
