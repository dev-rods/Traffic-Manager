# Mapeamento de fluxos — WhatsApp Scheduling Flow (Figma)

**Fonte:** [https://print-cream-02081339.figma.site/](https://print-cream-02081339.figma.site/)  
**Título:** WhatsApp Scheduling Flow  
**Criado com:** Figma Make  
**Remix (Figma Community):** [file/1597342041588746861](https://www.figma.com/community/file/1597342041588746861?openSignupModal=true)

**Contexto de negócio:** Laser Beauty (LB)

---

## Elementos identificados no carregamento inicial

| Elemento | Descrição |
|----------|-----------|
| **Título** | WhatsApp Scheduling Flow |
| **Marca/Cliente** | LB — Laser Beauty |
| **Estado de UI** | "digitando..." (indicador de digitação no chat) |

> **Nota:** O site Figma é um protótipo interativo. A inspeção via fetch HTTP capturou só o HTML inicial. **Para mapear todos os fluxos, é necessário navegar manualmente no link**, clicando em cada frame, botão e transição do protótipo.

---

## Estrutura de fluxos (template para preenchimento)

Use a tabela abaixo para registrar cada fluxo que você encontrar ao navegar no protótipo. Inclua: nome do fluxo, gatilho (ex.: mensagem do usuário, clique em botão), tela(s)/estado(s) e resultado ou próxima ação.

### Fluxo 1 — [Nome do fluxo]

| Campo | Descrição |
|-------|-----------|
| **Objetivo** | Ex.: Agendar horário, confirmar atendimento, escolher serviço |
| **Gatilho** | Ex.: Usuário envia "Olá", clica em "Agendar", responde a lista interativa |
| **Telas / Estados** | 1. Tela X → 2. Tela Y → 3. ... |
| **Decisões (if/else)** | Ex.: Se escolher "Manutenção" → fluxo A; se "Nova cliente" → fluxo B |
| **Resultado** | Ex.: Horário agendado, mensagem de confirmação, lead qualificado |
| **Observações** | Imagens, templates, botões, listas, variáveis de template |

---

### Fluxo 2 — [Nome do fluxo]

*(replicar a mesma tabela para cada fluxo identificado)*

---

### Fluxo 3 — [Nome do fluxo]

*(idem)*

---

## Fluxos típicos em “WhatsApp Scheduling” (referência)

Com base em padrões comuns de agendamento via WhatsApp e no [PROMPT_WHATSAPP_MESSAGING_SERVICE.md](./PROMPT_WHATSAPP_MESSAGING_SERVICE.md), estes são fluxos que **podem** existir no protótipo. Confira no Figma e marque ou ajuste:

| # | Nome provável | Descrição breve | Relação com o backend |
|---|----------------|-----------------|------------------------|
| 1 | **Boas-vindas / Menu** | Primeira interação; menu com opções (Agendar, Remarcar, Cancelar, Falar com atendente) | Webhook: `text` ou `button` → enviar template/list interativa |
| 2 | **Escolha de serviço** | Cliente escolhe tipo de serviço (ex.: depilação, design de sobrancelhas) | Webhook: `interactive.list_reply` ou `button` → próximo template |
| 3 | **Escolha de data** | Seleção de data (calendar picker ou lista de datas) | Template ou interactive → webhook processa e responde com horários |
| 4 | **Escolha de horário** | Lista de horários disponíveis | `list_reply` / `button` → confirmar e persistir agendamento |
| 5 | **Confirmação** | Resumo (serviço, data, horário) + botão Confirmar/Cancelar | `button` → sender persiste e envia confirmação |
| 6 | **Confirmação enviada** | Mensagem final “Agendamento confirmado” (e opcional: lembrete) | Sender (template ou texto) |
| 7 | **Remarcar** | Cliente pede remarcar → escolher novo horário | Similar aos fluxos 3–6, com passo “qual agendamento?” antes |
| 8 | **Cancelar** | Cliente cancela → confirmação de cancelamento | `button` → sender atualiza estado e envia template |
| 9 | **Falar com atendente** | Encaminha para fila humana ou encerra com “em breve retornamos” | Webhook: registra intenção; sender: mensagem de status |
| 10 | **Digitando… / Erro** | Estados de “digitando” ou mensagem de erro (ex.: horário indisponível) | “digitando” = indicador de UI; erros = templates ou texto do sender |

---

## Como completar este mapeamento

1. Abra [https://print-cream-02081339.figma.site/](https://print-cream-02081339.figma.site/) no navegador.
2. Percorra **todos os frames** do protótipo (setas, hotspots, troca de device).
3. Para cada **fluxo** (caminho de telas com início e fim):
   - Preencha uma seção **“Fluxo N — [Nome]”** com a tabela de Objetivo, Gatilho, Telas, Decisões, Resultado e Observações.
   - Se encontrar fluxos que não estão na tabela de “Fluxos típicos”, crie novas linhas ou seções.
4. Se existir **telas de erro, timeout ou fallback** (ex.: “não entendi”, “tente de novo”), documente como fluxos ou subfluxos.
5. Atualize a **“Última atualização”** no final do documento.

---

## Relação com o backend (WhatsApp Messaging Service)

- **Webhook** (`POST /webhook/whatsapp`): recebe `messages` (texto, `button`, `interactive`), `message_template_status_update`, etc. Cada decisão de fluxo (if/else por `button.payload`, `list_reply.id`, `text.body`) deve estar refletida no handler.
- **Senders**: envio de texto, template (com botões, listas) e interactive. Cada tela do Figma que representa “resposta do sistema” corresponde a uma ou mais chamadas de envio.
- **Templates**: nomes e estrutura (body, botões, listas) usados no protótipo devem ser alinhados ao CRUD de templates e ao catálogo aprovado na Meta.

---

## Última atualização

- **Data:** *(preencher após navegar no Figma)*  
- **Revisado por:** *(opcional)*  
- **Fluxos mapeados:** *(número e nomes)*
