# AGENTCRAFT — Scoring Rubric (agent-facing) · v2

> Concise rubric the assessing agent follows. For the full contract, formulas, and
> report schema see **SPEC.md** (v2). The full band-anchor prose + per-sub-signal
> partition-counting rules live in **SKILL.md §4**; the 24-trait map is in
> **CROSSWALK.md**. BRAND is defined once in SPEC.md §0 (`BRAND = "AGENTCRAFT"`).
>
> **You are a coach, not a scorekeeper.** The number is the anchor; the *value* is that
> you genuinely read the developer's work and explain **what** they did, **how** they
> work, **where** they're weak and **why** it costs them, and **how** to improve — with
> an example from their **own** history. A counts-only readout is the shallow sin AGENTCRAFT
> exists to fix. Score honestly; coach usefully.
>
> **Honest data-flow (say it straight if the user asks):** the judge is the user's *own*
> Claude Code agent, reading their local history + repo to coach them — a coach must see
> the work. The extractor curates a small, redacted set of representative excerpts so you
> deep-read the *relevant slices*, not a raw dump. **Nothing is sent to any third party**
> (no MEGA, no AGENTCRAFT server, no telemetry); the report stays on the user's disk. There is
> an optional counts-only lite mode for the privacy-paranoid. Do **not** claim "the AI
> never sees your data" — it does, because coaching requires it; the true, narrower claim
> is *your own Claude, local, zero third-party egress.*
>
> **v2 in one line:** score every sub-signal as a **partition** (`eligible = applied +
> declined + missed`, `declined` counts *positive*, `verified_outcome ≤ applied`); the
> 0–100 number is **derived from the counts**, then nudged onto the bands below — never a
> gut read. Run the extractor (`agentcraft_extract.py`, SKILL Step 1) FIRST so you score from
> counts. v2 is a backward-tolerant superset of v1 — a v1 report still scores/renders.

## How to read (before scoring anything)

Read BOTH the chat AND the system, or the score is wrong. Gather:

1. **Session history** — local Claude Code transcripts/episodes in the window
   (turns, tool calls, results, completion claims).
2. **Repo discipline surface** — MANDATORY, this is what MEGA misses:
   - `CLAUDE.md` (root + `.claude/CLAUDE.md` + nested) — standing rules.
   - `.claude/skills/**` — encoded runbooks/skills.
   - hooks / gates — `.claude/settings*.json` hooks, pre/post-task gates, CI configs.
   - scripts — memory scripts, handoff files, ADR/decision logs, `MEMORY.md`.

**Prove-don't-declare:** every pillar score carries `evidence` (session/turn/file).
No evidence ⇒ don't inflate. **Credit-positive:** good habits count up; a correct
"declined a bad option" / "chose not to act" is **positive**, never a penalty (it is
the `declined` bucket, not a `missed`). **Fairness:** discipline encoded in files
counts even if not re-typed per prompt.

Scoring scale per signal: 0–39 weak · 40–64 developing · 65–84 strong · 85–100 elite.

### v2 scoring basis (do this per sub-signal, not "by feel")

1. **Segment episodes.** Split the window into task episodes (one objective span each).
   `coverage.task_episodes` is THE denominator + hard upper bound for every `eligible`.
2. **Partition each sub-signal** over the episodes it could apply to:
   `eligible = applied + declined + missed` (sums exactly), plus
   `verified_outcome ≤ applied` (of the applied, how many were independently confirmed).
3. **Derive the number:** `credit_rate = (applied + declined) / eligible`; `base = round(100 ×
   credit_rate)`; nudge `base` onto the band tier (weak/developing/strong/elite) so a rate
   and an anchor can't disagree. `verified_outcome` feeds the card's **% VERIFIED** stat and
   caps an inflated "elite" if the applied were never checked. **Never invent the number.**
4. **measurement_status:** `measured` if `eligible ≥ 3` (real 0–100, `limitations:null`);
   else `unmeasured` (`score:null`) with a `limitations` code — `no-opportunity` (eligible
   0), `below-threshold` (1–2), `extraction-gap` (capability gated out), `narrow-window`,
   `retention-window-bounded`, `harness-capability-missing`.
5. **Capability-gating (fairness):** if the depended-on capability (message / retrieval /
   mutation / verification / delegation / configuration / attachment / compaction / branch)
   is **gated out** this window, mark the sub-signal `unmeasured` + `extraction-gap` — **never
   a low score**. A behaviour the harness couldn't record is not a deficit.
6. **Containment:** each sub-signal's `{eligible,applied,declined,missed,verified_outcome}`
   ≤ its pillar's roll-up; a `measured` sub-signal needs a `measured` pillar. The renderer
   validates this fail-loud (SPEC §2d).

