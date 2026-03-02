# Design: Offline Conversion Upload para Google Ads

**Data:** 2026-03-01
**Autor:** dev-andre
**Status:** Aprovado (aguardando implementacao)

---

## Objetivo

Enviar conversoes reais (agendamentos) de volta ao Google Ads via Offline Conversion Upload API, conectando o GCLID capturado no WhatsApp ao agendamento realizado. Isso permite que o algoritmo do Google (Target CPA / Maximize Conversions) otimize lances baseado em **agendamentos reais com valor**, nao apenas cliques no botao do WhatsApp.

## Contexto

### Problema

O Google Ads otimiza lances baseado em conversoes "rasas" (clique no WhatsApp + envio de formulario). Nem todo lead que clica converte em agendamento. O algoritmo pode estar gastando mais dinheiro em cliques que nunca geram receita.

### O que ja existe

- Tabela `scheduler.leads` no PostgreSQL com GCLID, phone, booked, first_appointment_value (implementado em 2026-03-01)
- Webhook do WhatsApp extrai GCLID automaticamente da mensagem `(ref: GCLID)`
- Quando um appointment e criado, o lead e marcado como `booked=TRUE` com valor
- Google Ads API v20 integrada no infra/ com `GoogleAdsClientService`
- Modelo economico com CPA saudavel ja calculado
- Estrategia de lance atual: Maximize Conversions / Target CPA
- Conversoes configuradas no Google Ads: clique WhatsApp + envio de formulario

### Abordagem escolhida: Hibrida (Fase 1)

Deixar o Google fazer o que faz bem (bidding com ML) e alimenta-lo com dados de conversao melhores. Fases futuras adicionam automacoes complementares (keywords, budget, etc.).

---

## Design Tecnico

### Fluxo de Dados

```
Lead clica WhatsApp -> GCLID salvo na tabela leads (ja implementado)
     |
Lead agenda sessao -> booked=TRUE + valor (ja implementado)
     |
Lambda scheduled (diario, 7h BRT) -> busca leads convertidos pendentes
     |
Google Ads Offline Conversion Upload API -> envia GCLID + timestamp + valor
     |
Marca lead como "conversion_sent" -> evita reenvio
```

### Regras de Negocio

- So envia leads com `gclid IS NOT NULL` e `booked = TRUE` e `conversion_uploaded_at IS NULL`
- O GCLID tem validade de **90 dias** no Google Ads — leads mais antigos sao ignorados
- Envia `first_appointment_value` como valor da conversao (em BRL)
- O timestamp da conversao e o `updated_at` do lead (momento do agendamento)
- Em caso de falha no upload, o lead NAO e marcado — sera retentado no proximo ciclo
- Conversoes parciais (batch com falha em alguns itens) marcam apenas os que foram enviados com sucesso

### Alteracoes no Banco de Dados

**PostgreSQL** — nova coluna na tabela `scheduler.leads`:

```sql
ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS conversion_uploaded_at TIMESTAMPTZ;
```

### Arquivos a Criar/Modificar

| Arquivo | Acao | Descricao |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | Modificar | Migration: coluna `conversion_uploaded_at` |
| `scheduler/src/services/lead_service.py` | Modificar | Metodos `get_pending_conversions()` e `mark_conversion_uploaded()` |
| `infra/src/services/google_ads_client_service.py` | Modificar | Metodo `upload_offline_conversions()` usando ConversionUploadService |
| `infra/src/functions/conversions/uploader.py` | Criar | Lambda handler scheduled (EventBridge cron) |
| `infra/sls/functions/conversions/interface.yml` | Criar | Config da Lambda com schedule e IAM roles |
| `infra/serverless.yml` | Modificar | Incluir interface de conversions |

### Google Ads API — Metodo de Upload

```python
from google.ads.googleads.client import GoogleAdsClient

def upload_offline_conversions(client, customer_id, conversion_action_id, conversions):
    """
    conversions: list of {gclid, conversion_date_time, conversion_value}
    """
    conversion_upload_service = client.get_service("ConversionUploadService")

    click_conversions = []
    for conv in conversions:
        click_conversion = client.get_type("ClickConversion")
        click_conversion.gclid = conv["gclid"]
        click_conversion.conversion_action = (
            f"customers/{customer_id}/conversionActions/{conversion_action_id}"
        )
        click_conversion.conversion_date_time = conv["conversion_date_time"]  # "2026-03-01 10:00:00-03:00"
        click_conversion.conversion_value = conv["conversion_value"]
        click_conversion.currency_code = "BRL"
        click_conversions.append(click_conversion)

    response = conversion_upload_service.upload_click_conversions(
        customer_id=customer_id,
        conversions=click_conversions,
        partial_failure=True,  # continua mesmo se alguns falharem
    )

    return response
```

### Lambda Scheduled — Logica do Uploader

