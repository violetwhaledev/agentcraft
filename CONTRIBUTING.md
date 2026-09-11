# Contributing to AGENTCRAFT

Thanks for being here. AGENTCRAFT is **v2, open, and improving in public** — contributions
are genuinely welcome, whether you write code, sharpen the rubric, or just fix a typo.
v2 is a **backward-tolerant superset** of v1 (episode + partition scoring, capability
gating, ~40 sub-signals covering all 24 MEGA traits + 2 moat axes); old reports still
render (see [MIGRATION.md](./MIGRATION.md)) — don't break that bridge.

## The one rule that matters most

**Never break the privacy invariant.** AGENTCRAFT is 100% local. No contribution may add
telemetry, an HTTP POST of user data, an external API call for user data, or any
"send" step. The renderer must stay offline (no `requests` / `urllib` / sockets). If a
feature seems to *need* the network to score a user, it doesn't belong in AGENTCRAFT.

## Good first contributions

- ✍️ **A coaching example** — a sharper `how` / `example` / `retest_tip` for a pillar.
- 🎨 **Card-layout ideas** — mockups or code for the FIFA-style card / radar / panel.
- ⚖️ **A fairness edge-case** — a scenario the rubric scores unfairly, with the fix.
- 📚 **Docs** — clearer wording in README / SPEC / RUBRIC, or a typo fix.
- 🧪 **A synthetic fixture** — a hand-authored `*.agentcraft.json` for `examples/` (never real data).

## Ground rules

- **prove-don't-declare.** Show your work. For code, verify it and say how:
  - Python: `python -c "import py_compile; py_compile.compile('render/agentcraft_card.py', doraise=True)"`
  - JS: `node --check yourfile.js`
  - Or a smoke run (`--summary-only`) and paste the output.
  Report `file:line` evidence, not adjectives.
- **Respect the contract.** [`SPEC.md`](./SPEC.md) (the report schema, pillars, formula)
  and [`RUBRIC.md`](./RUBRIC.md) are the source of truth; [`CROSSWALK.md`](./CROSSWALK.md)
  is the 24-trait superset proof. Changing the contract needs a clear rationale in the
  PR — the skill and the renderer both depend on it. **Keep v2 backward-tolerant:** a v1
  report (bare-number sub-signals, no partition) MUST still validate and render.
- **Adding a sub-signal (v2 workflow).** A new sub-signal touches four places, in order:
  (1) an observable-cue row in [`SPEC.md`](./SPEC.md) §1b (with its `Capability` + `Trait`);
  (2) a band-anchor block + partition-counting rule in
  [`SKILL.md`](./skill/agentcraft-assess/SKILL.md) §4; (3) a one-liner under its pillar in
  [`RUBRIC.md`](./RUBRIC.md); (4) if it maps a MEGA trait, a row in
  [`CROSSWALK.md`](./CROSSWALK.md). The 7-pillar radar stays fixed — grow sub-signals, not axes.
- **The brand is provisional.** `AGENTCRAFT` collides with `agentcraft.com` / `agentcraft.io`, so it's
  single-sourced in **one** place ([`SPEC.md`](./SPEC.md) §0) with a grep-sweep rename recipe
  and three candidate names (AGENTCRAFT / PAIRSCORE / FORGEIQ). Keep it single-sourced — if you
  add a surface that needs the name, reference §0; **don't scatter a new literal.**
- **Credit MEGA.dev, don't trash it.** AGENTCRAFT exists *because* MEGA opened the category. We
  win by being deeper + open + private, not by dissing anyone.
- **Be kind and specific.** Assume good faith. Small, focused PRs merge faster.

## Workflow

1. Fork, branch, make your change.
2. Verify it locally (see prove-don't-declare above).
3. Open a PR describing **what** changed and **how you verified it**.
4. Never commit a real scan — `*.agentcraft.json` and friends are git-ignored for a reason.

## License

By contributing, you agree your contributions are licensed under the [MIT License](./LICENSE).

---

Questions or an idea you're not sure about? Open an issue and let's talk. 🌱
