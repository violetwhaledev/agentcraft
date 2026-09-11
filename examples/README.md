# examples/

**Synthetic fixtures only.** Everything committed here is hand-authored, synthetic
sample data — used for the docs (the README hero image), the renderer, and the tests.
**No real user data lives here.** Your actual report comes from running the
`agentcraft-assess` skill locally on *your* Claude Code history; those real scans are
git-ignored by default and never leave your machine.

> **A real card renders from *your own* scan.** These fixtures exist so the
> renderer, the docs, and the tests have something deterministic to point at.

## Contents

- **`sample-report.agentcraft.json`** — a canonical **synthetic** report matching the
  SPEC v1 schema ([`../SPEC.md`](../SPEC.md) §7). It exercises every schema invariant:
  P1–P7 all present, meta-metrics kept out of OVERALL, evidence on every graded
  pillar, one coaching entry per below-target pillar, sub-signals filled, and `brand`
  mirroring the SPEC. Scores OVERALL **72 (silver)** with **P7 = 85** as a strength
  (discipline encoded in `CLAUDE.md` + skills) — the fairness rule in action.
- **`sample-report-v2.agentcraft.json`** — a **synthetic** v2 report that exercises the
  partition / capability-gating / trend blocks. Source of the README hero card.
- **`breach-fixture.json`** — a **synthetic** report deliberately seeded so the tests can
  confirm the renderer's redaction guard scrubs any path/filename/secret from the
  shareable page.
- **`hero-card.png`** / **`.html`** — the **rendered** hero card for the synthetic v2 report
  above (a real offline render, not a mockup; it is the README hero).

## Try it

```bash
# Text summary of a synthetic fixture (validates the schema; exit 0 = OK):
python ../render/agentcraft_card.py --report ./sample-report-v2.agentcraft.json --summary-only

# Reproduce the hero card (offline; writes -share.html + -share.png):
python ../render/agentcraft_card.py --report ./sample-report-v2.agentcraft.json --out ./my-card.png --page share
```

## Privacy note

Real reports match the `.gitignore` patterns (`*.agentcraft.json`, `agentcraft-report*.json`,
`agentcraft-card*.png`, `*-share.*`, `*-depth.*`, …) and stay local. Only the synthetic
fixtures above are committed. **Never commit anyone's real scan.**
