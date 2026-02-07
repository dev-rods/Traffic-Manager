# PRD — 004 Allowlist de telefones para envio de mensagens

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Implementar uma trava (feature flag) que restrinja o envio de mensagens WhatsApp apenas para numeros de telefone previamente autorizados. Isso garante que, durante desenvolvimento e testes, mensagens nao sejam enviadas acidentalmente para clientes reais.

---

## 2. Contexto

O sistema scheduler envia mensagens WhatsApp em 3 pontos: webhook (respostas conversacionais), endpoint `/send` (envio direto via API), e cron de reminders. Atualmente nao existe nenhuma trava — qualquer mensagem processada e enviada diretamente para o z-api.

Durante fases de desenvolvimento e homologacao, e necessario garantir que apenas numeros de teste recebam mensagens. A solucao deve ser simples (sem tabelas extras), centralizada (um unico ponto de controle), e facilmente desativavel quando o sistema estiver pronto para producao.

---

## 3. Escopo

### Dentro do escopo
- Variavel de ambiente `ALLOWED_PHONES` com lista de telefones autorizados (comma-separated)
- Guard centralizado na camada de provider que bloqueia envio para numeros nao autorizados
- Log claro quando uma mensagem for bloqueada
- Default seguro: quando `ALLOWED_PHONES` nao esta definida ou vazia, **todas as mensagens sao bloqueadas**
- Wildcard `*` para liberar todos os numeros (modo producao)
- Reutilizacao do `normalize_phone()` existente em `scheduler/src/utils/phone.py`
- Cobre todos os pontos de envio: webhook, /send, reminders

### Fora do escopo
- Interface administrativa para gerenciar a lista
- Armazenamento em banco de dados ou SSM
- Notificacao ao usuario de que a mensagem foi bloqueada (apenas log interno)

---

## 4. Areas / arquivos impactados

| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `scheduler/src/providers/zapi_provider.py` | modificar | Adicionar guard nos metodos `send_text`, `send_buttons`, `send_list` |
| `scheduler/src/providers/whatsapp_provider.py` | modificar | Adicionar funcao utilitaria `is_phone_allowed()` |
| `scheduler/serverless.yml` | modificar | Adicionar env var `ALLOWED_PHONES` |

---

## 5. Dependencias e riscos

- **Dependencias:** Reutiliza `normalize_phone()` de `scheduler/src/utils/phone.py` (ja existente).
- **Riscos:**
  - Se `ALLOWED_PHONES` nao for configurada em producao, todas as mensagens serao bloqueadas. Mitigacao: configurar `ALLOWED_PHONES=*` no ambiente de producao.
  - Formato de telefone e normalizado automaticamente via `normalize_phone()` (trata DDI 55, zero a esquerda, etc.).

---

## 6. Criterios de aceite

- [x] Mensagens para numeros na allowlist sao enviadas normalmente
- [x] Mensagens para numeros fora da allowlist sao bloqueadas com log WARNING
- [x] Mensagens bloqueadas retornam `ProviderResponse(success=True)` simulado (para nao quebrar fluxo)
- [x] Quando `ALLOWED_PHONES` nao esta definida ou vazia, todas as mensagens sao bloqueadas (default seguro)
- [x] Quando `ALLOWED_PHONES=*`, todas as mensagens passam (modo producao)
- [x] Guard cobre os 3 metodos de envio: `send_text`, `send_buttons`, `send_list`
- [x] Variavel configurada no `serverless.yml`
- [x] Reutiliza `normalize_phone()` de `src/utils/phone.py`

---

## 7. Referencias

- `CLAUDE.md` (padroes do projeto)
- `scheduler/src/providers/zapi_provider.py` (provider atual)
- `scheduler/src/providers/whatsapp_provider.py` (interface do provider)
- `scheduler/src/utils/phone.py` (normalize_phone reutilizado)

---

## Status (preencher apos conclusao)

- [x] Pendente
- [x] Spec gerada: `spec/004-message-allowlist.md`
- [x] Implementado em: 2026-02-07
- [ ] Registrado em `TASKS_LOG.md`