A pillar is `measured` if it has ≥1 `measured` sub-signal; else `eligible:false`,
`score:null`, excluded from OVERALL (v1 semantics + a machine-readable reason). Run the
**extractor** (`agentcraft_extract.py`, SKILL Step 1) FIRST so you score from real counts.

**Depth contract:** each pillar decomposes into **named sub-signals**, and each
sub-signal has a **countable observable cue** — see the indicator table in
[`SPEC.md`](./SPEC.md) §1b (canonical) and the full band-anchor prose in
[`SKILL.md`](./skill/agentcraft-assess/SKILL.md) §4. Score the cue, average sub-signals into
the pillar; never score a pillar "by feel". The most countable cues (use the §2b
extractor in SKILL): `inspect_before_edit` = Edits preceded by a Read/Grep on the same
path; `closure` = completion claims with a captured verify receipt; `delegation_judgment`
= right delegate-vs-inline calls; `context_economy` = inverse re-paste ratio + `usage`
cache reuse.

---

## P1 — Intent & Framing
- **Strong:** goals stated unambiguously; framed at the problem level; each task has
  a checkable "done when X"; bad tasks re-scoped/declined.
- **Weak:** vague asks; solution dictated before the problem is understood; no
  acceptance criteria ("just make it work").
- **Read:** task-initiating turns; CLAUDE.md task-framing conventions.
- **Sub-signals:** `goal_clarity` · `problem_framing` · `acceptance_defined` ·
  **`constraint_precision`** ➕v2 — prompt names the real constraints/non-goals (perf
  budget, "don't touch X", stack, deadline) *precisely*, not vaguely (T05).

## P2 — Context & Grounding
- **Strong:** decisions anchored to real files/logs/errors/tests; evidence supplied
  exactly at the decision; minimal re-paste; aware of what the agent already holds.
- **Weak:** decisions from memory/assumption; same context pasted repeatedly;
  contradicts state the agent already has.
- **Read:** decision points + surrounding turns; measure duplicate/re-pasted blocks;
  CLAUDE.md context conventions.
- **Sub-signals:** `artifact_anchoring` · `evidence_at_decisions` · `context_economy` ·
  `agent_state_awareness` · **`progressive_disclosure`** ➕v2 — context fed *when needed*
  (staged), not one giant dump up front (T10) · **`session_boundary_awareness`** ➕v2 —
  tracks what survives a compaction / new session; re-primes only what was lost, doesn't
  re-dump everything (completes T03; capability `compaction` — score conservatively if partial).

## P3 — Execution & Diagnosis
- **Strong:** inspects/reads before editing; reproduces the bug; states the
  **root cause** in one line; fixes cause not symptom.
- **Weak:** edits before reading; patches the first visible symptom; no repro; cause
  never named.
- **Read:** build/fix/debug episodes; ordering of inspect → diagnose → fix.
- **Sub-signals:** `understand_before_build` · `root_cause_depth` · `inspect_before_edit`
  (countable: Edit/Write preceded by a Read/Grep on the **same path**) ·
  **`capability_provisioning`** ➕v2 — before delegating/asking, user *equips* the agent
  (grants tools/MCP, points at the right skill, sets scope) rather than expecting blind
  success (T14) · **`feedback_specificity`** ➕v2 — corrections are specific + actionable
  ("wrong: it drops nulls; do X"), not vague ("nope, try again") (T21).

## P4 — Orchestration
- **Strong:** right delegate-vs-inline calls (both directions credited); clean
  decomposition; briefs carry goal+context+acceptance; parallel work is independent;
  sub-results verified before merge.
- **Weak:** delegates trivia or hoards work that should be split; vague briefs;
  colliding parallel edits; blindly accepts sub-results.
- **Read:** subagent/delegation episodes, decomposition, brief text, integration
  steps; CLAUDE.md orchestration rules (e.g. ">100 LOC ⇒ spawn").
- **Sub-signals:** `delegation_judgment` · `decomposition` · `brief_quality` ·
  `parallelism_hygiene` · `result_integration` · **`decision_rights`** ➕v2 — authority
  allocated correctly: agent decides reversible/local calls autonomously; user reserves
  the irreversible ones (deploy/spend/delete) (T18).
- **Capability note:** if **no delegation happened** this window, `delegation` is
  `gated_out` → the delegation-dependent sub-signals are `unmeasured` + `extraction-gap`
  (score `delegation_judgment` on a correct "don't delegate" if that call is visible).

## P5 — Verification
- **Strong:** verifies through a **different channel** than the one that made the
  claim (run it / test it / inspect the artifact — not "the agent said so"); closes
  the loop; acceptance is falsifiable.
