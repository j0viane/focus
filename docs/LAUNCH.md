# Launch kit — Product Hunt + Show HN

Use with gallery assets in [`assets/`](assets/) and the walkthrough in [`DEMO.md`](DEMO.md).

**Locked tagline:** Blast radius you can defend — evidence-only, before you merge.

**One-liner for “this already exists”:** Editor tools show hop lists while you type. Focus is pre-merge decision support — evidence-only topology, Danger Zones, one HUD from `audit --local` to the PR comment.

---

## Product Hunt

### Name
Focus

### Tagline (≤60 chars)
Blast radius you can defend — before you merge

### Description (short)
Focus maps how files in your repo connect (Python + JS/TS imports) and shows the blast radius of a change before you merge. Same Mermaid HUD in the CLI and as a GitHub PR comment. Evidence-only — no LLM inventing edges. Quiet when the change is boring; loud when you touch a shared hub.

### Topics
Open Source, Developer Tools, GitHub, Productivity, Artificial Intelligence (adjacent — for AI-assisted PRs)

### First comment (maker)

Hey Product Hunt 👋

I’m Joviane. I built **Focus** because AI ships code in seconds and understanding doesn’t.

When an assistant rewrites a shared util, juniors (and tired seniors) still have to answer: *what else breaks?* Existing tools either dump AI summaries on the PR or show hop inventories in the editor. I wanted something I could **defend in review**: a computed import graph, Danger Zones when you touch a hub, and the **same HUD** from `focus audit --local` to the PR comment — with no model inventing edges.

**Try it**

```bash
pip install focus-hud
focus audit --local --out focus-hud.md
```

Add the Action to any repo: copy [`examples/focus-action.yml`](https://github.com/j0viane/focus/blob/main/examples/focus-action.yml).

Repo: https://github.com/j0viane/focus  
Demo walkthrough: https://github.com/j0viane/focus/blob/main/docs/DEMO.md

Would love feedback from folks who review AI-sized PRs — what’s missing for you to trust a blast-radius tool?

### Links
- Website / repo: https://github.com/j0viane/focus
- Demo: https://github.com/j0viane/focus/blob/main/docs/DEMO.md

---

## Show HN

**Title:** Show HN: Focus – evidence-only blast radius before you merge

**Body:**

```
Focus answers one question before you merge: what else in this codebase
could break because of this change?

It builds an import graph (Python + JS/TS), then shows a Mermaid HUD with
Danger Zones — same artifact from `focus audit --local` and a GitHub Action
PR comment. No LLM inventing edges.

Not an editor hop-list product. Aimed at the AI-PR moment: skim vs dig
with evidence you can defend in review.

Install:
  pip install focus-hud
  focus audit --local --out focus-hud.md

Action (any repo):
  https://github.com/j0viane/focus/blob/main/examples/focus-action.yml

Repo: https://github.com/j0viane/focus
```

---

## Launch checklist

- [ ] Tag `v0.1.0` and push (triggers PyPI publish once Trusted Publishing is set — [`PUBLISH.md`](PUBLISH.md))
- [ ] Schedule PH (Tue–Thu often better) + Show HN same day or next morning
- [ ] Pin a GitHub Discussion / Issue for feedback
- [ ] Triage only launch-blocking bugs for 48h

Install: `pip install focus-hud` · Action: [`examples/focus-action.yml`](../examples/focus-action.yml).
