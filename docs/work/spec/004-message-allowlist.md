# Spec — 004 Allowlist de telefones para envio de mensagens

> Gerado na fase **Spec**. Use como input para a fase Code (implementacao).

- **PRD de origem:** `prd/004-message-allowlist.md`

---

## 1. Resumo

Adicionar um guard centralizado na camada de provider (ZApiProvider) que verifica se o telefone destinatario esta numa allowlist antes de enviar qualquer mensagem. A allowlist e configurada via variavel de ambiente `ALLOWED_PHONES` (comma-separated). Comportamento: vazia/nao definida = bloqueia tudo (default seguro); `*` = libera tudo (modo producao); lista de telefones = permite apenas os listados. Reutiliza `normalize_phone()` de `src/utils/phone.py` para normalizacao.

---

## 2. Arquivos a criar

Nenhum.

---

## 3. Arquivos a modificar

| Arquivo | Alteracoes |
|---------|------------|
| `scheduler/src/providers/whatsapp_provider.py` | Adicionar funcao `is_phone_allowed(phone)` |
| `scheduler/src/providers/zapi_provider.py` | Adicionar metodo `_check_allowlist(phone)` e chamar no inicio de `send_text`, `send_buttons`, `send_list` |
| `scheduler/serverless.yml` | Adicionar env var `ALLOWED_PHONES` |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementacao sugerida

1. `scheduler/src/providers/whatsapp_provider.py` — adicionar `is_phone_allowed()`
2. `scheduler/src/providers/zapi_provider.py` — adicionar guard nos metodos de envio
3. `scheduler/serverless.yml` — adicionar env var

---

## 6. Detalhes por arquivo

### `scheduler/src/providers/whatsapp_provider.py`

- **Modificar**
- Adicionar import de `normalize_phone` de `src.utils.phone` (reutilizacao)
- Adicionar funcao standalone `is_phone_allowed(phone: str) -> bool`:
  - Le `os.environ.get("ALLOWED_PHONES", "")`
  - Se vazio/nao definido, retorna `False` (default seguro — bloqueia tudo)
  - Se valor e `*`, retorna `True` (modo producao — libera tudo)
  - Faz split por virgula, strip de espacos
  - Usa `normalize_phone()` existente para normalizar phone e lista (trata DDI 55, zero a esquerda)
  - Retorna `True` se phone normalizado esta na lista normalizada

### `scheduler/src/providers/zapi_provider.py`

- **Modificar**
- Adicionar metodo privado `_check_allowlist(self, phone: str) -> Optional[ProviderResponse]`:
  - Chama `is_phone_allowed(phone)`
  - Se nao permitido: loga WARNING com phone (ultimos 4 digitos) e retorna `ProviderResponse(success=True, provider_message_id="blocked-by-allowlist")`
  - Se permitido: retorna `None` (sinaliza para continuar envio)
- Chamar `_check_allowlist` no inicio de `send_text`, `send_buttons`, `send_list`:
  - `blocked = self._check_allowlist(phone); if blocked: return blocked`

### `scheduler/serverless.yml`

- **Modificar**
- Adicionar no bloco `environment`:
  ```yaml
  # Message allowlist (comma-separated phones, empty = block all, * = allow all)
  ALLOWED_PHONES: ${env:ALLOWED_PHONES, ''}
  ```
- Usa `${env:ALLOWED_PHONES, ''}` para ler de variavel local do ambiente (nao SSM), com default vazio (bloqueia tudo)

---

## 7. Convencoes a respeitar

- Logging: usar `logger.warning(...)` para mensagens bloqueadas
- Phone masking no log: mostrar apenas ultimos 4 digitos para privacidade
- Reutilizar `normalize_phone()` de `src/utils/phone.py` (nao duplicar logica de normalizacao)
- Manter compatibilidade com a interface `WhatsAppProvider` abstrata
- Python 3.8: usar `Optional[X]` ao inves de `X | None`
