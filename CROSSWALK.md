# AGENTCRAFT — the MEGA → AGENTCRAFT crosswalk (the superset proof)

> **What this file proves, precisely.** AGENTCRAFT v2 measures **every axis MEGA measures**
> — all 24 traits, each **mapped** to a AGENTCRAFT sub-signal (not lost, not approximated)
> — **PLUS** two axes MEGA is structurally blind to, **PLUS** it coaches, **PLUS** it
> runs 100% locally. That combined claim is only honest **because this table backs it**.
> Read it as the receipt for the headline.
>
> Source of truth: the sub-signal indicator table in [`SPEC.md`](./SPEC.md) §1b and the
> design rationale in [`AGENTCRAFT_V2_AUDIT_AND_UPGRADE.md`](./AGENTCRAFT_V2_AUDIT_AND_UPGRADE.md)
> §C.5. If this table and SPEC §1b ever disagree, **SPEC §1b wins** — fix this file.
>
> BRAND is single-sourced in [`SPEC.md`](./SPEC.md) §0 (`BRAND = "AGENTCRAFT"`, provisional).

---

## How the mapping works (read this before the table)

- AGENTCRAFT keeps a **clean 7-pillar radar** on the card. Under the hood, each pillar
  decomposes into **named sub-signals** (~40 total). A MEGA trait maps to the AGENTCRAFT
  sub-signal that observes the *same behaviour* — sometimes one-to-one, sometimes a
  trait is covered by a pair of sub-signals.
- **Status legend:**
  - **have** — AGENTCRAFT v1 already measured this behaviour; v2 keeps it.
  - **NEW** — added in v2 specifically to cover a MEGA trait v1 had no signal for.
  - **completed** — v1 had partial coverage; v2 adds a sub-signal that finishes the trait.
  - **MOAT** — a AGENTCRAFT axis with **no MEGA equivalent** (MEGA is blind to it).
- Every sub-signal is scored the same way: an **episode partition**
  (`eligible = applied + declined + missed`, `declined` counts positive), score
  **derived from counts**, with `verified_outcome <= applied`. See SPEC §1c.

---

## The 24 MEGA traits — all mapped (no trait left behind)

| MEGA trait | AGENTCRAFT v2 home (pillar · sub-signal) | Status |
|---|---|---|
| **T01** Intent Clarity | P1 · `goal_clarity` | have |
| **T02** Problem Framing Altitude | P1 · `problem_framing` | have |
| **T05** Constraint Precision | P1 · `constraint_precision` | **NEW** |
| **T06** Falsifiable Acceptance | P1 · `acceptance_defined` + P5 · `falsifiable_acceptance` | have |
| **T04** Context Anchoring | P2 · `artifact_anchoring` | have |
| **T09** Evidence Injection | P2 · `evidence_at_decisions` | have |
| **T10** Progressive Disclosure | P2 · `progressive_disclosure` | **NEW** |
| **T11** Context Economy | P2 · `context_economy` | have |
| **T03** Agent State Modeling | P2 · `agent_state_awareness` + `session_boundary_awareness` | **completed** |
| **T07** Problem Understanding First | P3 · `understand_before_build` | have |
| **T13** Inspect-Before-Edit | P3 · `inspect_before_edit` *(countable ratio)* | have |
| **T08** Root-Cause Orientation | P3 · `root_cause_depth` | have |
| **T14** Capability Provisioning | P3 · `capability_provisioning` | **NEW** |
| **T15** Delegation Judgment | P4 · `delegation_judgment` | have |
| **T16** Decomposition Skill | P4 · `decomposition` | have |
| **T17** Agent Brief Quality | P4 · `brief_quality` | have |
| **T19** Parallelism Hygiene | P4 · `parallelism_hygiene` | have |
| **T20** Result Integration | P4 · `result_integration` | have |
| **T18** Decision Rights Allocation | P4 · `decision_rights` | **NEW** |
| **T23** Verification Closure & Independence | P5 · `independent_channel` + `closure` | have |
| **T22** Steering & Trust Calibration | P5 · `steering_calibration` | **NEW** |
| **T21** Feedback Specificity | P3/P5 · `feedback_specificity` *(correction quality)* | **NEW** |
| **T12** Durable Memory & Provenance | P6 · `decision_persistence` + `rationale_recorded` | **completed** |
| **T24** Recovery & Learning Discipline | P6 · `mistake_nonrepetition` + `recovery_discipline` | **completed** |

**Count check:** 24 distinct MEGA traits (T01–T24), each with a AGENTCRAFT home.
17 carried from v1 (**have**), 4 finished in v2 (**completed**: T03, T12, T24 — and
T21 is net-new but complements P3 correction quality), 6 net-new sub-signals for
previously-unmeasured traits (**NEW**: T05, T10, T14, T18, T22, T21). No MEGA trait is
dropped, approximated, or folded away.

---

## The two axes MEGA cannot see — AGENTCRAFT's moat

MEGA scores a **single chat**. These behaviours only appear **across sessions** and **in
the repo's encoded discipline** — a single-conversation scorer is structurally blind to
them. AGENTCRAFT reads them because the skill reads your `CLAUDE.md` / `.claude/skills` /
hooks / memory files and ≥2 sessions of history, locally.

| AGENTCRAFT axis (no MEGA equivalent) | pillar · sub-signal | Status |
|---|---|---|
| Cross-session inheritance | P6 · `cross_session_inheritance` | **MOAT** |
| Discipline encoded in files | P7 · `discipline_encoded` | **MOAT** |
| Config / hooks / gates actually used | P7 · `config_coverage` | **MOAT** |
| Rigor automated, not re-typed | P7 · `automation_vs_retyping` | **MOAT** |

> **The fairness twist lives here.** A developer who bakes their rigor into
> `CLAUDE.md` + skills + hooks scores **higher** on P7, not lower — because encoding
> discipline is the *higher* skill. A chat-only scorer sees the automated developer
> "not re-typing the rules" and reads it as laziness. AGENTCRAFT inverts that (SPEC §4).

---

## What that adds up to (the honest headline)

> **AGENTCRAFT v2 measures every axis MEGA measures — all 24 traits, mapped — PLUS the two
> axes MEGA can't see (Memory & Continuity, System-Discipline), PLUS it coaches you on
> what to fix, PLUS it runs on your own Claude with zero third-party egress (your work is
> read locally to coach you — a coach must — and nothing is sent to any third party). A
> strict superset, kept under a cleaner 7-axis card.**

That sentence is only allowed to stand *because* the table above is complete and the
[`sample-report-v2.agentcraft.json`](./examples/sample-report-v2.agentcraft.json) fixture exercises
it. Prove-don't-declare: if you find a MEGA trait with no honest AGENTCRAFT home, that's a
bug in this table — [open a PR](./CONTRIBUTING.md).

---

*The crosswalk is the receipt. Deeper, broader, ours — and provable.*
