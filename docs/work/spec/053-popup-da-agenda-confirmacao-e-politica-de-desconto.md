# Spec - 053 Pop-up da agenda: confirmação antes de mandar mensagem e política de desconto da clínica como padrão

> Gerada em 20/11/2026 a partir de `prd/053-popup-da-agenda-confirmacao-e-politica-de-desconto.md`. Decisões da §4 confirmadas pelo André em 20/11 (3 alterada: falta e confirmado também confirmam; 7: estreia é o banco; 8: combinado da paciente pré-preenchido).
> Fluxo: código → PR → deploy dev (backend primeiro) → roteiro → prod com o André. Sem migration.

---

## 1. O que muda, em três frases

No painel, seis ações do pop-up deixam de executar no primeiro clique e passam por um componente único de confirmação inline com "Voltar": link de cobrança (também no Caixa), link dos documentos, recebi em dinheiro, pedir nova assinatura, marcar falta e marcar como confirmado. No desconto, nasce o modo **"Política da clínica"**, padrão do "Novo agendamento" (salvo paciente com combinado, que abre em "Personalizado N%"), com cotação ao vivo por uma rota autenticada nova; ao salvar, o painel não manda desconto e o backend decide com `politica_de_desconto.decide`, a mesma função do bot e do site. "Sem desconto" vira "zero de propósito" (razão `none`) e, na edição, "Política da clínica" com áreas alteradas re-decide pelo sinal `discountPolicy: true`.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/politica_de_desconto.py` | `RAZAO_NENHUM = "none"`, `RAZOES_DA_POLITICA`, `razao_e_da_politica()` |
| `scheduler/src/services/appointment_service.py` | `create_appointment`: sem opinião → `decide`; **novo** `aplica_politica(appointment_id)` |
| `scheduler/src/functions/appointment/create.py` | aceita `discountReason: "none"` só com pct 0 |
| `scheduler/src/functions/appointment/update.py` | `discountPolicy: true` (exclusivo com pct/cents) → `aplica_politica` depois da etapa 1 |
| `scheduler/src/functions/appointment/quote.py` | **novo** `POST clinics/{clinicId}/quote` (`agenda.ler`) |
| `scheduler/sls/functions/appointment/interface.yml` | função `QuoteAppointment` |
| `scheduler/tests/unit/test_rotas_abertas_ao_staff.py` | `"appointment/quote.py": "agenda.ler"` |
| `scheduler/tests/unit/test_politica_no_painel.py` | **novo**: criação pela política, `none`, `aplica_politica`, cotação, contrato de razões |
| `scheduler/tests/unit/test_desconto_contrato.py` | razão `none` e `policy` nos dois lados |
| `scheduler/tests/integration/053-popup-da-agenda.md` | **novo** roteiro |
| `scheduler/tests/postman/053-cotacao.postman_requests.json` | **novo** |
| `frontend/src/components/ui/Confirmacao.tsx` (+test) | **novo** confirmação inline |
| `frontend/src/pages/agenda/components/EnviarLinkDePagamento.tsx` (+test) | confirma antes de `mandar()`; CPF depois |
| `frontend/src/pages/agenda/components/EnviarLinkDosDocumentos.tsx` (+test) | confirma antes de `mandar()` |
| `frontend/src/pages/agenda/components/PagamentoDoAgendamento.tsx` (+test) | confirma antes de `confirmarDinheiro()` |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` (+test) | "Pedir nova assinatura" usa `Confirmacao` |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` (+test, `FaltaDoPaciente.test.tsx`) | "Marcar falta" e "Marcar como confirmado" confirmam |
| `frontend/src/lib/desconto.ts` (+test) | modo `policy`; `POLITICA_DA_CLINICA`; `payloadDoDesconto`; `descontoDoAgendamento`; `textoDoDesconto`; `rotuloDaRazao` |
| `frontend/src/pages/agenda/components/DescontoField.tsx` (+test) | quarto modo, primeiro; bloco da cotação |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | padrão; cotação; aviso da estreia; payload |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` | `policy` gravado; re-decisão; resumo |
| `frontend/src/lib/alteracaoDeAgendamento.ts` (+test) | linha "Desconto" com texto da política |
| `frontend/src/services/appointments.service.ts`, `hooks/useAppointments.ts` | `cotar`, `useCotacao` |
| `frontend/src/types/index.ts` | `Cotacao`, `CotacaoPayload`, `UpdateAppointmentPayload.discountPolicy` |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx`, `pages/dashboard/components/TodayAppointments.tsx` | `DISCOUNT_LABELS` → `rotuloDaRazao` de `lib/desconto` (fonte única) |

---

## 3. Backend

### 3.1 `politica_de_desconto.py`

```python
RAZAO_NENHUM = "none"            # zero de propósito, escolhido no painel
RAZOES_DA_POLITICA = (RAZAO_PRIMEIRA_SESSAO, RAZAO_FAIXA_2, RAZAO_FAIXA_3)

