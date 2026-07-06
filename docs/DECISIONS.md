# Focus — Phase 0 Decisions

Resolved open questions from ethics, privacy, and planning reviews.

**Last updated:** July 2026

---

## Decisions log

| Question | Decision | Rationale |
|---|---|---|
| Default HUD caveat for partial static analysis | Use frozen text in [`HUD.md`](HUD.md) Block 4; append detected blindspots | Honest without alarming on every PR |
| LLM label pass opt-in | **Yes — default off** (`FOCUS_LLM_ENABLED=false`) | Private code stays local until repo owner enables |
| Fixture repo license | MIT for `tests/fixtures/glass_box/`; committed to Focus repo | Clear redistribution for open-source path later |
| Stack: CLI framework | **Typer** | Locked in [`STACK.md`](STACK.md) |
| Stack: graph library | **NetworkX** | Locked in [`STACK.md`](STACK.md) |
| HUD schema source of truth | **`docs/HUD.md`** | `focus.mdc` references it; tests assert against it |
| Phase 0 exit | **Complete** — Phase 1 may start | All exit criteria met 2026-07-06 |

---

## Related documents

- [`ETHICS.md`](ETHICS.md)
- [`PRIVACY.md`](PRIVACY.md)
- [`ROADMAP.md`](ROADMAP.md)