- **Weak:** "trust me / looks right"; verification intended but not done; accept
  tests that can't fail.
- **Read:** every completion/correctness claim → was it independently, closed,
  falsifiably verified? CLAUDE.md verify gates (compile-check, smoke, tests).
- **Sub-signals:** `independent_channel` · `closure` · `falsifiable_acceptance` ·
  **`steering_calibration`** ➕v2 — trust calibrated to evidence: tighten the loop after
  a miss, loosen it after verified wins — neither blind-trust nor micromanage (T22).

## P6 — Memory & Continuity  **[MEGA-BLIND — moat]**
- **Strong:** decisions persisted durably (handoff/ADR/memory store/`MEMORY.md`);
  later sessions demonstrably reuse earlier knowledge; a past mistake is recorded
  and **not repeated**.
- **Weak:** everything re-derived each session; no memory artifacts; same mistake
  recurs across sessions.
- **Read:** ≥2 sessions or a memory artifact; look for inheritance/non-repetition.
- **Eligible-when:** window spans ≥2 sessions OR a memory artifact exists.
- **Sub-signals:** `decision_persistence` · **`cross_session_inheritance`** 🛡️moat
  (no MEGA equivalent — a later turn references an earlier decision; a session-start
  recall/summary read at boot) · `mistake_nonrepetition` (a BUG_FIX/LESSON exists AND the
  same error does not recur) · **`rationale_recorded`** ➕v2 — persisted decisions carry
  the *why* + provenance, not just the *what*; an ADR-shaped record (completes T12) ·
  **`recovery_discipline`** ➕v2 — after a failure, a distinct recover→diagnose→guard
  sequence (not just retry): the loss is turned into a durable guard/test (completes T24).

## P7 — System-Discipline  **[MEGA-BLIND — moat]**
- **Strong:** discipline **encoded** in CLAUDE.md / skills / hooks / gates / scripts;
  repeated instructions are automated, not re-typed; agent honored the encoded rules.
- **Weak:** no CLAUDE.md/skills/hooks; rules re-pasted every prompt or absent;
  config exists but is ignored.
- **Read:** the full repo discipline surface (see "How to read" #2). Always eligible
  — an empty discipline surface is an honest low score, not "no data".
- **Sub-signals (all 🛡️moat — no MEGA equivalent):** `discipline_encoded` (count files
  + lines of encoded standing rules) · `config_coverage` (`.claude/settings*.json` hooks /
  git hooks / CI / memory scripts exist **and** sessions follow them) ·
  `automation_vs_retyping` (rules that would be retyped each prompt live in config/skills/
  hooks — sparse retype + dense config = the fairness win). Capability: `configuration`
  (read from disk — independent of chat volume, so P7 is never `extraction-gap`).
- **Fairness anchor:** encoding discipline is the HIGHER skill; score it as such.
  Do NOT reward per-prompt re-typing over automation.

---

## After pillars
- **OVERALL** = weighted mean over *eligible* pillars (weights in SPEC §3; renormalize).
  A pillar is eligible ⇔ `measured` (≥1 measured sub-signal). Formula/weights unchanged v1→v2.
- **Tier:** 85+ diamond · 75–84 gold · 65–74 silver · <65 bronze.
- **Meta-metrics** (OUTCOME / EFFICIENCY / COVERAGE / **VERIFIED_RATE** v2): report, do
  NOT average in. `verified_rate` = sum(`verified_outcome`) / sum(`applied`) → card "% VERIFIED".
- **capability_gating** (v2): emit the `observable / partial / gated_out` classification for
  the window (SPEC §7.4) so the read is auditable; gated-out capabilities → their sub-signals
  `unmeasured` + `extraction-gap`, never scored low.
- **Descriptive blocks** (v2, optional, NEVER graded): `profile` · `style` · `work_mix` ·
  `collaboration_shape` · per-week `trend` (shows P6/P7 compounding) · `practices[]` ·
  `anti_patterns[]` (cost token ∈ rework/wasted-context/undetected-defect/manual-toil/
  stalled-thread). Prove-don't-declare — omit any block you cannot infer with evidence.
- **Coaching:** one entry per eligible pillar below target (default target 75) with fields
  `weak · why · how · example · retest_tip` (SPEC §5). Coach, not verdict — concrete,
  evidence-anchored, actionable. Affirm at/above-target pillars in one line. Prefer a
  `retest_tip` phrased as a partition ratio (e.g. "next scan: applied/eligible on X").
- **Emit** the JSON report per SPEC §7 (v2 superset) to a LOCAL file that stays on the
  user's disk. Send nothing to any third party (no external API/telemetry/upload of the
  user's data); the only judge is the user's own local Claude agent.