def razao_e_da_politica(razao) -> bool:
    return razao in RAZOES_DA_POLITICA
```

Exportar em `__all__`. `decide` não muda: a estreia continua vindo de `e_primeira_visita` (decisão 7; conta só `CONFIRMED`, cancelado e falta não são visita).

### 3.2 `appointment_service.create_appointment`

Trocar o bloco "2a-bis":

```python
# Ninguém opinou: vale a política da clínica, a MESMA do bot e do site
# (PRD 053). Inclui o combinado da paciente, que vence tudo. O painel em
# "Sem desconto" manda razão "none" e cai fora deste if.
if discount_cents is None and not discount_pct and not discount_reason:
    decisao = decide(self.db, clinic_id, phone, len(service_area_pairs or []))
    if decisao.pct:
        discount_pct, discount_reason = decisao.pct, decisao.razao
```

- `qtd_areas` é a contagem dos pares depois dos combos no site; aqui os pares já chegam do painel sem combo. Usar `len(service_area_pairs or [])` (sem pares, 0: só personalizado e primeira sessão podem valer, e é o que `decide` faz).
- Import: `from src.services.politica_de_desconto import decide, razao_e_da_politica, RAZAO_NENHUM`. Remover o import de `desconto_do_paciente` se ficar sem uso.
- Bot e site passam `pct=0, razao=None` quando `decide` deu nada: entram neste `if` e `decide` roda de novo com o mesmo resultado (determinística para os mesmos dados). Uma consulta a mais, nenhuma mudança de comportamento. Anotar no comentário.
- Razão `none` é gravada como veio (`discount_reason = 'none'`, `pct = 0`).

### 3.3 `appointment_service.aplica_politica` (novo)

```python
def aplica_politica(self, appointment_id: str) -> Dict[str, Any]:
    """Re-decide o desconto pela política da clínica sobre o preço de tabela
    ATUAL (PRD 053, decisão 5). Chamado pela edição depois da troca de áreas.
    Zera discount_cents: a política é percentual."""
