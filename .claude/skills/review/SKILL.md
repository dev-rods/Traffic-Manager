---
name: review
description: Code review for Traffic Manager that validates pragmatic programming practices, DRY violations, unnecessary complexity, and stack-specific best practices (React 19, Python Lambda, TanStack Query). Use when reviewing changed files, before commits, or when the user asks to review code quality.
user-invocable: true
argument-hint: "[files, feature, or 'staged' for git staged changes]"
---

## MANDATORY PREPARATION

Before reviewing, gather context:
1. Read `CLAUDE.md` and `frontend/CLAUDE.md` for project conventions
2. If argument is "staged" or empty, run `git diff --cached --name-only` (or `git diff --name-only` if nothing staged) to identify changed files
3. Read all changed files fully — never review code you haven't read

---

## Review Checklist

Review each changed file against ALL of the following dimensions. Be specific — cite file:line for every finding.

### 1. DRY & Reuse (CRITICAL)

**This is the most important check.** Is new code duplicating something that already exists?

- **Serializers**: Does the project already have a `_serialize_row` helper? Is the new code creating another one?
- **HTTP helpers**: Are error responses using `http_response()` from `src/utils/http.py` or building manual responses?
- **Frontend services**: Is there already a service method for this API call? Check `frontend/src/services/`
- **Hooks**: Is there already a hook wrapping this query? Check `frontend/src/hooks/`
- **Types**: Is there already a type for this data shape? Check `frontend/src/types/index.ts`
- **Utility functions**: Check `frontend/src/utils/` for existing helpers (formatCurrency, formatPhone, formatDate, dateHelpers)
- **UI components**: Check `frontend/src/components/ui/` (Modal, Input, Badge, ErrorState, EmptyState, Skeleton)

**The test**: For every new function, type, or constant — search the codebase for an existing equivalent before approving.

### 2. Unnecessary Complexity

- Is a simple solution being over-engineered? (abstractions for one-time use, premature generalization)
- Are there new files that should be additions to existing files?
- Are there new utility functions that could be inline expressions?
- Is there indirection that doesn't pay for itself? (wrapper functions that just call another function)
- Are there feature flags or config for things that should just be code?

### 3. Frontend Best Practices (React 19 + TanStack Query v5)

- **Server state**: All API data goes through TanStack Query hooks — never `useState` + `useEffect` for fetching
- **Query keys**: Follow the factory pattern (`xxxKeys.all`, `xxxKeys.list(...)`, `xxxKeys.detail(...)`)
- **Mutations**: `useMutation` with `onSuccess` invalidating related queries
- **Derived state**: No `useEffect` to sync state — use derived values or the render-time pattern (`if (x !== prevX)`)
- **Component size**: Components over 200 lines should likely be split
- **Type safety**: Zero `any`, zero `as` casts except for narrowing error types
- **Named exports only**: No `export default`
- **4 states**: Every data-fetching view handles loading, error, empty, success
- **Forms**: React Hook Form + Zod for validation, not manual state
- **Impeccable design**: New UI follows the Design Principles section in `frontend/CLAUDE.md`

### 4. Backend Best Practices (Python Lambda + PostgreSQL)

- **Handler structure**: Thin handler → service layer → DB. Business logic never in handlers
- **SQL injection**: All queries use parameterized `%s` placeholders, never f-strings with user input
- **Error handling**: Specific exceptions (`ConflictError`, `NotFoundError`) not generic `Exception`
- **DB connections**: Using `PostgresService` singleton, not raw `psycopg2.connect()`
- **Response format**: All responses via `http_response()` with consistent `{"status": "...", ...}` shape
- **Auth**: Every handler starts with `require_api_key(event)`
- **Logging**: Structured logging with clinic_id context, no sensitive data in logs
- **Idempotency**: Upserts use `ON CONFLICT` where applicable

### 5. Pragmatic Programmer Principles

- **Don't Repeat Yourself**: Covered in #1
- **Orthogonality**: Does the change have minimal blast radius? Does changing one thing require changing others?
- **Reversibility**: Are decisions easy to reverse? No hard-coded magic values
- **Tracer bullets**: Does the implementation work end-to-end even if incomplete, rather than building layers without connecting them?
- **Broken windows**: Does the change leave surrounding code in a worse state? (commented-out code, TODO without context, inconsistent naming)

---

## Output Format

Structure the review as:

### Summary
One paragraph: what was changed, overall quality assessment, and the single most important finding.

### Findings

For each issue found, report:

- **[SEV] file:line — Title**
  - What: describe the problem
  - Why: why it matters (duplication, complexity, bug risk, convention violation)
  - Fix: concrete suggestion

Severity levels:
- **[BLOCK]** — Must fix before merge (bugs, security, DRY violations with existing code)
- **[WARN]** — Should fix, but not a blocker (complexity, minor convention drift)
- **[NOTE]** — Suggestion for improvement (style, naming, optimization)

### What's Good
Highlight 1-3 things done well. Acknowledge good patterns.

### Verdict
**APPROVE**, **APPROVE WITH NOTES**, or **REQUEST CHANGES** — with a one-line reason.

---

## Rules

- Be direct and specific — "line 42 duplicates the serializer at appointment_service.py:15" not "consider reducing duplication"
- Always search the codebase before flagging a missing abstraction — maybe it already exists
- Don't flag style issues that are consistent with the rest of the codebase
- Don't suggest adding comments to self-explanatory code
- Don't suggest adding error handling for impossible states
- Don't suggest abstractions for one-off code
- Focus on what matters: duplication, bugs, security, and maintainability
