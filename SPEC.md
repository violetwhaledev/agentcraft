# AGENTCRAFT — Canonical Product Specification (v2)

> **Version:** v2 (schema `agentcraft_version: "2"`) — a **strict, backward-tolerant
> superset** of v1. Everything a v1 report expressed still validates and still
> renders; v2 ADDS the measurement rigor (episode + partition model, capability
> gating, `verified_outcome`, containment, `measurement_status`), a wider
> behavioural surface (~40 sub-signals covering all 24 MEGA traits PLUS the two
> MEGA-blind moat axes), and descriptive/synthesis blocks — without surrendering
> any moat (100% local · coaching · P6/P7 · fairness · MIT · own-agent-judge).
> Design provenance: `AGENTCRAFT_V2_AUDIT_AND_UPGRADE.md` (Part C, G1–G10, crosswalk C.5).
>
> **v1 → v2 backward-tolerance clause (load-bearing).** A v2-aware consumer MUST
> accept a v1 report unchanged: (a) if `agentcraft_version != "2"`, treat every pillar
> and sub-signal as v1 (a bare numeric `sub_signals` value is a v1 micro-bar; a
> v2 sub-signal is an OBJECT — see §7.2); (b) the OVERALL formula, tiers, weights,
> eligibility, meta-metrics semantics, and the coaching contract are **unchanged**
> from v1. v2 fields are all **additive + optional**: a v1 report is a valid v2
> report with the new fields absent. This is the migration bridge — never break it.