```

- Lê `clinic_id, patient phone, original_price_cents, version` e a contagem de áreas (`COUNT(*) FROM appointment_service_areas WHERE appointment_id`).
- `decisao = decide(db, clinic_id, phone, qtd_areas)`; `final = aplica_desconto(original, decisao.pct)`.
- `UPDATE ... SET discount_pct, discount_cents = NULL, discount_reason, final_price_cents, version = version + 1 WHERE id AND version` (optimistic lock, como os vizinhos). Razão gravada: `decisao.razao` (pode ser `None` quando a política não dá nada; `none` fica reservado à escolha explícita do painel).
- Devolve a linha atualizada.

### 3.4 `functions/appointment/create.py`

- Depois de ler `discountReason`: se `== "none"` e (`discountPct` > 0 ou `discountCents` veio) → 400 `"discountReason 'none' não combina com desconto"`.
- Nada mais: `none` com pct 0 chega ao serviço e cai fora do `if` da política.

### 3.5 `functions/appointment/update.py`

- Ler `aplicar_politica = body.get("discountPolicy") is True`.
- Exclusividade: `aplicar_politica` com `veio_pct` ou `veio_cents` → 400 `"Mande discountPolicy ou um desconto, não os dois"`.
- `discountReason == "none"` com pct > 0 ou cents → 400, como na criação.
- Nova etapa **1-bis**, logo após a etapa 1 (serviço/áreas) e antes da duração: `if aplicar_politica: service.aplica_politica(appointment_id); changed = True; messages.append("desconto pela política")`. Fica depois da etapa 1 porque o preço de tabela já é o das áreas novas, pela mesma razão que o bloco de pct/cents da etapa 4.
- Docstring: documentar `discountPolicy` e `discountReason: "none"`.

### 3.6 `functions/appointment/quote.py` (novo)

```
POST clinics/{clinicId}/quote          agenda.ler
Body: { "serviceIds": [...], "serviceAreaPairs": [{serviceId, areaId}], "phone": "55..." | null }
200: { "status": "SUCCESS", "quote": {
        "originalPriceCents", "discountPct", "discountReason", "finalPriceCents",
        "areaCount", "isFirst" } }