```python
def handler(event, context):
    # 1. Buscar todos os clientes ativos com Google Ads config
    # 2. Para cada cliente:
    #    a. Buscar leads pendentes (booked=TRUE, gclid NOT NULL, conversion_uploaded_at IS NULL, created_at > 90 dias atras)
    #    b. Montar batch de conversoes
    #    c. Chamar upload_offline_conversions()
    #    d. Para cada conversao com sucesso, marcar conversion_uploaded_at = NOW()
    #    e. Logar falhas para retry no proximo ciclo
    # 3. Registrar execucao no ExecutionHistory
```

### EventBridge Schedule

```yaml
# interface.yml
ConversionUploader:
  handler: src.functions.conversions.uploader.handler
  timeout: 300  # 5 min (batch pode ser grande)
  events:
    - schedule:
        rate: cron(0 10 * * ? *)  # 7h BRT = 10h UTC, diario
        enabled: true
```

### Configuracao do Cliente

O `conversion_action_id` sera armazenado no `optimization_config` do cliente na tabela `Clients` do DynamoDB:

```json
{
  "optimization_config": {
    "average_ticket": 270.0,
    "ltv_months": 6,
    "net_margin": 0.60,
    "lead_to_sale_conversion_rate": 0.20,
    "safety_factor": 0.70,
    "offline_conversion_action_id": "123456789"
  }
}
```

---

## Requisitos no Google Ads (manual, antes da implementacao)

### 1. Criar Conversion Action para Offline

No Google Ads (`ads.google.com`):

1. Ir em **Goals > Conversions > Summary**
2. Clicar **+ New conversion action**
3. Selecionar **Import > Other data sources or CRMs > Track conversions from clicks**
4. Configurar:
   - **Nome:** `Agendamento Real` (ou nome descritivo)
   - **Category:** `Purchase/Sale` ou `Lead`
   - **Value:** `Use different values for each conversion` (o valor vem do agendamento)
   - **Count:** `One` (1 conversao por lead, nao conta re-agendamentos)
   - **Click-through conversion window:** `90 days`
   - **Attribution model:** `Data-driven` (recomendado) ou `Last click`
5. Salvar e anotar o **Conversion Action ID** (numero que aparece na URL ou via API)

### 2. Configurar como Conversao Primaria

Para que o Target CPA/Maximize Conversions use essa conversao:

1. Na lista de Conversion Actions, clicar na conversao `Agendamento Real`
2. Em **Goal and action optimization**, marcar como **Primary action**
3. (Opcional) Considerar mudar as conversoes de WhatsApp/formulario para **Secondary** para que o Google otimize para agendamentos, nao cliques

**IMPORTANTE:** Fazer a mudanca Primary/Secondary so depois de ter pelo menos 30-50 conversoes offline registradas (2-4 semanas de dados). Mudar antes pode desestabilizar o algoritmo.

### 3. Verificar Permissoes da API

- A conta de servico (developer token) precisa ter permissao de **Standard Access** ou superior
- O usuario que gerou o refresh_token precisa ter role **Admin** ou **Standard** na conta Google Ads
- A Google Ads API v20 suporta `ConversionUploadService` — ja estamos nessa versao

### 4. Validar GCLID Auto-tagging

- Verificar que **auto-tagging** esta ativado na conta Google Ads (Settings > Account settings > Auto-tagging > ON)
- Sem auto-tagging, o GCLID nao e gerado e o upload de conversoes offline nao funciona

---

## Fase 2 — Automacao Complementar (futuro)

Apos a Fase 1 estar estavel (4-6 semanas de dados), implementar automacoes nas alavancas que o Google NAO controla:

| Alavanca | Frequencia | Descricao |
|----------|-----------|-----------|
| Negativacao de keywords | Diario | Identificar search terms com custo alto e 0 conversoes, negativar automaticamente |
| Expansao de keywords | Semanal | Identificar search terms com conversao e que nao sao keywords, adicionar |
| Budget redistribution | Semanal | Mover budget de campanhas com CPA alto para campanhas com CPA baixo |
| Pausar anuncios ruins | Semanal | Pausar anuncios com CTR < threshold por 30+ dias |
| Alertas de anomalia | Diario | Notificar se CPA subir >30% ou conversoes cairem >50% vs media |

Essas automacoes usarao os dados de conversao **real** (offline) como metrica de decisao, nao os cliques rasos.

---

## Metricas de Sucesso

Apos 30 dias de Fase 1:
- Conversoes offline aparecendo no Google Ads com valores corretos
- CPA calculado pelo Google reflete agendamentos reais (nao cliques)
- ROAS melhora porque o Google otimiza para leads que realmente agendam

Apos 60 dias:
- Comparar ROAS do periodo com Fase 1 vs periodo anterior
- Avaliar se o Target CPA esta convergindo para o CPA saudavel do modelo economico
