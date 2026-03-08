# TOKEN LOG — Traffic Manager

> Registro de consumo de tokens por task. Atualizado ao mover card para DONE.

---

## Formato

```
## CARD-XXX: [Título]
- **Data:** YYYY-MM-DD
- **Tokens início:** Xk (context ao iniciar a task)
- **Tokens fim:** Xk (context ao mover para QA)
- **Tokens consumidos (task):** ~Xk
- **Notas:** observações relevantes
```

---

## Histórico

*(nenhum ainda)*

---

## Monitoramento

| Contexto usado | Status | Ação |
|---|---|---|
| < 50% | 🟢 Verde | Normal |
| 50–70% | 🟡 Amarelo | Atenção, evitar tasks grandes |
| 70–85% | 🟠 Laranja | Compactar contexto antes de nova task |
| > 85% | 🔴 Vermelho | Parar, compactar ou nova sessão |

> Verificar com `session_status` antes de iniciar cada task.