```

- `require_acesso(event, "agenda.ler")` (já confere a clínica do path).
- `pares = carrinho.pares_do_corpo(...)`, `service_ids = carrinho.valida_carrinho(...)`, `cotacao = carrinho.cota(db, clinic_id, service_ids, pares, phone)`.
- Diferenças da rota pública: **devolve a razão com telefone** (é a recepção olhando a própria paciente) e `isFirst = cotacao.desconto.is_first`; não devolve `cadastro` nem `combos`.
- `discountPct` como `float`; `discountReason` pode ser `null`.
- 400 em `CarrinhoInvalido`; 404 se a clínica não existe/inativa (como a pública).
- `interface.yml`: `QuoteAppointment`, `memorySize: 512`, `timeout: 30`, `http post clinics/{clinicId}/quote cors`.
- Log: `[Quote] {clinic_id} tel=...final... pares=N razao=... pct=...` (sem o telefone inteiro).

### 3.7 Testes backend

`test_politica_no_painel.py` (novo), com banco falso no estilo de `test_desconto_por_valor.py`:

- `create_appointment` sem opinião chama `decide` e grava pct/razão (patch em `appointment_service.decide`).
- `decide` sem desconto: grava 0 e razão `None`.
- `discountReason: "none"` com pct 0: `decide` **não** é chamada; grava `none`.
- `none` com pct > 0 → 400 em `create` e em `update`.
- `discountPolicy: true` em `update`: chama `aplica_politica` depois de `update_appointment_services` (ordem conferida pelas chamadas gravadas no dublê).
- `discountPolicy` + `discountPct` → 400.
- `aplica_politica`: zera `discount_cents`, grava a razão de `decide`, recalcula `final_price_cents`, respeita a versão.
- `quote.py`: 200 com razão e `isFirst`; 400 carrinho inválido; sem `require_api_key`.
- `razao_e_da_politica`: as três verdadeiras; `custom`, `partnership`, `none`, `None` falsas.

`test_desconto_contrato.py`: as razões conhecidas do backend (`first_session`, `tier_2`, `tier_3`, `partnership`, `custom`, `none`) batem com `rotuloDaRazao` do front (ler o `.ts` por regex, como o contrato atual faz com a conta).

`test_rotas_abertas_ao_staff.py`: linha nova.

---

## 4. Frontend

### 4.1 `components/ui/Confirmacao.tsx` (novo)

```tsx
interface ConfirmacaoProps {
  pergunta: string           // "Mandar o link de cobrança de R$ 195,00 para (11) 9…-1234 pelo WhatsApp?"
  detalhe?: string           // "A cobrança será criada no Asaas." / "Link enviado em 19/11 às 10:02"
  acao: string               // rótulo do botão que executa: "Enviar", "Registrar", "Marcar falta"
  tom?: 'neutro' | 'perigo'  // perigo = botão vermelho (falta)
  loading?: boolean
  onConfirmar: () => void
  onVoltar: () => void
}
```

- Bloco compacto (`rounded-lg border bg-gray-50 p-3 text-sm`), pergunta em `text-gray-800`, detalhe em `text-xs text-gray-500`, dois botões à direita: `Button size="sm"` da ação (`variant` `primary` ou `danger`, `loading`) e `Button size="sm" variant="secondary"` "Voltar".
- `role="group"` com `aria-label={pergunta}`; o botão da ação recebe `autoFocus` (decisão: o custo é um Enter). `Escape` chama `onVoltar`.
- Teste: renderiza pergunta/detalhe; clicar na ação chama `onConfirmar` uma vez; "Voltar" e Escape chamam `onVoltar`; `loading` desabilita os dois.

### 4.2 Padrão de uso nos componentes

Cada componente ganha `const [confirmando, setConfirmando] = useState(false)`. O botão original passa a `onClick={() => setConfirmando(true)}`. Quando `confirmando`, renderiza `<Confirmacao … onConfirmar={() => { setConfirmando(false); executa() }} onVoltar={() => setConfirmando(false)} />` **no lugar** do botão, mantendo o resto da linha (status, datas).

- **`EnviarLinkDePagamento`**: precisa do valor e do telefone para o texto. Props novas: `valorCents: number | null`, `telefone: string | null` (o Caixa já tem `amountCents`/telefone em `CaixaPending`; o popover tem `a.final_price_cents`/`a.phone`). Pergunta: `Mandar o link de cobrança${valor ? ` de ${formataReais(valor)}` : ''} para ${formatPhone(telefone)} pelo WhatsApp?`; detalhe: `linkPendente ? 'Reenvia o mesmo link; não cria cobrança nova.' : 'A cobrança é criada no Asaas.'`. O fluxo do CPF (`pedindoCpf`) só aparece depois de confirmar, quando o backend responde `CPF_REQUIRED`; o "Enviar" do formulário do CPF não pede nova confirmação (a pessoa já confirmou).
- **`EnviarLinkDosDocumentos`**: prop nova `telefone: string | null`. Pergunta: `Mandar o link do termo e da ficha para … pelo WhatsApp?`; detalhe: `enviadoEm ? `Último envio em ${dataDe} às ${horaDe}` : undefined`.
- **`PagamentoDoAgendamento`**: pergunta `Registrar ${formataReais(a.final_price_cents)} recebido em dinheiro?`; detalhe `O pagamento fica como pago aqui e no Asaas.`; `acao="Registrar"`. Passa `valorCents`/`telefone` ao `EnviarLinkDePagamento`.
- **`TermoDoAgendamento`**: substituir o bloco `confirmaRenovar ? (...) : (...)` por `Confirmacao` com pergunta `Pedir termo e ficha de novo no próximo check-in?`, `acao="Sim, pedir"`. Estado `confirmaRenovar` continua.
- **`AppointmentPopover`**: estado `confirmando: 'falta' | 'confirmar' | null`. Quando setado, a lista de ações é substituída por `Confirmacao`:
  - falta: `Marcar falta de ${displayName} às ${hora}?`, detalhe `Dá para desfazer depois em "Desmarcar falta".`, `acao="Marcar falta"`, `tom="perigo"`; confirmar → `onMarcarFalta(a); onClose()`.
  - confirmar: `Marcar ${displayName} como confirmada?`, detalhe `A presença aparece confirmada pela equipe.`, `acao="Confirmar"`; confirmar → `onConfirmar(a); onClose()`.
  - "Desfazer confirmação" e "Desmarcar falta" seguem diretos. Atualizar os comentários do arquivo que justificam a ausência de confirmação (PRD 027) com a reversão de 20/11/2026.
- **`CaixaPanel`**: passar `valorCents={p.amountCents}` e `telefone={p.phone}` (conferir os nomes em `CaixaPending`; se o telefone não vier, mandar `null` e a pergunta omite o número).

### 4.3 `lib/desconto.ts`

```ts
export type ModoDeDesconto = 'policy' | 'none' | 'partnership' | 'custom'
export const POLITICA_DA_CLINICA: DescontoEscolhido = { modo: 'policy', tipo: 'pct', texto: '' }
export const SEM_DESCONTO = { modo: 'none', ... }   // continua

