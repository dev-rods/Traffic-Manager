# Frontend — CLAUDE.md

Padrões obrigatórios para o frontend React do Scheduler (painel da clínica).

---

## Fluxo de Implementação (Plano → Meta-plano → Code)

Toda feature frontend segue o fluxo definido em [`WORKFLOW.md`](../WORKFLOW.md). Antes de codar:

### Plano
- Quais componentes criar / modificar
- Estrutura de arquivos (onde cada coisa vive)
- Hooks e queries necessários (TanStack Query keys, mutations)
- Dependências entre componentes (ordem de implementação)
- Decisões de UX: quais estados, quais interações

### Meta-plano (validação do plano)
- Como verificar que cada componente funciona? (testes, visual, integração)
- Critérios de aceite: o que o usuário vê em cada estado (loading, erro, vazio, sucesso)?
- Edge cases: dados faltando, listas longas, permissões, responsividade
- Como testar integração com API real? (quais endpoints, quais mocks)

> O agent **não começa a codar** sem o Rodrigo aprovar plano + meta-plano.

---

## Princípios de Implementação

Toda implementação frontend segue estes princípios sem exceção:

1. **Production-ready** — cada componente sai pronto pra prod, não "MVP depois melhora"
2. **Completeness** — estados de loading, erro, vazio e sucesso tratados em toda tela
3. **Extensible** — componentes composáveis que aceitam variação sem rewrite
4. **Type-safe end-to-end** — tipos do backend refletidos no frontend, zero `any`

---

## Stack & Versões

| Lib | Versão | Papel |
|-----|--------|-------|
| React | 19 | UI |
| TypeScript | 5.9+ (strict) | Tipagem |
| Vite | 7 | Build & dev server |
| TailwindCSS | v4 | Estilo utility-first |
| React Router | v7 | Roteamento |
| TanStack Query | v5 | Server state & cache |
| Axios | 1.x | HTTP com interceptors |
| React Hook Form + Zod | latest | Forms + validação |
| Vitest + Testing Library | latest | Testes |

---

## Estrutura de Diretórios

```
frontend/src/
├── components/          # Componentes reutilizáveis (UI primitivos, guards)
│   ├── ui/              # Primitivos: Button, Input, Modal, Badge, Card, etc.
│   └── PrivateRoute.tsx, PublicRoute.tsx
├── hooks/               # Custom hooks (useAuth, useDebounce, etc.)
├── layouts/             # AppLayout (sidebar), AuthLayout
├── pages/               # Telas organizadas por domínio
│   ├── auth/
│   ├── dashboard/
│   ├── agenda/
│   ├── pacientes/
│   └── relatorios/
├── services/            # Camada HTTP — um arquivo por recurso
├── store/               # Contextos React (AuthContext)
├── types/               # Tipos centralizados (index.ts)
└── utils/               # Funções puras (format, parse, helpers)
```

---

## Padrões de Código

### Componentes

```typescript
// Sempre: named export, Props tipadas, forwardRef quando aplicável
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

export function Button({ variant = 'primary', size = 'md', loading, children, ...props }: ButtonProps) {
  // ...
}
```

**Regras:**
- Named exports (nunca default export)
- Props com interface explícita, não inline
- Valores padrão via destructuring
- Composição sobre herança — usar `children` e slots, não flags booleanas pra variantes complexas
- Um componente por arquivo. Arquivo = nome do componente

### Data Fetching com TanStack Query

```typescript
// hooks/useAppointments.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { appointmentsService } from '@/services/appointments.service';

// Query keys centralizadas e tipadas
export const appointmentKeys = {
  all: ['appointments'] as const,
  lists: () => [...appointmentKeys.all, 'list'] as const,
  list: (filters: AppointmentFilters) => [...appointmentKeys.lists(), filters] as const,
  details: () => [...appointmentKeys.all, 'detail'] as const,
  detail: (id: string) => [...appointmentKeys.details(), id] as const,
};

export function useAppointments(filters: AppointmentFilters) {
  return useQuery({
    queryKey: appointmentKeys.list(filters),
    queryFn: () => appointmentsService.list(filters),
  });
}

export function useCancelAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: appointmentsService.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() });
    },
  });
}
```

