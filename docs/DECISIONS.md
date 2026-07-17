# Focus — Phase 0 Decisions

Resolved open questions from ethics, privacy, and planning reviews.

**Last updated:** July 2026

---

## Decisions log

| Question | Decision | Rationale |
|---|---|---|
| Default HUD caveat for partial static analysis | Use frozen text in [`HUD.md`](HUD.md) Block 4; append detected blindspots | Honest without alarming on every PR |
| LLM caption labeler (evidence pack) | **Shipped opt-in (Phase 4c / 0.3.5)** | Labels **all** ℹ️ when enabled (incl. blank-line); never invents topology; fail-closed validate. See [`PRIVACY.md`](PRIVACY.md) |
| LLM pack payload vs engineering rule 11 | **Capped edit lines + measured slots** (never full files / never full graph) | Aligns product with PRIVACY; topology stays deterministic |
| Grounded caption validate before enable | **Fail-closed `validate_label`** | Reject hops, wrong risk, ungrounded identifiers/scope claims; keep deterministic on reject |
| No-key caption dogfood provider | **Ollama** (OpenAI-compatible localhost; default `qwen2.5:7b`) | Free local try without paid OpenAI/Anthropic key; pack stays on-machine |
| Fixture repo license | MIT for `tests/fixtures/` (same as Focus) | Clear redistribution for open-source / portfolio adoption |
| Project license | **MIT** (briefly tried GPL-3.0 for copyleft, reverted for adoption) | Credit via copyright notice; maximize try/fork friction-free use |
| Stack: CLI framework | **Typer** | Locked in [`STACK.md`](STACK.md) |
| Stack: graph library | **NetworkX** | Locked in [`STACK.md`](STACK.md) |
| HUD schema source of truth | **`docs/HUD.md`** | `focus.mdc` references it; tests assert against it |
| Phase 0 exit | **Complete** — Phase 1 may start | All exit criteria met 2026-07-06 |

---

## Related documents

- [`ETHICS.md`](ETHICS.md)
- [`PRIVACY.md`](PRIVACY.md)
- [`ROADMAP.md`](ROADMAP.md)