export const RAZOES_DA_POLITICA = ['first_session', 'tier_2', 'tier_3'] as const
export function rotuloDaRazao(razao: string | null | undefined, qtdAreas?: number): string
// first_session → '1ª sessão'; tier_2 → '2-4 áreas'; tier_3 → '5+ áreas';
// partnership → 'Parceria'; custom → 'Personalizado'; none/null → 'Sem desconto'
```

- `payloadDoDesconto`: `none` → `{ discountPct: 0, discountReason: 'none' }` (criação deixa de omitir: manda isto). `policy` → `{ discountPolicy: true }` (só a edição usa; a criação **omite** o bloco quando `policy`).
- `descontoDoAgendamento`: `partnership` → partnership; `discount_cents` → custom/cents; razão em `RAZOES_DA_POLITICA` → `{ modo: 'policy' }`; `custom` ou pct > 0 → custom/pct; senão (`none`, `null` com 0) → `SEM_DESCONTO`.
- `textoDoDesconto(d, cotacao?)`: `policy` → `cotacao?.discountReason ? `política da clínica (${rotuloDaRazao(r)}: ${formataPct(pct)}%)` : 'política da clínica'`.
- `resumoDoDesconto(d, subtotal, cotacao?)`: `policy` → se `cotacao` com pct > 0, `{ rotulo: `${rotuloDaRazao}: ${pct}%`, descontoCents: original - final, totalCents: final }` usando os centavos **da cotação** (o backend é a fonte); sem cotação, `null`.
- `validaDesconto`: `policy` → `null`.
- Mover `DISCOUNT_LABELS` do popover e do "Hoje" para `rotuloDaRazao` (dois mapas iguais em dois arquivos hoje).

### 4.4 `DescontoField.tsx`

- `MODOS`: `[{policy,'Política da clínica'}, {none,'Sem desconto'}, {partnership,'Parceria (100%)'}, {custom,'Personalizado'}]`. Cor do `policy` selecionado: `bg-emerald-50 border-emerald-300 text-emerald-700`.
- Props novas: `cotacao?: Cotacao | null`, `cotando?: boolean`, `erroDaCotacao?: string | null`.
- Quando `modo === 'policy'`, bloco abaixo dos botões (`mt-2 text-xs`):
  - `cotando` → "Consultando a política…";
  - `cotacao` com pct > 0 → `${rotuloDaRazao(r)}: ${formataPct(pct)}% (-${formataReais(original - final)})`;
  - `cotacao` com pct 0 → "Sem desconto pela política para esta paciente e estas áreas.";
  - `erroDaCotacao` → texto em `text-amber-600`: "Não foi possível consultar a política. O desconto é aplicado ao salvar.";
  - sem áreas/paciente → "Escolha a paciente e as áreas para ver o desconto."
- Testes: ordem dos botões; `policy` padrão exibe o bloco; cada um dos cinco estados.

### 4.5 `services/appointments.service.ts`, `hooks/useAppointments.ts`, `types`

```ts
export interface CotacaoPayload { serviceIds: string[]; serviceAreaPairs?: {serviceId; areaId}[]; phone?: string | null }
export interface Cotacao { originalPriceCents: number | null; discountPct: number; discountReason: string | null; finalPriceCents: number | null; areaCount: number; isFirst: boolean }
cotar(clinicId, payload) → POST `/clinics/${clinicId}/quote` → r.data.quote
export function useCotacao(payload: CotacaoPayload | null)  // enabled: !!payload; queryKey ['cotacao', clinicId, payload]; staleTime 30s
```

`UpdateAppointmentPayload.discountPolicy?: boolean`. `CreateAppointmentPayload.discountReason` já aceita string.

### 4.6 `CreateAppointmentModal.tsx`

- Estado inicial: `useState<DescontoEscolhido>(POLITICA_DA_CLINICA)`.
- `handleSelectPatient`: mantém a pré-seleção `custom` quando `custom_discount_pct != null` (decisão 8). Trocar de paciente para uma sem combinado volta para `POLITICA_DA_CLINICA` **só se** o modo atual for `custom` vindo da pré-seleção (guardar `preSelecionadoPelaPaciente` em ref/estado para não derrubar um personalizado digitado à mão).
- Cotação: `const payloadDaCotacao = desconto.modo === 'policy' && serviceId && selectedAreaIds.length > 0 ? { serviceIds: [serviceId], serviceAreaPairs, phone: selectedPatient?.phone ?? newPhone || null } : null`; `const cotacao = useCotacao(payloadDaCotacao)`. Passar `cotacao.data`, `cotacao.isPending`, erro para o `DescontoField` e para `resumoDoDesconto`.
- Resumo de preço: com `policy` e cotação, a linha "Desconto (1ª sessão: 10%)" e o total vêm da cotação; sem cotação, só o subtotal.
- Aviso da estreia (abaixo do `PrimeiraVisitaField`, `text-xs text-amber-600`): se `cotacao.data` e `primeiraVisita !== cotacao.data.isFirst`: marcado e não é → "O sistema não considera esta a primeira sessão (já há sessão confirmada). A política não dá o desconto de estreia."; desmarcado e é → "Para o sistema esta é a primeira sessão: a política aplica o desconto de estreia." Só quando a clínica tem desconto de estreia? Não dá para saber pela cotação; mostrar sempre que discordarem (é informação, não erro).
- Payload: `policy` → omite o bloco; demais → `descontoParaCriacao(desconto)` (que agora cobre `none` também, mandando `discountReason: 'none'`). Remover o comentário "Na criação `none` é omitir".
- Teste do modal (se houver `CreateAppointmentModal.test.tsx`; senão criar o mínimo): abre em "Política da clínica"; paciente com combinado abre em Personalizado; "Sem desconto" manda `discountReason: 'none'`; `policy` não manda desconto.

### 4.7 `EditAppointmentModal.tsx`

- `descontoGravado = descontoDoAgendamento(appointment)` já devolve `policy` para razões da política.
- Cotação: quando `desconto.modo === 'policy'`, `useCotacao({ serviceIds: [serviceId], serviceAreaPairs, phone: a.phone })`, só para o resumo e para o `DescontoField`.
- `discountChanged`: `policy` → verdadeiro se o modo mudou **ou** (`areasChanged || serviceChanged`) (decisão 5). Demais modos: como hoje.
- `alteracao.desconto`: `de: textoDoDesconto(descontoGravado)` com a razão gravada (`rotuloDaRazao(a.discount_reason)` e `a.discount_pct`), `para: textoDoDesconto(desconto, cotacao.data)`.
- `executa`: `policy` com `discountChanged` → `payload.discountPolicy = true` (nunca `discountPct`). Outros modos: `Object.assign(payload, payloadDoDesconto(desconto))` como hoje; `none` passa a mandar `discountReason: 'none'` (hoje manda `null`), o que grava `none` e deixa claro que foi escolha.
- `alteracaoDeAgendamento.ts`: nada estrutural; `textoDoDesconto` re-exportado ganha o parâmetro opcional.

### 4.8 Leitores

- `AppointmentPopover` e `TodayAppointments`: trocar `DISCOUNT_LABELS[...]` por `rotuloDaRazao(a.discount_reason)`. Comportamento igual; fonte única.

### 4.9 Testes frontend

- `Confirmacao.test.tsx` (4.1).
- `EnviarLinkDePagamento.test.tsx`: todos os casos passam a clicar em "Enviar link…" **e depois** em "Enviar"; caso novo "primeiro clique não envia; Voltar não envia"; o caso do CPF confirma antes.
- `EnviarLinkDosDocumentos.test.tsx`, `PagamentoDoAgendamento.test.tsx` ("dinheiro: a recepção dá a baixa" ganha a confirmação; novo caso de Voltar).
- `TermoDoAgendamento.test.tsx`: o caso de "Pedir nova assinatura" já cobre (primeiro clique não chama; "Sim, pedir" chama); conferir o texto do botão.
- `FaltaDoPaciente.test.tsx`: "chama onMarcarFalta sem passar por modal" vira "pede confirmação inline e só então chama onMarcarFalta"; novo "Voltar não chama". `AppointmentPopover.test.tsx` "confirma presença…" idem.
- `desconto.test.ts`: `payloadDoDesconto` (`none` → razão `none`; `policy` → `discountPolicy`), `descontoDoAgendamento` com `tier_2` → `policy`, `rotuloDaRazao`, `resumoDoDesconto` com cotação, `textoDoDesconto` com cotação.
- `DescontoField.test.tsx`: 4.4.
- `alteracaoDeAgendamento.test.ts`: linha "Desconto" de `2-4 áreas: 15%` para `5+ áreas: 20%`.

---

## 5. Ordem

1. Backend: `politica_de_desconto` (constantes) → `appointment_service` (`create_appointment`, `aplica_politica`) → `create.py`/`update.py` → `quote.py` + `interface.yml` → testes (`test_politica_no_painel`, `test_rotas_abertas_ao_staff`, `test_desconto_contrato`). `pytest` verde.
2. Deploy **dev** do backend; roteiro §6 casos 1-6.
3. Frontend: `Confirmacao` → os cinco componentes + popover → `lib/desconto` → `DescontoField` → service/hook/types → Create → Edit → leitores → testes. `npm run build`, `lint`, `test` verdes.
4. PR único (backend + front). Merge sobe o painel pela Vercel; o backend de dev já está no ar.
5. Smoke do painel em dev (casos 7-9) e, com o André, prod: `serverless deploy --stage prod` **antes** do merge chegar à Vercel de prod ou logo após (o painel tolera 404 na cotação).

---

## 6. Roteiro (dev) - esqueleto

Pré-requisitos como no 052. `C`, `S`, áreas e um telefone de paciente de teste **sem** combinado (`T1`) e um **com** combinado (`T2`), clínica com `discount_rules` ativa (primeira sessão e faixa 2).

| # | Chamada | Esperado |
|---|---|---|
| 1 | `POST clinics/{C}/quote` com 1 área e `T1` sem sessão confirmada | `discountReason: "first_session"`, `isFirst: true`, `finalPriceCents` < original |
| 2 | idem com 3 áreas e `T1` com uma sessão `CONFIRMED` anterior | razão `tier_2`, `isFirst: false` |
| 3 | idem com `T2` | razão `custom`, pct do cadastro |
| 4 | `POST appointments` sem bloco de desconto, `T1`, 3 áreas | gravado `discount_reason = tier_2`, `final_price_cents` igual ao da cotação |
| 5 | `POST appointments` com `discountPct: 0, discountReason: "none"` | gravado `none`, pct 0, final = original |
| 6 | `PUT appointments/{A}` com `serviceAreaPairs` (5 áreas) + `discountPolicy: true` | razão `tier_3`, `discount_cents` null; `discountPolicy` + `discountPct` → 400 |
| 7 | Painel: "Novo agendamento" | abre em "Política da clínica"; cotação muda ao trocar áreas; paciente com combinado abre em Personalizado; "Sem desconto" grava `none` |
| 8 | Painel: pop-up | os seis botões mostram a confirmação; "Voltar" não chama nada; confirmar chama uma vez; desfazeres seguem diretos |
| 9 | Painel: Caixa | o link de cobrança pede confirmação |
| 10 | `GET appointments?date=` antes/depois dos casos 6-8 | áreas e preços coerentes; fixtures canceladas ao fim |