**Regras:**
- Cada domínio tem seu hook file: `useAppointments.ts`, `usePatients.ts`, etc.
- Query keys factory pattern (nunca strings soltas)
- Mutations invalidam queries relacionadas
- Nunca chamar service direto do componente — sempre via hook

### Services (Camada HTTP)

```typescript
// services/patients.service.ts
import { api } from './api';
import type { Patient, CreatePatientPayload, PaginatedResponse } from '@/types';

export const patientsService = {
  list: (clinicId: string, params?: { search?: string; page?: number }) =>
    api.get<PaginatedResponse<Patient>>(`/clinics/${clinicId}/patients`, { params }).then(r => r.data),

  create: (clinicId: string, data: CreatePatientPayload) =>
    api.post<Patient>(`/clinics/${clinicId}/patients`, data).then(r => r.data),
};
```

**Regras:**
- Retorna `.data` (nunca AxiosResponse no componente)
- Tipagem explícita no generic do Axios
- Objeto literal exportado (não classe)
- clinic_id sempre como parâmetro (multi-tenant)

### Formulários

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  phone: z.string().regex(/^\+55\d{10,11}$/, 'WhatsApp inválido'),
});

type FormData = z.infer<typeof schema>;

export function PatientForm({ onSubmit }: { onSubmit: (data: FormData) => void }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });
  // ...
}
```

**Regras:**
- Schema Zod = source of truth para tipos do form
- `zodResolver` sempre
- Loading state via `isSubmitting`
- Erros inline por campo

### Estados Obrigatórios

Toda tela/componente que faz fetch deve tratar **4 estados**:

| Estado | O que renderizar |
|--------|-----------------|
| **Loading** | Skeleton/spinner contextual (não página inteira branca) |
| **Erro** | Mensagem + botão retry |
| **Vazio** | Ilustração + CTA (ex: "Nenhum paciente cadastrado. Cadastre o primeiro.") |
| **Sucesso** | Dados renderizados |

### Estilo (Tailwind)

- Utility classes direto no JSX (não `@apply` em CSS, exceto para base resets)
- Variantes via `clsx` ou `tailwind-merge` quando necessário
- Design tokens via CSS variables do Tailwind v4
- Responsivo: desktop-first, mas componentes não devem quebrar em tablet
- Cores semânticas: usar variáveis de tema, não hex hardcoded

### Testes

```bash
npm run test          # Vitest watch mode
npm run test:ci       # Single run (CI)
```

**O que testar:**
- Hooks custom: inputs → outputs, edge cases
- Componentes interativos: user events → resultado esperado
- Forms: validação, submit, estados de erro
- Services: mocking do Axios, payloads corretos

**O que NÃO testar:**
- Componentes puramente visuais sem lógica
- Re-testar comportamento já coberto pelo TanStack Query

---

## Convenções de Nomenclatura

| Item | Convenção | Exemplo |
|------|-----------|---------|
| Componentes | PascalCase | `AppointmentCard.tsx` |
| Hooks | camelCase com `use` prefix | `usePatients.ts` |
| Services | kebab-case com `.service` | `patients.service.ts` |
| Types | PascalCase | `Appointment`, `Patient` |
| Utils | camelCase | `formatCurrency.ts` |
| Constantes | SCREAMING_SNAKE | `API_BASE_URL` |
| CSS classes | Tailwind utilities | `className="flex items-center gap-2"` |

---

## Auth & API

- Token: `localStorage` key `tm_token`, clinic: `tm_clinic_id`
- Interceptor Axios: injeta `x-api-key` header em toda request
- 401 → logout automático + redirect `/login`
- Base URL: `VITE_API_BASE_URL` (env var)

---

## Comandos

```bash
cd frontend
npm run dev            # Dev server (localhost:5173)
npm run build          # Type check + build
npm run test           # Vitest watch
npm run lint           # ESLint (zero warnings)
npm run format:check   # Prettier check
```

---

## Design Principles (Impeccable)

Toda UI nova **deve** seguir os padrões do projeto [impeccable](../../impeccable/). Estas regras substituem defaults genéricos.

### Tipografia
- **Modular type scale** (não incrementos de 1px). Ratio 1.25–1.5 entre tamanhos
- Parear uma **fonte display distinta** com uma body limpa. Evitar Inter, Roboto, Open Sans
- Mínimo **16px** para body text; usar `rem/em`, nunca `px` para texto

### Espaçamento & Layout
- **Grid de 4pt** (4, 8, 12, 16, 24, 32, 48, 80px)
- Usar `gap` ao invés de margins para espaçamento entre siblings
- **Assimetria intencional > centralizar tudo.** Texto alinhado à esquerda, grids quebrados são mais fortes
- Cards são sobreusados — usar espaçamento e tipografia para agrupar. **Nunca aninhar cards dentro de cards**
- Max width: ~1400px para layouts, ~900px para colunas de conteúdo

### Cor & Contraste
- **Tint all neutrals** com hue sutil do brand (~0.01 chroma). Cinza puro parece morto
- Regra **60-30-10**: 60% neutro/white space, 30% secundário (texto, bordas), 10% accent
- **Nunca usar preto ou branco puros** (#000, #fff). Usar tons com chroma sutil
- Contraste mínimo **4.5:1** (AA) para body text; 3:1 para texto grande e UI components
- **Não depender só de cor** para transmitir informação

### Animação & Motion
- **100–150ms** para feedback instantâneo (botão, toggle)
- **200–300ms** para mudanças de estado (menu, hover)
- **300–500ms** para mudanças de layout (accordion, modal)
- Usar **easing exponencial** (`ease-out-quart/quint/expo`). **Evitar bounce/elastic**
- **Animar apenas transform e opacity.** Para height, usar `grid-template-rows: 0fr → 1fr`
- **Respeitar `prefers-reduced-motion`**

### Interação & Componentes
- **Botões rápidos** com optimistic UI para ações de baixo risco
- **Progressive disclosure**: opções simples primeiro, avançadas atrás de expandable sections
- **Hierarquia de botões**: ghost, text links, secondary. Nem tudo é primary
- **Empty states ensinam**, não só informam. Guiar o usuário para ação
- Touch targets mínimo **44px**

### Anti-patterns (NUNCA usar)
- Gradient text decorativo
- Dark mode com neon glowing como default
- Glassmorphism decorativo sem propósito
- Cards idênticos repetidos infinitamente (icon+heading+text)
- Modais desnecessários (usar inline quando possível)
- Rounded rectangles com borda colorida grossa de um lado só
- Sparklines decorativas que não comunicam nada
- Texto cinza em backgrounds coloridos (usar shade mais escura do background)

### Filosofia
- **Evitar "AI slop"**: se alguém vê e pensa "AI fez isso", é problema
- **Direção ousada e intencional > mediocridade segura**
- **Cada detalhe visual deve justificar sua presença**
- **Contraste > similaridade**: escolhas opostas (serif+sans, light+bold) criam clareza

---

## Checklist Pré-Commit (toda feature)

- [ ] Tipos corretos, zero `any`
- [ ] 4 estados tratados (loading, erro, vazio, sucesso)
- [ ] Testes para lógica e interações
- [ ] `npm run lint` passa sem warnings
- [ ] `npm run build` compila sem erros
- [ ] Componentes reutilizáveis extraídos quando padrão se repete 2+ vezes
- [ ] Design segue princípios Impeccable (ver seção acima)