> ## §0 · BRAND (single source of truth)
>
> This block is the **one** authoritative place the brand string is defined. Everything
> downstream (README title, renderer default, report `brand` field, skill folder name)
> is a **mirror** of this value — so a rename is one canonical edit + a scripted sweep,
> **not** a rewrite. `AGENTCRAFT` is **provisional**: `agentcraft.com` / `agentcraft.io` are taken by
> unrelated projects, so a rename is expected.
>
> ```
> BRAND             = "AGENTCRAFT"
> BRAND_STATUS      = "provisional (collision with agentcraft.com / agentcraft.io)"
> TAGLINE           = "Not a verdict — a coach."
> RENAME_CANDIDATES = ["AGENTCRAFT", "PAIRSCORE", "FORGEIQ"]   # weighed, not yet applied
> ```
>
> **Rename recipe (honest — it's a grep-sweep, not literally one line):**
> ```bash
> # 1. change BRAND above.
> # 2. find every literal (there are ~6 mirror sites):
> grep -ri "agentcraft" .
> #    → this SPEC, README title, skill/agentcraft-assess/ (folder), render/agentcraft_card.py defaults,
> #      .gitignore report globs (*.agentcraft.json / agentcraft-report* / agentcraft-card*), example filenames.
> # 3. replace the string, rename the skill folder + example files, done.
> ```
> Contributors: keep it single-sourced — do **not** scatter new literals. If you add a
> surface that needs the name, reference §0, don't hard-code a 7th copy.

---

## 0. One-paragraph model

AGENTCRAFT scores how well a developer collaborates with AI coding agents, computed
**entirely locally** from that developer's own Claude Code session history **plus
the discipline encoded in their repo** (CLAUDE.md, `.claude/skills`, hooks, gates,
scripts). It is a **strict superset of MEGA.dev**: it measures **all 24 MEGA
traits** (mapped under 7 clean pillars via ~40 sub-signals, §1b + §7.6) with the
same rigor — an **episode + partition** basis where every sub-signal's score is
*derived from counts* (`eligible = applied + declined + missed`, declined counting
positive, `verified_outcome <= applied`) rather than a gut number (§7.3) — **PLUS**
the two axes MEGA is structurally blind to (Memory & Continuity, System-Discipline)
— and it **coaches** rather than only judging. It ships as (1) a Claude Code Skill
(the assessment+coaching runbook), (2) an offline Python renderer (FIFA-style card
+ radar + growth-plan panel), and (3) a world-class README. The "judge" is the
user's **own** agent following the runbook locally — a coach must read the work, so
it does; the extractor **curates** what it reads (representative, redacted excerpts)
so it deep-reads the relevant slices, not a raw dump. No *external* API, no extra API
key, no telemetry, and **zero third-party egress** — the report stays on the user's disk
(§6 spells out the honest data-flow, including an optional counts-only lite mode).

We credit MEGA.dev as the inspiration that opened this category. We differentiate
by being **deeper + open (MIT) + coaching + zero-third-party-egress** (your own
Claude reads curated local slices — see §6).

---

## 1. The 7 pillars (each 0–100)

Each pillar is scored 0–100 by the user's own agent, reading local history and repo
discipline. Every pillar has an **eligible-when** condition (when there is enough
signal to score it) and a **scoring method** (how to map evidence → 0–100). If a
pillar is not eligible, it is reported as `eligible: false` with `score: null` and
is **excluded** from the OVERALL weighted mean (weights renormalize over eligible
pillars). This prevents punishing a user for signals a thin window cannot contain.

Scoring is **evidence-anchored** (prove-don't-declare): every pillar score must
carry `evidence` — concrete pointers (session id / turn index / file path) that
justify the number. No evidence ⇒ do not inflate the score.

### P1 — INTENT & FRAMING
- **Measures:** goal clarity, problem-level (not solution-dictated) framing,
  presence of checkable **"done when X"** acceptance criteria.
- **Eligible-when:** at least one task-initiating turn exists in the window.
- **Sub-signals (0–100 each, then averaged into the pillar):**
  - `goal_clarity` — is the desired outcome stated unambiguously?
  - `problem_framing` — framed at the problem level vs a premature fixed solution?
  - `acceptance_defined` — is there a falsifiable "done when ___" per task?
- **Scoring method:** proportion of task-initiations that are clearly framed AND
  carry acceptance criteria, weighted toward the harder signal (acceptance).
  Credit **declining/re-scoping a bad task** as positive framing.

### P2 — CONTEXT & GROUNDING
- **Measures:** anchoring to real artifacts (files/logs/errors/tests), supplying
  evidence at decision points, **context economy/efficiency** (low re-paste of the
  same material), and agent-state awareness (knowing what the agent already holds).
- **Eligible-when:** ≥1 decision point or ≥3 substantive turns exist.
- **Sub-signals:**
  - `artifact_anchoring` — decisions grounded in real files/paths/outputs.
  - `evidence_at_decisions` — evidence present exactly where a choice is made.
  - `context_economy` — inverse of redundant re-paste / context bloat.
  - `agent_state_awareness` — user avoids re-sending what the agent already has.
- **Scoring method:** fraction of decision points with fresh artifact evidence,
  penalized by measured re-paste ratio (duplicate blocks / total context).

### P3 — EXECUTION & DIAGNOSIS
- **Measures:** understand-before-build, root-cause over symptom, inspect-before-edit.
- **Eligible-when:** ≥1 build/fix/debug episode exists.
- **Sub-signals:**
  - `understand_before_build` — reading/inspection precedes mutation.
  - `root_cause_depth` — fixes address cause, not just visible symptom.
  - `inspect_before_edit` — files/state examined before being changed.
- **Scoring method:** per debug/build episode, score the inspect→diagnose→fix
  ordering; average across episodes. Reward reproduction + root-cause statements.

### P4 — ORCHESTRATION
- **Measures:** delegation judgment (when to spawn/subagent vs do inline),
  decomposition, brief quality, parallelism hygiene, result integration.
- **Eligible-when:** ≥1 delegation/subagent/multi-step decomposition OR an explicit
  in-scope decision NOT to delegate.
- **Sub-signals:**
  - `delegation_judgment` — right call on delegate vs inline (both directions credited).
  - `decomposition` — task broken into coherent, sized units.
  - `brief_quality` — briefs carry goal + context + acceptance (mirror of P1/P2).
  - `parallelism_hygiene` — parallel work is independent / non-colliding.
  - `result_integration` — sub-results verified and merged, not blindly accepted.
- **Scoring method:** average of sub-signals over orchestration episodes; if no
  delegation occurred but the task genuinely didn't need it, score on
  `delegation_judgment` alone (a correct "don't delegate" = full credit).

### P5 — VERIFICATION
- **Measures:** independent verification (a **different channel** than the one that
  produced the claim), verification closure, falsifiable acceptance.
- **Eligible-when:** ≥1 claim of completion/correctness exists.
- **Sub-signals:**
  - `independent_channel` — verified via a channel distinct from the producer
    (e.g. run/test/inspect the artifact, not just "the agent said it works").
  - `closure` — verification actually completed (not left as an intention).
  - `falsifiable_acceptance` — the accept test could have failed and would show it.
- **Scoring method:** fraction of completion claims that received independent,
  closed, falsifiable verification. Unverified "trust me" claims drag the score.

### P6 — MEMORY & CONTINUITY  **[MEGA-BLIND — our moat]**
- **Measures:** persisting decisions, cross-session inheritance, and
  learning-from-mistakes so the same mistake does not repeat.
- **Eligible-when:** the window spans ≥2 sessions/episodes OR a memory artifact
  exists (handoff file, memory store, ADR, decisions log, `MEMORY.md`, etc.).
- **Sub-signals:**
  - `decision_persistence` — decisions written down somewhere durable.
  - `cross_session_inheritance` — later sessions demonstrably use earlier knowledge.
  - `mistake_nonrepetition` — a past mistake is recorded and not repeated.
- **Scoring method:** evidence of durable memory + at least one demonstrated
  inheritance/non-repetition; scale by how systematically it happens.
- **Note:** This is a primary reason AGENTCRAFT beats MEGA — MEGA scores single-session
  chat and cannot see continuity across a developer's actual workflow.

### P7 — SYSTEM-DISCIPLINE  **[MEGA-BLIND — our moat]**
- **Measures:** is discipline **encoded in the repo** (CLAUDE.md / `.claude/skills`
  / hooks / gates / scripts) versus re-typed into every prompt? The skill **MUST
  read config + skills + hooks**, not only chat.
- **Eligible-when:** always eligible (a repo with *no* discipline config is a valid,
  informative signal — it scores low, and that's the honest read).
- **Sub-signals:**
  - `discipline_encoded` — standing conventions live in files, not in the user's memory.
  - `config_coverage` — CLAUDE.md / skills / hooks / gates actually exist & are used.
  - `automation_vs_retyping` — repeated instructions are automated, not re-pasted.
- **Scoring method:** inventory the repo discipline surface; score by breadth +
  depth of encoded discipline and evidence the agent honored it.
- **Fairness anchor:** this pillar (with the fairness rule, §4) directly **fixes the
  core unfairness in MEGA**, which penalizes people who bake discipline into the
  system instead of re-typing it each prompt.

---

## 1b. Sub-signal indicator table (the DEPTH contract — observable cues per sub-signal)

Sub-signals are **not** vibes. Each one is scored as a **partition** (§7.3):
`eligible = applied + declined + missed`, `verified_outcome <= applied`, and the
0–100 number is **derived from the counts** blended with band anchors —
`0–39 weak · 40–64 developing · 65–84 strong · 85–100 elite`. Score each sub-signal,
average sub-signals into the pillar. This is the granularity that beats a flat
7-number quiz — MEGA-like depth (all 24 traits) organized under our 7 clean pillars.
The full band-anchor prose + per-sub-signal partition-counting rules live in
`skill/agentcraft-assess/SKILL.md` §4 (the runbook); this table is the canonical index
of *what is observed*.

**Columns:** `Cue` = what to count in the JSONL/repo. `Capability` = which Claude
Code history capability (§2c) the sub-signal depends on — if that capability is
**gated out** for the window, the sub-signal is `unmeasured` + `extraction-gap`,
**never a low score** (fairness, §2c). `Trait` = the MEGA trait it maps to per the
crosswalk (C.5); `MOAT` = MEGA-blind axis, no trait equivalent.

| Pillar | Sub-signal | Observable cue (count it in the JSONL / repo) | Capability | Trait |
|---|---|---|---|---|
| **P1** | `goal_clarity` | task-initiating `user` turn names a concrete outcome/artifact + bounded scope (not "make it better") | message | T01 |
| P1 | `problem_framing` | states symptom/need & lets agent pick approach; an `AskUserQuestion`/"X or Y?" clarify = strong | message | T02 |
| P1 | `acceptance_defined` | a checkable "done when ___" in the prompt (tests green / verify `tsc` / returns 200) | message | T06 |
| P1 | `constraint_precision` **➕NEW** | prompt names the real constraints/non-goals (perf budget, "don't touch X", stack, deadline) precisely, not vaguely | message | T05 |
| **P2** | `artifact_anchoring` | prompts cite `path:line`, a pasted error/stacktrace, a test name — not "the code" | message, retrieval | T04 |
| P2 | `evidence_at_decisions` | the deciding turn carries the data (a referenced `tool_result`, a measured number) | message, retrieval | T09 |
| P2 | `progressive_disclosure` **➕NEW** | context is fed **when needed** (staged), not one giant dump up front; the agent is given the next artifact at the decision point | message | T10 |
| P2 | `context_economy` | low re-paste ratio; healthy `usage.cache_read` vs `cache_creation` (context reused, not rebuilt) | message, configuration | T11 |
| P2 | `agent_state_awareness` | references "the file you just read"/"as established"; builds on prior `tool_result` | message | T03 |
| P2 | `session_boundary_awareness` **➕NEW** | user tracks what survives a compaction / new session (re-primes only what was lost, doesn't re-dump everything) | message, compaction | T03 |
| **P3** | `understand_before_build` | per episode a `Read`/`Grep`/`Glob` (or repro) precedes the first `Edit`/`Write` | retrieval, mutation | T07 |
| P3 | `root_cause_depth` | explicit "Root cause:" statement; bug reproduced; fix targets cause not stack-trace line | retrieval, mutation | T08 |
| P3 | `inspect_before_edit` | **countable ratio:** `Edit`/`Write` preceded by a `Read`/`Grep` on the **same path** (§2b extractor) | retrieval, mutation | T13 |
| P3 | `capability_provisioning` **➕NEW** | before delegating/asking, user equips the agent (grants tools/MCP, points at the right skill, sets scope) rather than expecting blind success | configuration, delegation | T14 |
| P3 | `feedback_specificity` **➕NEW** | corrections are specific + actionable ("wrong: it drops nulls; do X") not vague ("nope, try again"); ties to correction quality | message | T21 |
| **P4** | `delegation_judgment` | big/parallel work → `Task`/`Agent`; trivia inline; a correct "do it inline" = full credit | delegation | T15 |
| P4 | `decomposition` | work split into waves/sized units (`TaskCreate`); each independently completable | delegation, message | T16 |
| P4 | `brief_quality` | the `Task`/`Agent` `prompt` states goal + context + "done when"; encoded brief templates count | delegation | T17 |
| P4 | `parallelism_hygiene` | parallel spawns touch disjoint files; a separate verifier (audytor ≠ budowniczy) | delegation | T19 |
| P4 | `result_integration` | after an agent returns, the main thread inspects/verifies before accepting | delegation, verification | T20 |
| P4 | `decision_rights` **➕NEW** | user allocates authority correctly: agent decides reversible/local calls autonomously; user reserves the irreversible ones (deploy/spend/delete) | delegation, message | T18 |
| **P5** | `independent_channel` | after `Edit`/`Write`, a `Bash` test/compile/lint/`curl` or a re-`Read` — **not** "agent said so" | verification | T23 |
| P5 | `closure` | the verify run has a captured result (exit 0 / "26/26 PASS" / 0 errors) in a `tool_result` | verification | T23 |
| P5 | `falsifiable_acceptance` | the check is a real pass/fail (test suite / type-check / HTTP status), not a tautology | verification | T06 |
| P5 | `steering_calibration` **➕NEW** | trust is calibrated to evidence: user tightens the loop after a miss, loosens it after verified wins — not blind-trust nor micromanage | message, verification | T22 |
| **P6** | `decision_persistence` | count durable artifacts: handoff files, ADRs, `MEMORY.md`, a memory-store/`*_remember*` script | configuration | T12 |
| P6 | `cross_session_inheritance` **🛡️MOAT** | a later turn references an earlier decision; a session-start recall/summary read at boot | configuration, compaction | MOAT |
| P6 | `mistake_nonrepetition` | a BUG_FIX/LESSON exists AND the same error does not recur later (recurrence = negative) | message, mutation | T24 |
| P6 | `rationale_recorded` **➕NEW** | persisted decisions carry the *why* + provenance (which session/file), not just the *what* — an ADR-shaped record | configuration | T12 |
| P6 | `recovery_discipline` **➕NEW** | after a failure, a distinct recover→diagnose→guard sequence (not just retry): the loss is turned into a durable guard/test | mutation, verification | T24 |
| **P7** | `discipline_encoded` **🛡️MOAT** | count files + lines of encoded standing rules (`CLAUDE.md`, `AGENTS.md`, `.claude/skills/**`) | configuration | MOAT |
| P7 | `config_coverage` **🛡️MOAT** | `.claude/settings*.json` hooks / git hooks / CI / memory scripts exist **and** sessions follow them | configuration | MOAT |
| P7 | `automation_vs_retyping` **🛡️MOAT** | rules that would be retyped each prompt live in config/skills/hooks (sparse retype + dense config = the fairness win) | configuration | MOAT |

> **Countable-first rule:** every sub-signal is scored from its partition (§7.3),
> not a gut read: the number is derived from `applied / eligible` blended with band
> anchors, with `verified_outcome` surfacing prove-don't-declare *per behaviour*.
> The two moat pillars (P6/P7) apply the **fairness framing**: encoded/automated
> discipline scores *up*; per-prompt re-typing does not.
>
> **Crosswalk completeness:** the table maps all 24 MEGA traits (T01–T24) — 17
> carried from v1, 7 NEW (`constraint_precision` T05, `progressive_disclosure` T10,
> `session_boundary_awareness` completing T03, `capability_provisioning` T14,
> `feedback_specificity` T21, `decision_rights` T18, `steering_calibration` T22,
> `rationale_recorded` completing T12, `recovery_discipline` completing T24) — PLUS
> the MEGA-blind moat sub-signals (`cross_session_inheritance`, `discipline_encoded`,
> `config_coverage`, `automation_vs_retyping`) with no MEGA equivalent. That is the
> strict-superset proof. Full table with status column: see `CROSSWALK.md`.

---

## 1c. Episode model + the partition (the scoring BASIS — v2)

> Closes DESIGN gaps G1 (holistic judgment → falsifiable partition) and G2 (no
> episode model → a defined denominator). This is what made the fresh dogfood run
> reproduce the workflow to Δ1; v2 makes it structural, not lucky.

**Episode.** A **task episode** is a contiguous objective span — initiation (a real
`user` task-initiating turn) → work (turns/tool-calls/sidechains) → outcome
(completed / abandoned / re-scoped). Sidechain (Task/Agent) spawns belong to the
episode that spawned them. `coverage.task_episodes` is the **count of episodes** in
the window and is **THE denominator + hard upper bound** for every sub-signal's
`eligible` (a sub-signal can never be eligible in more episodes than exist).

**Partition.** Every sub-signal is scored as a partition over the episodes where the
behaviour *could* apply:

```
eligible = applied + declined + missed        (a strict partition — they sum exactly)
verified_outcome <= applied                    (of the applied, how many were independently confirmed)
```

- `applied` — episodes where the developer **did** the good behaviour.
- `declined` — episodes where **correctly not doing it** is the good call
  (declined a bad option / correctly chose not to delegate / re-scoped a bad task).
  **`declined` counts POSITIVE** — it is credit, exactly the credit-positive rule
  (§3). It is NOT a miss.
- `missed` — episodes where the behaviour was warranted but absent (the only
  negative bucket).
- `verified_outcome` — subset of `applied` that got an **independent** confirmation
  (a check ran, output inspected, a failure was made to stop recurring). Surfaces
  prove-don't-declare *per behaviour* (§C.4) and feeds the card's "% VERIFIED" stat.

**Derivation (score is DERIVED, not a gut number).** The 0–100 sub-signal `score`
is derived from the partition, then nudged onto the band anchors — never invented:

```
credit_rate = (applied + declined) / eligible          # declined counts positive
base        = round(100 * credit_rate)
# band nudge: clamp/shape 'base' to the observed anchor tier (weak/developing/
#   strong/elite) from §1b + SKILL §4, so an anchor and a rate can't disagree.
# verified_outcome informs but does NOT double-penalize: it drives the card's
#   %-VERIFIED stat and can cap an inflated 'elite' when applied were never checked.
score = band_nudge(base, anchor_tier, verified_outcome, applied)
```

The pillar `score` (0–100) is the average of its **measured** sub-signal scores
(weighted where a pillar's method says so, §1). This keeps the OVERALL formula
(§3) and weights **unchanged** — the partition is the *reason* for the number, not a
new number the renderer must learn.

---

## 1d. measurement_status + limitations taxonomy (honest-empty, structural — v2)

> Closes G5: `eligible:false/score:null` was too coarse. v2 makes honest-empty a
> first-class structural distinction with a machine-readable reason, at both the
> sub-signal and pillar level.

Every sub-signal (and every pillar) carries a `measurement_status`:

- **`measured`** — `eligible >= 3`. Enough episodes to trust the number; `score`
  is a real 0–100, `limitations` is `null`.
- **`unmeasured`** — `eligible <= 2`. Too thin to score; `score` is `null`, and a
  **`limitations`** code MUST be present naming *why*. `unmeasured` is honest, not a
  failure — it is the opposite of fabricating a number from nothing.

**`limitations` codes (closed set):**

| code | when |
|---|---|
| `no-opportunity` | `eligible == 0` — the behaviour never had a chance to appear (e.g. no delegation happened, so P4 sub-signals had nothing to score). |
| `below-threshold` | `eligible ∈ {1, 2}` — it appeared, but too few times to trust a rate. |
| `extraction-gap` | the depended-on capability was **gated out** for this window (§2c) — the harness could not record the behaviour, so it is `unmeasured`, **never a low score.** This is the fairness fix (G3). |
| `narrow-window` | the coverage window itself was too short/narrow for this signal to accumulate (thin history, few active days). |
| `retention-window-bounded` | evidence needed for this signal predates the retained session history (older sessions rolled off disk) — bounded by retention, not by the developer. |
| `harness-capability-missing` | the Claude Code version / harness on this machine does not emit the field this signal needs (schema-version gap), distinct from a behaviour simply not occurring. |

A `measured` pillar requires at least one `measured` sub-signal; if all a pillar's
sub-signals are `unmeasured`, the pillar is `unmeasured` (→ v1 `eligible:false`,
`score:null`, excluded from OVERALL). This preserves the v1 eligibility semantics
exactly (§1) while adding the reason.

---

## 2c. Capability-gating map for Claude Code history (fairness + honesty — v2)

> Closes G3: a behaviour must never be read *low* because the harness could not
> show it. First model what Claude Code history CAN and CANNOT record, then gate.

Claude Code JSONL history exposes a fixed set of **capabilities** (what kind of
behaviour is observable in the transcript). Each sub-signal in §1b declares which
capabilities it depends on. For a given scan window, classify each capability:

- **`observable`** — the transcript reliably records it this window. Sub-signals
  depending only on observable capabilities are scored normally.
- **`partial`** — recorded but lossy/incomplete this window (see per-capability
  notes). Depending sub-signals are scored, but conservatively; if the specific
  evidence is missing, mark that sub-signal `unmeasured` + `extraction-gap`.
- **`gated_out`** — not recorded this window at all. Every depending sub-signal is
  `unmeasured` + `extraction-gap` (per §1d), **NEVER a low score.**

**Capability inventory (Claude Code):**

| capability | what it records | default class | notes |
|---|---|---|---|
| `message` | `user`/`assistant` text turns | observable | the base signal; almost always present |
| `retrieval` | `Read`/`Grep`/`Glob` + their `tool_result`s | observable | powers inspect-before-edit, anchoring |
| `mutation` | `Edit`/`Write` + results | observable | the "did work happen" signal |
| `verification` | `Bash` test/compile/lint/`curl` + exit codes in `tool_result` | observable | powers P5; can be `partial` if receipts live only in un-sampled sidechains |
| `delegation` | `Task`/`Agent`/`TaskCreate` spawns + returns | observable | powers P4; `gated_out` when no delegation occurred at all |
| `configuration` | the repo discipline surface (CLAUDE.md / skills / hooks / settings / memory scripts), read from disk | observable | powers P6/P7 + fairness; independent of chat volume |
| `attachment` | injected file-read context blocks | observable | supports anchoring/context economy |
| `compaction` | `summary` / compaction markers across a long window | **partial** | lossy: a compacted span hides mid-turn detail → `session_boundary_awareness`, `cross_session_inheritance` scored conservatively |
| `branch` | conversation branches / re-runs | **partial** | Claude Code records these unevenly by version → treat depending evidence cautiously |

**Gating rule (fairness anchor):** if a sub-signal's declared capability is
`gated_out` or the specific evidence is absent under a `partial` capability, that
sub-signal is `unmeasured` with `limitations: "extraction-gap"` — it is **excluded**
from the pillar average (not scored 0). The report's top-level
`capability_gating` block (§7.4) records the `observable / partial / gated_out`
classification for the window so the read is auditable.

---

## 2d. Containment consistency (structural rigor — v2)

> Closes DESIGN C.6: once everything is a partition, parent/child counts must be
> consistent, or the numbers are not trustworthy.

Once partitioned, the following invariants hold and the renderer validates them
**fail-loud** (mirroring MEGA's server check):

1. **Component-wise containment.** For every sub-signal `s` under pillar `P`, each
   of `{eligible, applied, declined, missed, verified_outcome}` for `s` is
   `<= ` the pillar `P`'s corresponding roll-up. A sub-signal cannot claim more
   episodes than its pillar saw.
2. **Partition holds at both levels.** `eligible == applied + declined + missed`
   for every sub-signal AND for every pillar roll-up.
3. **Verification bound.** `verified_outcome <= applied` everywhere.
4. **Measurement containment.** A `measured` sub-signal requires a `measured`
   pillar (you cannot have trustworthy child evidence under an untrustworthy
   parent). Equivalently: an `unmeasured` pillar has only `unmeasured` sub-signals.
5. **Episode ceiling.** No pillar's `eligible` exceeds `coverage.task_episodes`.

A report that violates any of these is malformed; the renderer raises (exit 2),
never renders a fabricated-consistent card.

---

## 2. Meta-metrics (shown, NOT part of the 0–100 average)

Displayed on the card as context, never folded into OVERALL:

- **OUTCOME rate** — goal-completion signals (tasks that reached their stated
  "done when X"). Reported as a rate 0–100% with a count.
- **EFFICIENCY** — turns-to-outcome, rework ratio, and context-economy. Reported
  as a compact index plus its components (`turns_per_outcome`, `rework_ratio`,
  `context_reuse`).
- **COVERAGE** — how much history the score is based on: sessions, episodes, and
  the time window. Low coverage ⇒ lower confidence; the card shows a confidence hint.

Meta-metrics are **descriptive**, not graded, so a fast/slow style is not punished
as if it were a skill deficit.

---

## 3. OVERALL formula, tiers

```
OVERALL = weighted_mean( pillar.score for pillar in P1..P7 if pillar.eligible )
```

- **Default pillar weights** (sum to 1.00 over the 7; renormalize over *eligible*
  pillars if any are ineligible):
  ```
  P1 Intent & Framing        0.16
  P2 Context & Grounding     0.16
  P3 Execution & Diagnosis   0.15
  P4 Orchestration           0.13
  P5 Verification            0.16
  P6 Memory & Continuity     0.12   [moat]
  P7 System-Discipline       0.12   [moat]
  ```
  Weights live in the report (`weights` block) so they are auditable and tunable.
- **Tiers** (mirrors MEGA's credit-good-habits spirit):
  ```
  85–100  diamond
  75–84   gold
  65–74   silver
   0–64   bronze
  ```
- **Credit-positive rule:** good habits count up. Notably, **"declined a bad
  option" / "correctly chose not to act" counts positive** (as in MEGA). The system
  is not a gotcha-hunter.

---

## 4. Fairness rule (load-bearing)

**Credit standing conventions.** If the repo's `CLAUDE.md` / `.claude/skills` /
hooks / gates encode a discipline, the user gets credit for that discipline **even
if they did not re-type it in each prompt.** This is exactly what MEGA misses:
MEGA reads chat only, so a developer who *automated* their rigor looks lazy while a
developer who *re-pastes* the same rules every prompt looks diligent. AGENTCRAFT inverts
that: encoding discipline into the system is the **higher** skill and is scored as
such (primarily via P7, and as positive evidence across P1/P2/P4/P5).

The renderer and coaching MUST reflect this: a high P7 with sparse per-prompt
repetition is a **strength**, not a gap.

---

## 5. Coaching output contract (the differentiator)

AGENTCRAFT is a **skill-development coach.** For **each pillar whose score is below its
target**, the report MUST contain a coaching entry that teaches **YOU — the human**
how to **level up your own skill** as an AI-coding collaborator. The prescription is
a **transferable personal habit you build in yourself** — a way of working that
carries to every codebase, every model, every AI session you'll ever run — **not** a
change to your agents, tools, hooks, extractor, or infrastructure. Target defaults to
the tier boundary the user is chasing (default target = 75, the gold line;
configurable per run). Each entry has exactly these fields:

```
pillar        : "P3"                      # which pillar
title         : short human label         # e.g. "Build your read-before-edit reflex"
weak          : what is weak (specific, evidence-anchored, from YOUR OWN work)
why           : WHY building this habit makes YOU a stronger AI-collaborator
                (the transferable payoff — across every codebase + every session,
                plus the cost the current gap keeps costing you)
how           : the concrete PERSONAL practice YOU adopt — a habit you build in
                yourself, phrased in the second person ("your next 5 edits, Read
                first"). NOT an infra/tooling/agent change.
example       : how YOU phrase or sequence things differently next time — a line
                you say/do yourself, adapted from your own work
retest_tip    : a personal behavior to WATCH IN YOURSELF on your next scan
                (a measurable signal you'll feel improve)
```

**The self-improvement rule (load-bearing — this is the North-Star).** Each weak
pillar maps to **a skill you develop + a personal practice you adopt + why it makes
you stronger + a behavior to track in yourself.** The prescription is
self-improvement, growth, leveling-up — never "tweak your setup".

- **GOOD** (`how`): *"Build the read-before-edit habit yourself: before you change a
  file, read the relevant lines and state your understanding in one sentence. This is
  the core diagnosis skill and it transfers to every codebase. Practice: your next 5
  edits, Read first."*
- **BAD** (forbidden as the primary `how`/`example`): *"make your angels echo
  `file:line` into the main thread", "add a `TaskCreate` to your wave", "wire your
  extractor to…"* — that is infra-plumbing, not a habit you build in yourself. An
  infra tip MAY appear only as a brief **secondary aside** after the personal
  practice, never as the coaching itself.

Voice: **warm, second-person, developmental — a coach, not a verdict.** Say "you".
Be encouraging and concrete, specific to the evidence, always about a habit the human
practices. Never generic ("communicate better") — always a personal move ("next
debug, before you touch the file, type 'Root cause: ___' and force yourself to fill
the blank").

Still evidence-anchored + prove-don't-declare: `weak` is pinned to the user's own
work (the sub-signal partition + a curated own-work excerpt where available). Only the
**prescription** changes — from "fix your infra" to "build this habit in yourself".

Pillars **at or above** target still get a one-line affirmation (optional
`strengths[]` array) but no full coaching block.

---

## 5b. Descriptive blocks + cross-cutting synthesis (richer, teachable — v2)

> Closes G7 (thin coverage, no descriptive blocks — the card couldn't *show
> compounding*) and G8 (no cross-cutting synthesis beyond per-pillar coaching).
> All blocks are **optional + descriptive** — never folded into OVERALL (same
> contract as meta-metrics, §2). They make the card teachable and let it show our
> whole thesis — P6/P7 growing over weeks — visibly.

**`profile`** — inferred, not asked: `{ role, experience, team, goal }` (free
strings; each SHOULD carry evidence or be omitted; prove-don't-declare — an
un-inferable field is omitted, never guessed).

**`style`** — observed coding style:
`{ paradigm, typing, testing, architecture, error_handling, abstraction }`
(free strings, e.g. `typing: "strict / type-hints everywhere"`).

**`work_mix`** — a count map over **9 task kinds**, summing to (roughly) the
episode count: `feature`, `bugfix`, `refactor`, `debug`, `test`, `docs`, `ops`,
`research`, `review`. Descriptive only — a fast/slow or feature-heavy/bug-heavy
mix is never a skill deficit.

**`collaboration_shape`** — the shape of the human↔agent loop:
`{ corrections, re_instructions, restarts, median_turns, max_concurrency }`
(counts + a median). Corrections/restarts are *observations*, not penalties.

**`trend`** — a per-week array `[ { week, overall, P6, P7, ... } ]`. This is the
block that lets the card **show P6/P7 compounding over weeks** — our whole thesis
made visible. Each entry is a week key (`YYYY-Www`) + that week's OVERALL and any
pillars worth trending. Emit only weeks the window actually covers.

**`practices[]`** — durable habits observed, by area:
`{ area:"P5", habit:"…", evidence:[…] }`. The positive meta-pattern layer.

**`anti_patterns[]`** — recurring costs, by area, each with a **cost token**:
`{ area:"P3", cost:"rework", observation:"…", evidence:[…] }`.
`cost ∈ { rework, wasted-context, undetected-defect, manual-toil, stalled-thread }`.
Brave-honest in both directions — a specific counter-observation beats another
compliment. Evidence-anchored like everything else (no evidence ⇒ do not assert).

---

## 6. Privacy stance (honest data-flow — the core feature)

AGENTCRAFT is a **coach**, and a coach has to read your work — so let's be precise about who
reads it and where it goes. **The judge is the user's *own* Claude Code agent** (their
existing session / Anthropic channel — the same one they already use), reading their local
history + repo to coach them. That is the honest data-flow, not "the AI never sees it."

- **Your own agent is the judge.** No separate scoring API, no extra API key, no *other*
  cloud model grading you. The judge is the local Claude Code agent following this runbook.
- **The extractor curates, so the read is bounded.** `agentcraft_extract.py` (pure stdlib, zero
  network) pre-digests the whole history on disk and hands the agent a small, redacted set
  of **representative excerpts** — the relevant slices that drove each weak signal — so the
  agent deep-reads what matters, not a raw dump of the entire history. Depth without the
  total-dump tragedy. An optional **counts-only lite mode** (`--max-excerpts 0`) scores from
  mechanical counts with **no excerpts read**, for the privacy-paranoid.
- **Zero third-party egress.** No MEGA, no AGENTCRAFT server, no telemetry, no HTTP POST of user
  data, no external API for user data. There is no network primitive in any shipped file
  (extractor + renderer are grep-clean of `requests`/`urllib`/`socket`/`POST`).
- **The report stays local.** The skill reads locally, reasons locally, and writes a **local
  report file** that stays on the user's machine.
- **Open-source, MIT.** Report files are git-ignored by default (see `.gitignore`) so a user
  never accidentally commits their own session analysis.

> **What we will NOT claim:** that AGENTCRAFT "never transmits" your data to the model or that
> "the AI never sees it." It does — a coach must. The true, narrower, honest claim is:
> *your own Claude, reading curated local slices to coach you, with zero egress to any
> third party.* Precision over marketing (prove-don't-declare).

---

## 7. Report-file schema v2 (the renderer consumes this)

The skill writes ONE local file. Canonical format is **JSON** (default filename
`agentcraft-report.agentcraft.json`). A human-readable Markdown twin (`agentcraft-report.agentcraft.md`)
MAY be emitted for reading, but the **renderer reads the JSON**. This is the
contract between the skill (producer) and `render/agentcraft_card.py` (consumer).

**v2 is a strict, backward-tolerant superset of v1.** Read §7.1 → §7.8 as one
schema. A consumer branches on `agentcraft_version`: `"2"` unlocks the v2 blocks
(partition sub-signal objects, capability gating, containment, descriptive/synthesis
blocks); anything else is read as v1 and MUST still validate and render (§7.2).

### 7.1 Top-level shape (v2)

```jsonc
{
  "agentcraft_version": "2",                 // "2" enables v2 blocks; "1"/absent => read as v1
  "brand": "AGENTCRAFT",                     // provisional; mirrors SPEC §0 BRAND
  "generated_at": "2026-09-11T00:00:00Z",
  "subject": { "label": "local-user", "repo_path": "C:/…/some-repo" },

  "coverage": {                         // META — descriptive, not graded
    "sessions": 12,
    "episodes": 47,
    "task_episodes": 47,                // v2: THE denominator (§1c). == episodes, named explicitly
    "distinct_active_days": 18,         // v2 (optional): drives confidence + narrow-window
    "task_classes_covered": 7,          // v2 (optional): 0..9 of the work_mix kinds seen
    "window": { "from": "2026-08-01", "to": "2026-09-10" },
    "confidence": "medium",             // low | medium | high (derived from volume + read depth)
    "sub_sampled": false                // v2 (optional): true if largest-N sessions sampled, not all
  },

  "meta_metrics": {                     // META — shown, NOT in OVERALL (unchanged from v1)
    "outcome_rate": { "pct": 78, "completed": 21, "attempted": 27 },
    "efficiency":   { "index": 71, "turns_per_outcome": 6.2,
                      "rework_ratio": 0.18, "context_reuse": 0.62 },
    "verified_rate": { "pct": 64, "verified": 43, "applied": 67 },  // v2: card "% VERIFIED" stat
    "coverage_ref": "see coverage block"
  },

  "weights": { "P1":0.16,"P2":0.16,"P3":0.15,"P4":0.13,"P5":0.16,"P6":0.12,"P7":0.12 },
  // ... pillars (§7.2), measurement_status (§7.3), capability_gating (§7.4),
  //     overall, coaching, strengths (§7.5), descriptive + synthesis (§7.7), config (§7.8)
}
```

### 7.2 Pillars — partition objects (v2) with v1 backward-tolerance

A pillar keeps its v1 fields (`name`, `eligible`, `score`, `evidence`, `moat`) so
the OVERALL formula is **unchanged**, and ADDS `measurement_status`, `limitations`,
and a pillar-level `partition` roll-up (sum/max over its measured sub-signals) so
containment (§2d) is checkable one level up.

**`sub_signals` in v2 is a map of OBJECTS** (v1 was a map of bare numbers). Each
object carries `score` (the derived 0–100, §1c), `measurement_status`, the partition
(`eligible/applied/declined/missed/verified_outcome`), `limitations`, `capability`,
and `evidence`.

> **Backward-tolerance (the migration bridge).** The renderer MUST accept BOTH
> shapes: a bare-number `sub_signals` value (v1) renders as a plain micro-bar; an
> object `sub_signals` value (v2) is read via `.get("score")` and renders the extra
> stats. A v1 report (bare numbers, no `measurement_status`, no `partition`) stays
> fully valid + renderable. The current v1 renderer already skips non-numeric
> sub_signal values silently, so a v2 file degrades gracefully on a v1 renderer.

```jsonc
"pillars": {
  "P3": {
    "name": "Execution & Diagnosis",
    "eligible": true,                   // v1 field: derived from measurement_status (measured => true)
    "measurement_status": "measured",   // v2: measured | unmeasured
    "score": 71,                        // 0-100 (avg of MEASURED sub-signal scores), or null if unmeasured
    "limitations": null,                // v2: null when measured; a §1d code when unmeasured
    "moat": false,                      // v2 optional on non-moat pillars; true on P6/P7
    "partition": {                      // v2: roll-up over measured sub-signals (containment parent)
      "eligible": 40, "applied": 27, "declined": 5, "missed": 8, "verified_outcome": 19
    },
    "sub_signals": {
      "inspect_before_edit": {          // v2 OBJECT form
        "score": 68,
        "measurement_status": "measured",
        "capability": "mutation",       // depended-on capability (§2c)
        "eligible": 14, "applied": 9, "declined": 2, "missed": 3,
        "verified_outcome": 6,          // <= applied
        "limitations": null,            // null when measured
        "evidence": [ { "session": "s3", "turn": 12, "note": "Read x.py before Edit x.py" } ]
      },
      "capability_provisioning": {      // v2 example of an UNMEASURED sub-signal
        "score": null,
        "measurement_status": "unmeasured",
        "capability": "configuration",
        "eligible": 1, "applied": 1, "declined": 0, "missed": 0, "verified_outcome": 0,
        "limitations": "below-threshold",   // §1d code REQUIRED when unmeasured
        "evidence": []
      }
    },
    "evidence": [ { "session": "s3", "turn": 40, "note": "root cause named before fix" } ]
  },
  "P6": { "name":"Memory & Continuity", "eligible":true, "score":58, "moat":true, "measurement_status":"measured",
          "limitations":null, "partition":{...}, "sub_signals":{...}, "evidence":[...] },
  "P7": { "name":"System-Discipline",   "eligible":true, "score":85, "moat":true, "measurement_status":"measured",
          "limitations":null, "partition":{...}, "sub_signals":{...}, "evidence":[...] }
  // ... all of P1..P7 present, always.
}
```

An **unmeasured pillar** (all sub-signals unmeasured, §1d) sets
`"eligible": false, "score": null, "measurement_status": "unmeasured",
"limitations": "<code>"` and is excluded from OVERALL — exactly v1 semantics + a reason.

### 7.3 measurement_status (per sub-signal + per pillar)

`measurement_status ∈ { "measured", "unmeasured" }`; when `"unmeasured"`,
`limitations ∈ { "no-opportunity", "below-threshold", "extraction-gap",
"narrow-window", "retention-window-bounded", "harness-capability-missing" }` (§1d).
`measured ⇔ eligible >= 3`; `unmeasured ⇔ eligible <= 2`. A measured sub-signal
requires a measured parent pillar (containment, §2d.4).

### 7.4 capability_gating (v2, top-level)

Records how each Claude Code capability (§2c) was classified for this window, so the
read is auditable. Sub-signals whose capability is `gated_out` are `unmeasured` +
`extraction-gap`.

```jsonc
"measurement_status": { "overall": "measured", "note": "sidechains sampled; compaction partial" },
"capability_gating": {
  "observable": ["message","retrieval","mutation","verification","delegation","configuration","attachment"],
  "partial":    ["compaction","branch"],
  "gated_out":  []                      // e.g. ["delegation"] if no delegation happened this window
}
```

### 7.5 overall / coaching / strengths (unchanged contract)

```jsonc
"overall": { "score": 72, "tier": "silver" },   // weighted mean over eligible pillars (unchanged)

"coaching": [ {                        // one entry PER eligible pillar below config.target
  // NOTE: the PRESCRIPTION (how/example/retest_tip) is a transferable HUMAN habit
  //       YOU build in yourself — not an infra/agent/tooling change (SPEC §5).
  "pillar": "P3", "title": "Build your name-the-cause reflex",
  "weak": "In several debug episodes you patched the first failing symptom before you'd said what actually caused it — the diagnosis instinct was there, but you didn't lead with it yourself.",
  "why": "Naming the cause before you fix is the core diagnosis muscle — it transfers to every codebase and every AI session you'll run. Build it in yourself and you stop shipping symptom-patches that regress and burn next session's turns.",
  "how": "Make it a personal reflex: your next 5 debugs, before you touch the file, say one sentence out loud — 'Root cause: ___' — and force yourself to fill the blank. Only then fix. It's a habit, not a rule you type.",
  "example": "Next debug, before your edit, type to yourself: 'Root cause: pool connection shared across coroutines.' — then fix that, not the stack-trace line.",
  "retest_tip": "Next scan, watch your own root_cause_depth: aim to feel yourself state a cause before the fix in every debug episode you run."
} ],

"strengths": [                         // optional; renderer tolerates str OR {pillar,note} (do not regress)
  { "pillar": "P7", "note": "Discipline is encoded in CLAUDE.md + skills — full credit without re-typing." }
]
```

### 7.6 (reference) sub-signal catalog

The full ~40 sub-signal set (7 pillars, all 24 MEGA traits + 4 moat sub-signals)
is defined in §1b with cues, capability tags, and trait mapping; band-anchor prose
+ per-sub-signal partition-counting rules live in `skill/agentcraft-assess/SKILL.md` §4.
A v2 producer SHOULD fill the catalog's sub-signals (as objects) for each measured
pillar; unmeasured ones carry `score:null` + a `limitations` code (never omitted
silently — honest-empty is structural, §1d).

### 7.7 Descriptive + synthesis blocks (v2, all optional + descriptive)

Never folded into OVERALL (§5b). Omit any block that cannot be inferred with
evidence (prove-don't-declare) rather than guessing.

```jsonc
"profile":   { "role":"solo founder / full-stack", "experience":"senior", "team":"solo", "goal":"ship a local-first tool" },
"style":     { "paradigm":"pragmatic OO+functional", "typing":"strict type-hints", "testing":"self-verify + fixtures",
               "architecture":"single-source contract", "error_handling":"fail-loud", "abstraction":"low, direct" },
"work_mix":  { "feature":14, "bugfix":9, "refactor":4, "debug":8, "test":3, "docs":5, "ops":2, "research":1, "review":1 },
"collaboration_shape": { "corrections":11, "re_instructions":6, "restarts":2, "median_turns":6, "max_concurrency":6 },
"trend": [
  { "week":"2026-W34", "overall":68, "P6":48, "P7":74 },
  { "week":"2026-W35", "overall":71, "P6":54, "P7":80 },
  { "week":"2026-W36", "overall":74, "P6":58, "P7":85 }   // P6/P7 compounding — the thesis, visible
],
"practices":     [ { "area":"P5", "habit":"pastes the exit line as a closure receipt", "evidence":[{"session":"s7","turn":33}] } ],
"anti_patterns": [ { "area":"P3", "cost":"rework", "observation":"3 edits before a Read on the same path",
                     "evidence":[{"session":"s4","turn":9}] } ]
```

### 7.8 config (what this run used)

```jsonc
"config": {
  "target": 75,
  "tier_bands": { "diamond": 85, "gold": 75, "silver": 65 },
  "credit_positive": true,             // "declined a bad option" counts up (declined bucket, §1c)
  "fairness_rule": true,               // credit standing conventions
  "measurement_threshold": 3           // v2: measured requires eligible >= this (default 3)
}
```

### Schema invariants v2 (the renderer relies on / validates these)

*Carried from v1 (unchanged — a v1 report satisfies these):*
1. `pillars` always contains keys `P1..P7`; ineligible pillars have
   `eligible:false` and `score:null`.
2. `overall.score` is an integer 0–100; `overall.tier` ∈
   {diamond, gold, silver, bronze} consistent with `config.tier_bands`.
3. `meta_metrics`, `coverage`, and all §7.7 descriptive/synthesis blocks are
   **never** folded into `overall`.
4. Every graded (eligible) pillar SHOULD carry ≥1 `evidence` item.
5. `coaching` has one entry per eligible pillar with `score < config.target`.
6. `brand` mirrors the SPEC §0 `BRAND` value — single source of truth for rename.

*v2 additions (validated fail-loud when `agentcraft_version == "2"`; §2d):*
7. **Partition holds** for every v2 sub-signal object AND every pillar `partition`
   roll-up: `eligible == applied + declined + missed`.
8. **Verification bound:** `verified_outcome <= applied` everywhere.
9. **Component-wise containment:** each of `{eligible, applied, declined, missed,
   verified_outcome}` for a sub-signal is `<=` its pillar's corresponding roll-up.
10. **Measurement containment:** a `measured` sub-signal requires a `measured`
    pillar; `measured ⇔ eligible >= config.measurement_threshold` (default 3),
    `unmeasured ⇔ eligible <= threshold-1` AND `limitations` is a valid §1d code.
11. **Episode ceiling:** no pillar `partition.eligible` exceeds
    `coverage.task_episodes`.
12. **Backward-tolerance (the bridge):** a report with `agentcraft_version != "2"`, or a
    v2 report whose `sub_signals` values are bare numbers, MUST still validate and
    render as v1 — invariants 7–11 apply **only** to v2 sub-signal OBJECTS.

---

## 8. What ships (artifacts)
1. `skill/agentcraft-assess/SKILL.md` — the assessment + coaching runbook (producer of §7).
2. `render/agentcraft_card.py` — offline renderer (consumer of §7): FIFA-style card +
   7-axis radar + growth-plan (coaching) panel + v2 panels (% verified, measurement
   badges, trend, practices/anti-patterns). No network. Reads JSON, writes image.
3. `agentcraft_extract.py` — pure-stdlib streaming extractor (mandatory Step 1): emits
   per-episode partition counts so the agent scores *from counts*, not vibes. No network.
4. `README.md` — world-class docs, credits MEGA, states privacy stance.
5. `SPEC.md` (this file), `RUBRIC.md`, `CROSSWALK.md` (24-trait → home table),
   `MIGRATION.md` (v1→v2 backward-tolerance note) — the contract downstream builders inherit.
6. `LICENSE` (MIT), `.gitignore`, `examples/` (synthetic fixtures only —
   `sample-report.agentcraft.json` v1 + `sample-report-v2.agentcraft.json` v2).

---

*AGENTCRAFT v2 spec. A strict superset of MEGA — all 24 traits, mapped under a cleaner
card — PLUS the two axes MEGA can't see, PLUS a coach, PLUS 100% local. Deeper,
broader, ours. Backward-tolerant to v1. Prove-don't-declare.*
