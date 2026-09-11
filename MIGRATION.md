# AGENTCRAFT — v1 → v2 migration note

> **TL;DR:** v2 is a **strict, backward-tolerant superset** of v1. A v1 report still
> validates and still renders — untouched. Nothing you already have breaks. v2 only
> *adds* rigor and surface. You do not have to migrate anything; you re-scan when you
> want the new depth.
>
> The contract is in [`SPEC.md`](./SPEC.md) — the backward-tolerance clause at the top,
> the v2 schema in §7, and the invariants in §7 "Schema invariants v2". This file is
> the plain-language version.

---

## The one guarantee that matters

**A v1 report is a valid v2 report.** Concretely, a v2-aware renderer MUST accept an
old report unchanged:

- If `agentcraft_version` is `"1"` (or absent), every pillar and sub-signal is read as v1.
- A v1 `sub_signals` value is a **bare number** (a micro-bar). A v2 `sub_signals` value
  is an **object** (with the partition, `verified_outcome`, `measurement_status`, etc.).
  The renderer accepts **both** — bare number renders as before; object renders the
  extra stats.
- The **OVERALL formula, tiers, weights, eligibility rule, meta-metrics, and the
  coaching contract are unchanged** from v1. v2 fields are all **additive + optional**.

So: your old `agentcraft-report.agentcraft.json` still passes `--summary-only` and still draws a
card. This is the migration bridge — it is a documented, tested invariant, not a hope.

---

## What v2 adds (and why you'd re-scan)

v2 absorbs the measurement rigor that made a chat-only scorer look more "auditable",
**without** giving up any AGENTCRAFT moat. New in v2:

1. **Episode + partition model.** Every sub-signal is now a falsifiable partition —
   `eligible = applied + declined + missed` (with `declined` counting *positive*), and
   the 0–100 number is **derived from the counts**, not a gut read. (SPEC §1c.)
2. **`verified_outcome` per behaviour.** "Of the times you did X, how many were
   independently confirmed?" — feeds a new **% VERIFIED** card stat. (SPEC §C.4 / §7.1.)
3. **`measurement_status` + `limitations`.** Honest-empty is now structural: `measured`
   (≥3 eligible) vs `unmeasured` with a machine-readable reason (`no-opportunity`,
   `below-threshold`, `extraction-gap`, …). No more fabricating a number from nothing.
   (SPEC §1d.)
4. **Capability-gating.** A behaviour the harness *couldn't record* is marked
   `unmeasured` + `extraction-gap` — **never scored low**. Fairness + honesty. (SPEC §2c.)
5. **Containment consistency.** Sub-signal counts can't exceed their pillar's; the
   renderer validates it fail-loud. (SPEC §2d.)
6. **~40 sub-signals covering all 24 MEGA traits** + the 2 moat axes. (See
   [`CROSSWALK.md`](./CROSSWALK.md).)
7. **Descriptive + synthesis blocks** — `profile`, `style`, `work_mix`,
   `collaboration_shape`, a per-week `trend` (which finally lets the card **show P6/P7
   compounding over weeks**), plus `practices[]` and `anti_patterns[]`. All descriptive,
   never folded into your grade. (SPEC §5b / §7.7.)

None of this changes what a **strong** score means — it makes the number more auditable
and the coaching more teachable.

---

## What has NOT changed (the moats — never regressed)

- **Zero third-party egress.** Your own Claude reads your work locally to coach you (a
  coach must); the extractor curates the slices it reads. No telemetry, no extra API key,
  no MEGA/AGENTCRAFT server — nothing is sent to any third party, and the report stays local.
- **Coaching.** Per-pillar `weak / why / how / example / retest` — same contract.
- **P6 Memory & Continuity + P7 System-Discipline** — the two MEGA-blind axes stay.
- **The fairness rule** — encoded discipline scores *up*, not down.
- **7-axis radar card**, HTML-always + PNG-graceful-fallback, `strengths[]` tolerating
  a string **or** an object, MIT license, your-own-agent-as-judge, git-ignored reports.

---

## How to migrate (you basically don't)

- **Keep your v1 report?** It renders as-is. Do nothing.
- **Want v2 depth?** Re-run the assessment (it now runs the extractor as a mandatory
  Step 1) and render again. Same command, richer card.

```bash
# your old v1 report still works, untouched:
python render/agentcraft_card.py --report agentcraft-report.agentcraft.json --summary-only   # exit 0

# to get v2 depth, re-scan in Claude Code, then render the fresh report:
python render/agentcraft_card.py --report agentcraft-report.agentcraft.json --out agentcraft-card-me.png
```

There is no data conversion, no schema rewrite, and no lock-in. v2 is *more rigorous +
broader*, still yours, still local.

---

*v1 → v2: a superset, not a replacement. Your old card still renders. Prove-don't-declare.*
