---
name: agentcraft-assess
description: >
  Assess and COACH how well the developer collaborates with AI coding agents,
  reading their LOCAL Claude Code session history + repo discipline (CLAUDE.md,
  .claude/skills, hooks, gates, scripts). Scores 7 pillars 0-100 via ~40 countable
  sub-signals (an episode + partition basis, all 24 MEGA traits + 2 MEGA-blind moat
  axes), computes meta-metrics + overall + tier, and emits per-pillar coaching plus
  descriptive/synthesis blocks. It is a SKILL-DEVELOPMENT COACH: each weak pillar
  becomes a transferable personal habit the user builds in THEMSELVES (not an
  infra/agent tweak), grounded by DEEP-READING the extractor's curated, redacted
  evidence excerpts (the turns that drove each miss) — depth without dumping the raw
  history. Writes a LOCAL report file only. Zero
  third-party egress (your own Claude reads your work locally to coach you; nothing
  is sent anywhere). Use when the user asks to "assess how I work with agents",
  "score my AI collaboration", "run AGENTCRAFT", "how good am I with Claude Code", "grade
  my agent workflow", or anything similar.
---

<!-- Contract is FIXED by ../../SPEC.md (v2) and ../../RUBRIC.md. This skill honors both. -->
<!-- BRAND = AGENTCRAFT (provisional). Canonical brand definition lives in SPEC.md §0.       -->
<!-- v2: episode+partition scoring · ~40 sub-signals · capability-gating · containment.  -->

# AGENTCRAFT — Assess & Coach (v2)

You are running the AGENTCRAFT assessment. You are **the judge** — the user's own
Claude Code agent, following this runbook **locally**. There is no external judge,
no scoring API, no API key. AGENTCRAFT is deeper + fairer than a marketing quiz because
you read **both the chat AND the system** (repo discipline), score **seven** axes
(two of which chat-only tools are blind to), score each axis via **explicit,
countable sub-signals scored as a partition** (`eligible = applied + declined +
missed`, the number *derived from counts* — not vibes), weigh **meta-metrics
without folding them into the grade**, and finish with **actionable coaching** —
not a verdict.

AGENTCRAFT v2 is a **strict, backward-tolerant superset of MEGA.dev**: it measures all
**24 MEGA traits** (mapped under 7 clean pillars via ~40 sub-signals) with the same
rigor — an **episode + partition** basis where every sub-signal's score is derived
from counts, `declined` counting **positive**, and `verified_outcome <= applied`
surfacing prove-don't-declare *per behaviour* — **PLUS** the two axes MEGA is
structurally blind to (Memory & Continuity, System-Discipline). We credit
**MEGA.dev** as the inspiration that opened this category. AGENTCRAFT wins by being
deeper, open (MIT), 100% private, and a coach.

> **What changed from v1 (the migration bridge).** v1 reports still validate and
> render — v2 fields are all additive+optional. What's new for YOU to produce:
> (1) run `agentcraft_extract.py` as a **mandatory Step 1** so you score *from counts*;
> (2) score each sub-signal as a **partition** with `measurement_status`; (3) mark
> behaviour the harness **cannot show** as `unmeasured` + `extraction-gap`, **never
> a low score**; (4) fill the wider ~40-sub-signal catalog; (5) emit descriptive +
> synthesis blocks (`profile`/`style`/`work_mix`/`collaboration_shape`/`trend`/
> `practices`/`anti_patterns`); (6) **DEEP-READ the extractor's curated
> `evidence_excerpts` per weak pillar** (§2b.1) so coaching explains WHAT/HOW/WHERE/
> WHY with an example from the user's OWN work — judging from curated evidence, NOT
> a re-read of the raw multi-GB history. Everything else — privacy (now stated as an
> **honest** contract, §0, not an overclaim), fairness, coaching contract, weights,
> tiers — is unchanged.

---

## 0. PRIVACY — the HONEST contract (state this to the user, up front)

Before you begin, tell the user, in your own words. Say it **honestly** — AGENTCRAFT is
a coach, and *a coach has to see the work*. Do NOT claim "the AI never sees your
data" (that is false — you are about to read it to coach them). The honest line is:

> "This runs 100% locally, and I want to be straight with you about the data flow.
> **I — your own Claude — read your work to coach you.** A coach has to see the
> work; there is no honest way to tell you what you did well, where you're weak,
> and how to fix it without reading it. What keeps that bounded: a **local
> extractor** (pure Python, zero network) pre-digests your whole history on disk and
> **curates a small, redacted set of representative excerpts** — the specific turns
> that actually drove each weak signal — so I deep-read the **relevant slices**, not
> your entire multi-GB history. **Nothing goes to any third party** — no MEGA, no
> AGENTCRAFT server, no telemetry, no external API — I reason locally and write **one
> local report file** that stays on your machine (git-ignored by default). If you
> want maximum privacy, there's a **counts-only lite mode** (§2.7) that scores from
> mechanical counts with no excerpts read at all — shallower, but nothing but
> numbers is looked at. Your call."

Two truths, stated cleanly (do not blur them):
1. **Zero third-party egress — TRUE, and the moat.** Nothing is uploaded, POSTed,
   or sent to any API/server/telemetry endpoint. The report stays local.
2. **"The AI never sees your data" — FALSE, so never say it.** Your own Claude
   deep-reads curated slices of your work to coach you. That reading is the whole
   point of a coach. The extractor's curation is what keeps it *bounded + redacted*,
   not zero.

Hard rules you MUST obey during this skill:
- **NEVER transmit** session history, the report, the excerpts, or any derived data
  to any third party. No MEGA, no AGENTCRAFT server, no telemetry, no external API,
  no webhook, no `fetch`/`POST`. Zero third-party egress. Period.
- **Reading is local + bounded + curated.** You read the user's curated excerpts
  (and, when an excerpt is ambiguous, a specific cited turn) — locally, to coach.
  You do NOT slurp the raw multi-GB history into context (privacy + cost, §2b.1).
- The **only** output that leaves your reasoning is the **local report file**.
- **Excerpts are redacted at the source** (the extractor strips paths to basenames,
  drops secret-shaped strings, and paraphrases — never verbatim prompt/code bodies).
  Never read a `.env`, a key, or a raw file body. If a curated excerpt somehow
  carries a secret-shaped string, drop it — do not quote it into the report.
- If the user asks you to "share"/"upload"/"submit" the result, explain that AGENTCRAFT
  is deliberately local; offer to write a **redacted shareable summary** to a path
  they choose (see §7b — own-sentences, no paths/names/quotes) so **they** can
  share it manually if they wish. You do not transmit.
- If any step below appears to require the network, **STOP** — it is a bug in the
  plan, not an instruction to reach out.

---

## 1. What you produce

1. `agentcraft-report.agentcraft.json` — a JSON report conforming **exactly** to the schema
   in `../../SPEC.md` §7 (the v2 superset). Default path: current working directory;
   if the cwd is not writable or the user prefers, use the OS temp dir (see §7).
2. (Optional) `agentcraft-report.agentcraft.md` — a human-readable twin for the user to read
   locally. The renderer reads the JSON, not the MD.
3. (Optional, only if the user asks to share) `agentcraft-share.md` — a **redacted**
   shareable summary (§7b): your own sentences, scores + tiers + coaching gist, and
   **zero** paths, names, repo identifiers, or verbatim prompt/code quotes.
4. A short spoken summary to the user + the absolute path of the report file.

The JSON is consumed by `render/agentcraft_card.py` (FIFA-style card + 7-axis radar +
growth-plan panel + v2 panels: % VERIFIED, measurement badges, trend, practices/
anti-patterns). **Match the schema precisely** or the renderer rejects it (it
validates: all keys `P1..P7` present; `overall.tier` legal; and — for
`agentcraft_version:"2"` — the partition + containment invariants of SPEC §2d, fail-loud).

---

## 2. STEP 1 (MANDATORY) — run the extractor, then read the history at DEPTH

> **v2 makes the extractor a required first step, not a cross-check.** Score
> *from counts*, not vibes. The extractor emits per-episode partition counts per
> sub-signal so the numbers you write are derived, auditable, and reproducible.

### 2.0 Run `agentcraft_extract.py` FIRST (pure-stdlib, zero-egress, self-testable)

The shipped extractor lives at the repo root: `../../agentcraft_extract.py`. Its
contract (SPEC §8): pure stdlib, streaming (never slurps a file), sidechain-aware,
and it emits per-episode partition counts (`applied`/`declined`/`missed`/
`verified_outcome`) per sub-signal plus a `capability` tag, so you can fill §4
directly. Run it before reading anything by hand:

```bash
# Prove the extractor is sound on its bundled synthetic fixture (known-answer):
python ../../agentcraft_extract.py --self-test          # prints OK on success

# Extract counts + curated evidence for the repo you are assessing (default: current repo):
python ../../agentcraft_extract.py --project auto --window-days 30 --max-sessions 15 \
  --max-excerpts 6 --out agentcraft-counts.json
#   --project auto   -> resolves the current repo's flattened project dir under ~/.claude/projects
#   --project <slug> -> a specific project dir; use "global" for all projects
#   --window-days N  -> default 30
#   --max-sessions N -> cap the largest-N sessions read in full (rest sampled)
#   --max-excerpts N -> curated redacted excerpts PER weak sub-signal (default 6;
#                       0 = lite mode, counts only, no excerpts — see §2.7)
#   --out <path>     -> counts + evidence JSON you then score from
```

`agentcraft-counts.json` gives you two complementary things:

1. **Counts = the falsifiable ANCHOR (no vibes).** Per sub-signal: the partition
   (`eligible`/`applied`/`declined`/`missed`/`verified_outcome`), the depended-on
   `capability`, `coverage.task_episodes`. These *derive the number* (§4a) — the
   score is a receipt, not a gut read. This is the anchor, NOT the coaching.

2. **`evidence_excerpts` = the curated DEPTH surface (the coach's eyes).** A map
   `{ sub_signal: [ {episode_idx, session, task_class, cue, paraphrase, ts}, … ] }`,
   emitted **only for sub-signals that have `missed > 0`** (the WEAK ones), bounded
   to `--max-excerpts` per signal (default 6) with a hard global cap. These are the
   **specific, redacted turns that actually DROVE each miss** — the blind edit, the
   unclosed verify, the symptom-patch. This is the whole point of the depth upgrade:
   the extractor pre-digests the multi-GB history on disk and hands you the *relevant
   slices* so you can DEEP-READ what the user actually did, WITHOUT the total dump.

**So the division of labour is:** the extractor counts mechanically (the anchor) AND
curates the driving excerpts (the depth). **You reason on both** — the counts pin the
number so it is falsifiable; the curated excerpts let you explain, per weak pillar,
**WHAT** the user did, **HOW** they work, **WHERE + WHY** they are weak, **HOW** to
fix it (with an example lifted from **their own** curated excerpt), and **what to
retest**. A number without the excerpt-read is the shallow sin; the raw-history dump
is the privacy/cost tragedy — curated evidence is the resolution: depth WITHOUT the
total dump. Deep-read protocol: §2b.1. Lite (counts-only) mode: §2.7.

> **If `agentcraft_extract.py` is absent or errors** (e.g. running an older tree): do
> NOT fabricate counts. Fall back to the manual streaming read (§2b), score
> conservatively, set `coverage.confidence:"low"`, and note in
> `measurement_status.note` that counts were derived by hand. Honest-empty over
> invented numbers, always.
>
> **If the extractor emits counts but NO `evidence_excerpts`** (an older extractor
> that predates the curation upgrade): you still have the anchor. Do the deep-read
> the honest, bounded way — for each weak sub-signal, open the specific cited
> session/turn the counts point at (targeted, not the whole history) so your
> coaching stays evidence-anchored. Never coach from counts alone unless the user
> chose lite mode (§2.7).

### 2.7 COUNTS-ONLY LITE MODE (for the privacy-paranoid — the user's explicit choice)

Some users want maximum privacy: score me, but read as little of my work as
possible. Honor that with **lite mode** — run the extractor with `--max-excerpts 0`
so it emits **counts only, zero excerpts**, and you score purely from the partition:

```bash
python ../../agentcraft_extract.py --project auto --max-excerpts 0 --out agentcraft-counts.json
```

In lite mode:
- Score every sub-signal from its partition (§4a) exactly as normal — the counts are
  still a real, falsifiable anchor, so OVERALL + tier are still honest numbers.
- **Do NOT open sessions/turns to deep-read.** No curated excerpts exist; do not go
  hand-read the raw history to compensate — that would defeat the user's choice.
- Coaching is **necessarily shallower**: `weak` is the partition ("`closure`
  `applied 4/7`, so 3 completion claims shipped without a captured receipt"), `why`
  and `how` are the general mechanism + fix — but you **cannot** cite a specific
  own-work example, because you did not read one. Say so honestly.
- Set `coverage.confidence:"low"` and
  `measurement_status.note:"lite-mode: scored from counts only, no excerpts read"`.
  This is honest transparency: the user traded coaching depth for reading less.

Lite mode is the floor; the default (curated excerpts) is the coaching product.
Both are 100% local, both are zero-third-party-egress. The only difference is how
much of the user's own work you read to coach them — their explicit call.

### 2.1 Locate the local session history

Claude Code stores session transcripts as **JSONL** (one JSON object per line)
under a per-project directory.

**Store root (this machine):**
```
~/.claude/projects/
```
On Windows this resolves to `C:\Users\<you>\.claude\projects\`. Each subdirectory
is one project; its name is the project's absolute path with separators and dots
flattened to `-` (e.g. `C--Users-<you>-Desktop-myrepo`). Inside, every
`<uuid>.jsonl` is one session.

**Discover, don't assume (adapt to the shell; Windows uses `python`, not python3):**
```bash
ls ~/.claude/projects/                         # project dirs (each = one repo)
ls -t ~/.claude/projects/*/*.jsonl | head -40  # newest sessions across all projects
ls ~/.claude/projects/*/*.jsonl | wc -l        # total sessions (feeds COVERAGE)
ls -lS ~/.claude/projects/<slug>/*.jsonl | head -20  # size (find the load-bearing sessions)
```

**Which sessions (scope):**
- **Default scope = the repo you are currently in** (so P7 discipline + the chat
  evidence describe the SAME project). The extractor's `--project auto` resolves it.
- "all my work" / "global" ⇒ widen to all project dirs (`--project global`).
- **Window:** default last ~30 days OR most-recent ~15 sessions, whichever is
  larger, capped so you can read a representative sample. Record the real
  `from`/`to` in `coverage.window`, and `coverage.task_episodes` (the denominator).

### 2a. Understand the JSONL schema (verified against real Claude Code data)

Each line is one JSON object; the `type` field routes it. Field names vary slightly
by Claude Code version — **inspect first, don't guess.** Observed schema:

| `type` | What it is | Fields you use |
|--------|------------|----------------|
| `user` | A human turn | `message.content` (str **or** list of blocks), `timestamp`, `cwd`, `gitBranch`, `sessionId`, `isMeta` |
| `assistant` | An agent turn | `message.content` = list of blocks (`thinking`, `text`, `tool_use`), `message.usage` (token economy), `message.model` |
| `attachment` | Injected context (file reads etc.) | `attachment` payload |
| `system` | System notices | `subtype`, `messageCount` |
| `summary` | Rolled-up prior context (compaction marker) | `summary` text |
| `mode` / `permission-mode` | session mode markers | `mode`, `permissionMode` |
| `ai-title` / `last-prompt` / `queue-operation` / `file-history-snapshot` | metadata | — |

**Content blocks inside `message.content` (list form):**
- `text` — natural language.
- `thinking` — extended-thinking (assistant only).
- `tool_use` — `{name, input}` — **the richest behavioral signal.** Names seen in
  the wild: `Bash, Edit, Write, Read, Grep, Glob, Task/Agent, TaskCreate,
  TaskUpdate, TaskStop, WebSearch, WebFetch, ToolSearch, AskUserQuestion,
  NotebookEdit`, plus `mcp__*` tools.
- `tool_result` — inside a `user` turn: the output of a prior `tool_use`
  (compile/test/exit-code evidence lives here — read it for P5 `verified_outcome`).

> `user` turns whose text starts with `<local-command-caveat>` or that carry
> `isMeta: true` are **plumbing, not real prompts** — exclude them from
> prompt-quality scoring (they would otherwise deflate P1/P2 unfairly).

**Parse defensively:** wrap `json.loads` per line in try/except; `message.content`
may be a bare string. Never assume a key exists.

```bash
# Keys present per line (sanity-check the schema on THIS machine's version):
head -3 "<one>.jsonl" | python -c "import sys,json; [print(sorted(json.loads(l).keys())) for l in sys.stdin if l.strip()]"

# Tool-name histogram for one session (fast behavioral fingerprint):
python -c "import sys,json,collections;c=collections.Counter();\
[c.update(b.get('name') for b in (json.loads(l).get('message',{}).get('content') or []) if isinstance(b,dict) and b.get('type')=='tool_use') for l in open(sys.argv[1],encoding='utf-8') if l.strip()];\
print(c.most_common(20))" "<one>.jsonl"
```

### 2b. Read LARGE sessions properly (DEPTH — do not under-read)

Heavy engineering is often **delegated to subagents**; their `tool_use` /
`tool_result` blocks live in **sidechains** (Task/Agent spawns + nested turns), not
only the main thread. Read main-thread text only and P3 (execution) + P5
(verification) get under-scored — the actual inspect→edit and compile/test evidence
is inside the sidechains. **You must sample them** (the extractor follows sidechains
automatically; this is the manual fallback).

Strategy for a large or multi-session window:
1. **Stream, don't slurp.** Iterate JSONL line-by-line (generator); files can be
   tens of MB.
2. **Sample by structure, not head/tail.** Walk the whole file, retain only
   signal-bearing blocks: every `tool_use` (name + `file_path`/`command`/`pattern`/
   `subagent_type`/`prompt`), every `tool_result` first/last line (exit code,
   PASS/FAIL, error), every real `user`/`assistant` `text`. Drop `thinking` bulk
   (keep only its presence), drop attachment bodies.
3. **Follow the sidechains.** A `Task`/`Agent` `tool_use` ⇒ treat the spawned
   agent's turns as an **episode of their own**; extract the same signals. The
   matching `tool_result` (the agent's return) usually holds the verification
   receipt / root-cause statement — read it.
4. **Budget the read.** Too big to read fully ⇒ read the **N largest** sessions in
   full (they hold the load-bearing work) plus a spread of recent smaller ones, and
   set `coverage.sub_sampled:true` + a `measurement_status.note`. Honest partial
   coverage beats a confident guess — but do not settle for main-thread-only when
   sidechains are present and readable.

Practical streaming extractor (adapt paths; pure-local, stdlib only) — use as a
manual **cross-check** on the shipped extractor's counts:
```bash
python -c "
import sys, json
def blocks(line):
    try: o=json.loads(line)
    except Exception: return None,[]
    t=o.get('type'); m=o.get('message') or {}
    c=m.get('content')
    if isinstance(c,str): c=[{'type':'text','text':c}]
    return t,(c or [])
for path in sys.argv[1:]:
    tools=[]; verifs=0; reads_before_edit=0; edits=0; last_paths=set()
    for line in open(path,encoding='utf-8',errors='replace'):
        t,cs=blocks(line)
        for b in cs:
            if not isinstance(b,dict): continue
            if b.get('type')=='tool_use':
                n=b.get('name'); inp=b.get('input') or {}
                tools.append(n)
                if n in ('Read','Grep','Glob'):
                    fp=inp.get('file_path') or inp.get('path') or inp.get('pattern')
                    if fp: last_paths.add(str(fp))
                if n in ('Edit','Write'):
                    edits+=1
                    fp=inp.get('file_path')
                    if fp and str(fp) in last_paths: reads_before_edit+=1
                if n=='Bash':
                    cmd=(inp.get('command') or '').lower()
                    if any(k in cmd for k in ('test','pytest','tsc','py_compile','--check','node --check','build','lint')):
                        verifs+=1
    print(path.split('/')[-1][:12], 'tools=',len(tools),'edits=',edits,'read_before_edit=',reads_before_edit,'verify_runs=',verifs)
" ~/.claude/projects/<slug>/*.jsonl
```

**If there is little or no history:** do NOT fabricate. Set `coverage.confidence`
to `"low"`, keep the window honest, mark thin pillars/sub-signals `unmeasured` with
a `limitations` code (§4b), and say so plainly. A small, honest read beats a
confident fiction.

### 2b.1 CURATED-EVIDENCE DEEP-READ — the coach's eyes (JUDGE-FROM-CURATED-EVIDENCE)

This is the depth move that makes AGENTCRAFT a real coach instead of a number-spitter — and
the discipline that keeps it private + cheap. **You judge FROM the curated evidence
excerpts, NOT from a re-read of the raw multi-GB history.**

**The protocol:**
1. **For every weak sub-signal** (any with `missed > 0`), open its list under
   `evidence_excerpts` and **DEEP-READ the curated excerpts** — the specific,
   redacted turns that actually drove the miss. This is where you SEE the work: the
   blind edit that skipped a Read, the "done" claim with no captured receipt, the
   symptom-patch with no root-cause line. Reading the user's work to coach them is
   **required** — a coach must see the work — and the curation is exactly what keeps
   that reading bounded (the relevant slices) and redacted (no secrets/paths/bodies).
2. **Turn each weak pillar's excerpts into rich coaching** (§6): explain **WHAT** the
   user did (from the excerpt), **HOW** they work (the pattern across excerpts),
   **WHERE + WHY** they're weak (which sub-signal, and the cost it causes), **HOW** to
   fix it — with an `example` **lifted from their OWN curated excerpt**, not a generic
   template — and **what to retest**. The counts pin the number; the excerpts give it
   a face.
3. **When a curated excerpt is genuinely ambiguous**, you MAY open the ONE specific
   cited session/turn it points at (`session` + `episode_idx`/`ts`) to disambiguate —
   **bounded + targeted**, a single referenced turn, never the whole history. Prefer
   the curated paraphrase; only reach past it when you truly cannot coach without the
   detail.

**The hard privacy + cost line (do NOT cross it):**
- **Do NOT slurp the raw multi-GB session history into your context to "read
  everything."** That is the total-dump tragedy — it explodes cost AND needlessly
  exposes the user's entire work when the curated slices already carry the signal.
  The extractor pre-digested the history on disk *precisely so you don't have to*.
- The excerpts are already redacted (basenames not paths, paraphrases not verbatim
  bodies, secret-shaped strings dropped). Keep it that way: if you open a cited turn
  and it contains a secret, a `.env`, or a raw key — do NOT quote it. Coach around it.
- Bounded read = curated excerpts + at most a few targeted cited turns for ambiguity.
  That is the entire reading budget. Depth WITHOUT the total dump — that is the whole
  resolution.

**Lite mode exception (§2.7):** if the user chose `--max-excerpts 0`, there are no
excerpts and you do NOT open turns to compensate — you coach from counts alone,
honestly shallower, because that is what they asked for.

---

## 3. STEP 2 — Read the repo discipline surface (MANDATORY — this is the moat)

This is what chat-only tools (MEGA) cannot see, and it powers **P7** plus the
**fairness rule** across P1/P2/P4/P5. The discipline surface is the `configuration`
capability (§4c) — it is **always observable from disk**, independent of chat
volume. Inventory the repo being assessed:

```bash
# Standing rules (root + .claude + nested):
ls -a                          # look for CLAUDE.md, AGENTS.md
find . -name "CLAUDE.md" -not -path "*/node_modules/*" 2>/dev/null
cat ./CLAUDE.md ./.claude/CLAUDE.md 2>/dev/null

# Encoded runbooks / skills:
ls -R .claude/skills 2>/dev/null

# Hooks & gates (harness-enforced automation):
cat .claude/settings.json .claude/settings.local.json 2>/dev/null   # look for "hooks"
ls .git/hooks 2>/dev/null | grep -v sample                          # active git hooks
ls .github/workflows 2>/dev/null                                    # CI gates

# Memory & continuity artifacts (also feeds P6):
find . -maxdepth 3 \( -iname "MEMORY.md" -o -iname "SESSION_HANDOFF*.md" \
  -o -iname "*ADR*.md" -o -ipath "*decisions*" -o -ipath "*memory*" \) \
  -not -path "*/node_modules/*" 2>/dev/null
```

Record concretely: which artifacts **exist**, what discipline they **encode**
(e.g. "verify gates: compile-check before ship", ">100 LOC ⇒ spawn subagent",
"never delete data"), and whether the chat shows the agent **honored** them.

**Fairness anchor (load-bearing, SPEC §4):** if a discipline is encoded in files,
the user gets **credit** for it **even if they did not re-type it in each prompt.**
Encoding rigor into the system is the **higher** skill. Do NOT reward per-prompt
re-pasting over automation — that is exactly MEGA's blind spot, and inverting it is
AGENTCRAFT's core fairness fix. A high P7 with sparse per-prompt repetition is a
**strength**, not a gap. In the partition (§4a), an encoded-and-honored discipline
counts as `applied`; a correct absence of a rule that isn't needed counts as
`declined` (positive), never `missed`.

---

## 4. STEP 3 — Score the 7 pillars via the PARTITION over sub-signals (0–100 each)

Follow `../../RUBRIC.md` for per-pillar Strong/Weak language, `../../SPEC.md` §1
(eligibility), §1b (the sub-signal indicator table), §1c (the partition), §1d
(measurement_status), §2c (capability-gating), §2d (containment). **This section is
the depth engine:** every pillar decomposes into named sub-signals, every sub-signal
is scored as a **partition of episodes**, and the 0–100 number is **derived from the
counts** — never a gut read.

### 4a. The partition (score is DERIVED — SPEC §1c)

For **each sub-signal**, over the episodes where the behaviour *could* apply:

```
eligible = applied + declined + missed        (a strict partition — they sum exactly)
verified_outcome <= applied                    (of the applied, how many were independently confirmed)
```

- **`applied`** — episodes where the developer **did** the good behaviour.
- **`declined`** — episodes where **correctly NOT doing it** is the good call
  (declined a bad option / correctly chose not to delegate / re-scoped a bad task /
  a rule wasn't needed). **`declined` counts POSITIVE** — it is credit
  (credit-positive rule), NOT a miss. AGENTCRAFT is not a gotcha-hunter.
- **`missed`** — episodes where the behaviour was warranted but absent (the ONLY
  negative bucket).
- **`verified_outcome`** — subset of `applied` independently confirmed (a check
  ran, output inspected, a failure made to stop recurring). Surfaces
  prove-don't-declare *per behaviour*; feeds the card's "% VERIFIED" stat.

**Derive the score (do not invent it):**
```
credit_rate = (applied + declined) / eligible        # declined counts positive
base        = round(100 * credit_rate)
# band-nudge base onto the observed anchor tier (weak/developing/strong/elite)
#   from the §4d catalog, so a rate and an anchor can't disagree.
# verified_outcome informs the card's %-VERIFIED and can CAP an inflated 'elite'
#   when applied were never independently checked (prove-don't-declare) — it does
#   NOT double-penalize.
score = band_nudge(base, anchor_tier, verified_outcome, applied)
```
Band scale: `0–39 weak · 40–64 developing · 65–84 strong · 85–100 elite`.

**Pillar score** = the average of its **measured** sub-signal scores (weighted where
a pillar's method says so, §4d). The pillar's `partition` block is the **roll-up
(sum) over its measured sub-signals** — this is the containment parent (§4e). This
keeps the OVERALL formula + weights **unchanged** — the partition is the *reason*
for the number, not a new number.

### 4b. measurement_status + limitations (honest-empty, structural — SPEC §1d)

Every sub-signal (and pillar) carries `measurement_status`:
- **`measured`** — `eligible >= 3` (`config.measurement_threshold`, default 3).
  Real 0–100 `score`; `limitations: null`.
- **`unmeasured`** — `eligible <= 2`. `score: null`, and a **`limitations`** code
  MUST name *why*. Unmeasured is honest — the opposite of fabricating a number.

`limitations` closed set (pick the precise one):
| code | when |
|---|---|
| `no-opportunity` | `eligible == 0` — the behaviour never had a chance (e.g. no delegation happened ⇒ P4 sub-signals had nothing to score). |
| `below-threshold` | `eligible ∈ {1,2}` — it appeared, too few times to trust a rate. |
| `extraction-gap` | the depended-on capability was **gated out** for this window (§4c) — the harness could not record it ⇒ `unmeasured`, **never a low score** (the fairness fix). |
| `narrow-window` | the coverage window was too short/narrow for this signal to accumulate. |
| `retention-window-bounded` | evidence predates the retained session history (older sessions rolled off disk). |
| `harness-capability-missing` | this Claude Code version doesn't emit the field the signal needs (schema gap), distinct from the behaviour simply not occurring. |

A **measured pillar** requires ≥1 measured sub-signal. If ALL a pillar's sub-signals
are unmeasured ⇒ the pillar is `unmeasured` → set `eligible:false`, `score:null`,
`measurement_status:"unmeasured"`, `limitations:"<code>"`, **excluded from OVERALL**
(exact v1 eligibility semantics + a reason). P7 is a special case: the
`configuration` capability is read from disk, so P7 is essentially always measurable
— an empty discipline surface is an honest LOW score (`missed`), not `unmeasured`.

### 4c. Capability-gating (fairness — SPEC §2c: never score-low what can't be shown)

Each sub-signal declares a depended-on **capability**. For the window, classify each
capability `observable` / `partial` / `gated_out`, and record it in the top-level
`capability_gating` block:

| capability | records | default | if gated_out |
|---|---|---|---|
| `message` | user/assistant text | observable | rare (base signal) |
| `retrieval` | Read/Grep/Glob + results | observable | anchoring/inspect sub-signals → extraction-gap |
| `mutation` | Edit/Write + results | observable | execution sub-signals → extraction-gap |
| `verification` | Bash test/compile/lint + exit codes | observable/partial | if receipts live only in un-sampled sidechains ⇒ partial |
| `delegation` | Task/Agent/TaskCreate spawns+returns | observable | **gated_out when no delegation happened at all** ⇒ P4 sub-signals `no-opportunity`/`extraction-gap` |
| `configuration` | repo discipline surface (from disk) | observable | powers P6/P7; independent of chat volume |
| `attachment` | injected file-read context | observable | supports anchoring/economy |
| `compaction` | `summary`/compaction markers | **partial** | lossy ⇒ `session_boundary_awareness`, `cross_session_inheritance` scored conservatively |
| `branch` | conversation branches/re-runs | **partial** | recorded unevenly by version ⇒ treat cautiously |

**Gating rule (fairness anchor):** if a sub-signal's capability is `gated_out`, OR
the specific evidence is absent under a `partial` capability, mark that sub-signal
`unmeasured` + `limitations:"extraction-gap"` — it is **excluded from the pillar
average**, **NOT scored 0**. This is the difference between "you didn't do it" and
"we couldn't see it." Never conflate them.

### 4d. Procedure per pillar

1. **Classify capability.** Any depended-on capability gated_out ⇒ mark those
   sub-signals `unmeasured` + `extraction-gap` up front (§4c).
2. **Partition each measurable sub-signal** from the extractor counts (§4a):
   `applied`/`declined`/`missed`/`verified_outcome`, derive `score`, set
   `measurement_status` + `limitations` per §4b.
3. **Roll up the pillar partition** (sum over measured sub-signals) and compute the
   pillar `score` (average of measured sub-signal scores; weighted where noted).
4. **Attach ≥1 `evidence` item per graded pillar and per measured sub-signal** — a
   concrete pointer: `{ "session":"<uuid-or-short>", "turn":<n>, "note":"<what you
   saw>" }` or a file path (`{"session":"repo","turn":0,...}`) for repo-derived
   evidence. **prove-don't-declare: no evidence ⇒ do not inflate.** If you cannot
   point to it, you cannot claim it.
5. **Verify containment** (§4e) before moving on.

**Global counting rules (be rigorous, not vibes):**
- **Episode** = a coherent task span (initiation → work → outcome/abandon).
  `coverage.task_episodes` is THE denominator + hard upper bound for every
  sub-signal's `eligible`.
- **Decision point** = a turn where a choice is made. **Completion claim** = any
  "done / works / fixed / passing" assertion; P5 = fraction with independent, closed,
  falsifiable verification (that's `verified_outcome` on the P5 sub-signals).
- **Sidechain-aware:** for P3/P4/P5, the strongest signal often lives in subagent
  returns (§2b). Read them; if you genuinely couldn't, mark those sub-signals
  `partial`/`extraction-gap`, don't infer high scores you didn't observe.

### 4d.1 SUB-SIGNAL INDICATOR CATALOG (band anchors + partition-counting rules)

> Canonical index of *what is observed* = SPEC §1b (with `Capability` + `Trait`
> columns). Below is the **band-anchor prose + the partition-counting rule** for
> each sub-signal — how to fill `applied`/`declined`/`missed`/`verified_outcome`.
> The two moat pillars (P6/P7) keep the **fairness framing**: encoded/automated
> discipline scores *up*; re-typing does not. 🛡️MOAT = MEGA-blind. ➕NEW = added in v2.

#### P1 — INTENT & FRAMING  *(weight toward `acceptance_defined`)* — capability: `message`
- **`goal_clarity`** (T01) — desired outcome stated unambiguously?
  - *Count:* per task-initiating episode — `applied` if the initiating turn names a
    concrete outcome/artifact + bounded scope; `declined` if the user correctly
    re-scopes/declines a bad ask; `missed` if "fix it"/no object.
  - *Anchors:* weak = "make it better" / no object · developing = goal, fuzzy scope
    · strong = goal + bounded scope · elite = goal + scope + explicit non-goals.
- **`problem_framing`** (T02) — problem-level vs premature fixed solution?
  - *Count:* `applied` = states symptom/need & lets agent choose approach, OR asks a
    genuine clarifying question (`AskUserQuestion` / "X or Y?"); `declined` = solution
    was correctly dictated because it was truly the only option; `missed` = solution
    forced before the problem is understood.
  - *Anchors:* weak = solution dictated blind · developing = problem stated, one
    solution assumed · strong = problem-level + open approach · elite = trade-offs
    surfaced before committing.
- **`acceptance_defined`** (T06) — a falsifiable "done when ___" per task?
  - *Count:* `applied` = a checkable success test in the prompt ("done when tests
    green", "verify with `tsc`", "returns 200"); `missed` = none; `declined` rarely
    applies. `verified_outcome` = the acceptance was actually exercised later (ties
    to P5).
  - *Anchors:* weak = none · developing = vague "make it work" · strong = one
    falsifiable criterion · elite = falsifiable + measurable per subtask.
- **`constraint_precision`** ➕NEW (T05) — real constraints/non-goals named precisely?
  - *Count:* `applied` = prompt names concrete constraints ("don't touch X", perf
    budget, stack, deadline); `declined` = no constraint applied and none was needed;
    `missed` = an obvious constraint went unstated and caused drift.
  - *Anchors:* weak = no constraints, agent guesses · developing = vague ("keep it
    clean") · strong = concrete constraints + non-goals · elite = constraints +
    trade-off priority ("prefer clarity over speed here").
- *Method:* average the four, weighted toward `acceptance_defined` (hardest, most
  predictive). Credit declining/re-scoping a bad task as `declined` (positive).

#### P2 — CONTEXT & GROUNDING  *(penalized by re-paste; economy is a first-class win)*
- **`artifact_anchoring`** (T04, `retrieval`) — grounded in real files/paths/outputs?
  - *Count:* per decision point — `applied` = cites `path:line`, a pasted
    error/stacktrace, a test name, a real output; `missed` = "the code" in the
    abstract / from memory.
  - *Anchors:* weak = from-memory · developing = names files, no specifics · strong =
    path + actual error/output · elite = path:line + exact failing output + relevant
    prior result.
- **`evidence_at_decisions`** (T09, `retrieval`) — evidence present where a choice is made?
  - *Count:* `applied` = the deciding turn carries the justifying data (a referenced
    `tool_result`, a measured number); `missed` = choice asserted.
  - *Anchors:* weak = choices asserted · developing = evidence nearby not at the
    decision · strong = evidence at the decision · elite = evidence + why the
    alternative was rejected.
- **`progressive_disclosure`** ➕NEW (T10, `message`) — context fed WHEN needed, staged?
  - *Count:* `applied` = the agent is handed the next artifact at the decision point
    (staged); `declined` = a single upfront dump was genuinely the right call for a
    tiny task; `missed` = one giant dump when staging was warranted, or context
    withheld until the agent was already stuck.
  - *Anchors:* weak = giant upfront dump or starves the agent · developing = some
    staging · strong = context arrives at the decision point · elite = deliberately
    sequences context to the work.
- **`context_economy`** (T11, `configuration`) — inverse of redundant re-paste?
  - *Count:* `applied` = low re-paste; leans on encoded config/prior context; healthy
    `usage.cache_read` vs `cache_creation`; `missed` = same big blocks re-pasted each
    turn. **Re-paste ratio = duplicated context blocks / total context blocks.**
  - *Anchors:* weak = re-pastes every turn · developing = some re-paste · strong =
    tight, reuses state · elite = near-zero re-paste + leans on CLAUDE.md/skills so
    rules aren't retyped (the fairness win).
- **`agent_state_awareness`** (T03, `message`) — avoids re-sending what the agent has?
  - *Count:* `applied` = references "the file you just read"/"as established"; builds
    on a prior `tool_result`; `missed` = re-explains from scratch.
  - *Anchors:* weak = re-explains from scratch · developing = occasional awareness ·
    strong = consistently builds on held state · elite = deliberately manages the
    context window.
- **`session_boundary_awareness`** ➕NEW (T03, `compaction` — often `partial`) —
  tracks what survives compaction/new session?
  - *Count (conservative when compaction is partial):* `applied` = after a `summary`/
    new session, re-primes only what was lost (doesn't re-dump everything); `missed` =
    re-dumps the whole context or loses a decision that was in scope. If the compacted
    span hides the detail ⇒ mark `unmeasured` + `extraction-gap`.
  - *Anchors:* weak = re-dumps or loses decisions · developing = partial re-priming ·
    strong = re-primes only the lost pieces · elite = manages the boundary
    deliberately (writes a handoff before compaction).
- *Method:* fraction of decision points with fresh artifact evidence, penalized by
  measured re-paste ratio. Leaning on encoded config = credit (`declined`/`applied`),
  never a gap (fairness rule).

#### P3 — EXECUTION & DIAGNOSIS  *(read sidechains — §2b)*
- **`understand_before_build`** (T07, `retrieval`+`mutation`) — inspection precedes mutation?
  - *Count:* per build/fix episode — `applied` = a `Read`/`Grep`/`Glob` (or repro)
    precedes the first `Edit`/`Write` and the plan references what was read; `missed` =
    builds blind.
  - *Anchors:* weak = builds blind · developing = reads some · strong = reads/greps
    the target before editing · elite = reads + states an understanding first.
- **`root_cause_depth`** (T08, `mutation`) — fixes address cause not symptom?
  - *Count:* `applied` = explicit **"Root cause:"** statement, bug reproduced, fix
    targets cause; `verified_outcome` = a guard/test was added so it can't recur;
    `missed` = patches first visible symptom.
  - *Anchors:* weak = patches symptom · developing = partial cause · strong = cause
    named + fixed · elite = cause named, reproduced, guarded against recurrence.
- **`inspect_before_edit`** (T13, `mutation`) — files examined before change? **(most countable)**
  - *Count:* the extractor's `read_before_edit / edits` directly — `applied` = an
    `Edit`/`Write` preceded by a `Read`/`Grep` on the **same path**; `missed` = an
    edit with no prior inspection of that path.
  - *Anchors (ratio):* weak = <0.3 · developing = 0.3–0.6 · strong = 0.6–0.85 · elite
    = >0.85 (edits are essentially always preceded by inspection).
- **`capability_provisioning`** ➕NEW (T14, `configuration`+`delegation`) — equips the agent before asking?
  - *Count:* `applied` = before delegating/asking, the user grants the right tools/
    MCP, points at the right skill, sets scope; `declined` = the agent already had
    what it needed, so no provisioning was required; `missed` = expects blind success
    from an under-equipped agent, then fails.
  - *Anchors:* weak = throws work at an unequipped agent · developing = some setup ·
    strong = equips tools/scope before delegating · elite = provisions + verifies the
    agent can actually reach what it needs.
- **`feedback_specificity`** ➕NEW (T21, `message`) — corrections specific + actionable?
  - *Count:* per correction turn — `applied` = specific + actionable ("wrong: it
    drops nulls; do X"); `missed` = vague ("nope, try again"). No-correction episodes
    aren't eligible (`no-opportunity` if the whole window had none).
  - *Anchors:* weak = "that's wrong" with no direction · developing = points at the
    area · strong = names the exact defect + the fix · elite = defect + fix + why, so
    the agent generalizes.
- *Method:* per episode, score the inspect→diagnose→fix ordering; average across
  episodes. When work is delegated, score the **sidechain** ordering, not the main
  thread's silence.

#### P4 — ORCHESTRATION  *(both delegate AND correctly-don't-delegate credited)* — capability: `delegation`
> If NO delegation happened in the whole window, `delegation` is `gated_out`: score
> `delegation_judgment` alone on the correct "do it inline" calls (those are
> `declined` = positive); mark the rest `unmeasured` + `no-opportunity`. A user who
> correctly never needed to delegate is not penalized.
- **`delegation_judgment`** (T15) — right call on delegate vs inline (both directions)?
  - *Count:* `applied` = big/parallel work delegated (`Task`/`Agent`); `declined` = a
    correct "this is small, do it inline"; `missed` = hoards big work OR delegates
    trivia.
  - *Anchors:* weak = hoards or delegates trivia · developing = mixed · strong =
    mostly right · elite = consistently right + explicit reasoning about when to split.
- **`decomposition`** (T16) — task broken into coherent, sized units?
  - *Count:* `applied` = work split into waves/subtasks (`TaskCreate`), each
    independently completable; `missed` = one giant vague ask.
  - *Anchors:* weak = one giant ask · developing = rough split · strong = coherent
    sized units · elite = units sized to be independently verifiable.
- **`brief_quality`** (T17) — briefs carry goal + context + acceptance?
  - *Count:* `applied` = the `Task`/`Agent` `prompt` states goal + files/context +
    "done when"; encoded brief templates (e.g. a 5-pillar spawn template in CLAUDE.md)
    count as standing brief quality (fairness → `applied`); `missed` = "go build X".
  - *Anchors:* weak = "go build X" · developing = goal only · strong = goal + context
    + acceptance · elite = that + verification instruction + scope guard.
- **`parallelism_hygiene`** (T19) — parallel work independent / non-colliding?
  - *Count:* `applied` = parallel spawns touch disjoint files + a separate verifier
    (audytor ≠ budowniczy); `declined` = correctly ran sequentially to avoid a
    collision; `missed` = colliding parallel edits.
  - *Anchors:* weak = colliding edits · developing = some overlap · strong = disjoint
    work · elite = disjoint + independent verification lane.
- **`result_integration`** (T20, `delegation`+`verification`) — sub-results verified, not blindly accepted?
  - *Count:* `applied` = after a return, the main thread inspects/verifies before
    accepting and echoes the return's evidence; `missed` = blindly accepts.
    `verified_outcome` = an independent check ran on the merged result.
  - *Anchors:* weak = blindly accepts · developing = skims · strong = verifies before
    merge · elite = verifies + reconciles conflicts + records.
- **`decision_rights`** ➕NEW (T18, `delegation`+`message`) — authority allocated correctly?
  - *Count:* `applied` = agent decides reversible/local calls autonomously while the
    user reserves the irreversible ones (deploy/spend/delete); `declined` = correctly
    kept a call human because it was irreversible; `missed` = micromanages reversible
    calls OR lets the agent make an irreversible one unsupervised.
  - *Anchors:* weak = all-or-nothing (micromanage or blind-trust) · developing =
    inconsistent · strong = reversible→agent, irreversible→human · elite = explicit,
    encoded decision-rights (e.g. a CLAUDE.md rule that deploy/spend stays human).
- *Method:* average over orchestration episodes; if no delegation occurred but the
  task genuinely didn't need it, score on `delegation_judgment` alone.

#### P5 — VERIFICATION  *(the receipt must exist and be independent)* — capability: `verification`
- **`independent_channel`** (T23) — verified via a channel distinct from the producer?
  - *Count:* `applied` = after `Edit`/`Write`, a `Bash` test/compile/lint run (or a
    local HTTP-status probe), a re-`Read`, or a `tool_result` with an exit code /
    PASS-FAIL — **not** "the agent said it works"; `missed` = "trust me".
    `verified_outcome` = the check actually passed/failed with a captured result.
    (These are the *user's own local* verify commands read from history — AGENTCRAFT never
    runs a network call itself; the only thing you write is the local report.)
  - *Anchors:* weak = "trust me / looks right" · developing = manual eyeball · strong
    = an independent run/test on most changes · elite = on essentially every change,
    incl. delegated work.
- **`closure`** (T23) — verification actually completed, not just intended?
  - *Count:* `applied` = the verify run has a captured result (exit 0 / "26/26 PASS"
    / 0 errors) in a `tool_result`; `missed` = "let's run the tests" with no output.
  - *Anchors:* weak = intended, never closed · developing = closed sometimes · strong
    = closed for most claims · elite = every completion claim carries a pasted receipt.
- **`falsifiable_acceptance`** (T06) — the accept test could have failed and would show it?
  - *Count:* `applied` = a real pass/fail (test suite / type-check / HTTP status),
    tied to the stated "done when"; `missed` = a tautology check that can't fail.
  - *Anchors:* weak = can't-fail check · developing = weak check · strong = genuine
    pass/fail gate · elite = falsifiable + tied to the up-front acceptance.
- **`steering_calibration`** ➕NEW (T22, `message`+`verification`) — trust calibrated to evidence?
  - *Count:* `applied` = tightens the loop after a miss, loosens after verified wins;
    `declined` = correctly stayed hands-off because the track record justified it;
    `missed` = blind-trust after failures OR micromanage after proven wins.
  - *Anchors:* weak = fixed stance regardless of evidence · developing = reacts
    slowly · strong = adjusts trust to results · elite = deliberate, explicit
    calibration ("you've been solid here, I'll batch-review").
- *Method:* fraction of completion claims that received **independent, closed,
  falsifiable** verification. Count receipts in sidechains too (§2b); if a claim's
  proof lives only in a sub-thread and never surfaces, that's a real closure `missed`
  (coach it, §6) — not an `extraction-gap` if you *could* have read the sidechain.

#### P6 — MEMORY & CONTINUITY  **[MEGA-BLIND — moat · fairness framing]** — capability: `configuration`
- **`decision_persistence`** (T12) — decisions written somewhere durable?
  - *Count:* `applied` per episode whose decisions were persisted (handoff, ADR,
    `MEMORY.md`, a memory-store/`*_remember*` script); `missed` = decision made,
    nothing persisted.
  - *Anchors:* weak = nothing persisted · developing = ad-hoc notes · strong =
    systematic handoff/ADR · elite = automated dual-write to a durable store.
- **`cross_session_inheritance`** 🛡️MOAT (`configuration`+`compaction`) — later sessions use earlier knowledge?
  - *Count:* `applied` = a later turn references an earlier decision, a session-start
    recall/handoff read at boot; `missed` = every session starts blind. Compaction
    partial ⇒ score conservatively.
  - *Anchors:* weak = starts blind · developing = occasional reference · strong =
    consistent inheritance · elite = automated recall at session start (the machine
    inherits, not just the human).
- **`mistake_nonrepetition`** (T24, `message`+`mutation`) — a past mistake recorded and NOT repeated?
  - *Count:* `applied` = a BUG_FIX/LESSON exists AND the same error does not recur;
    `missed` = the same mistake recurs across sessions (recurrence = the negative).
  - *Anchors:* weak = same mistake repeats · developing = recorded but sometimes
    repeats · strong = recorded and avoided · elite = recorded, avoided, and encoded
    into a guard/gate so it *can't* repeat.
- **`rationale_recorded`** ➕NEW (T12, `configuration`) — persisted decisions carry the WHY + provenance?
  - *Count:* `applied` = a persisted decision records *why* + which session/file (an
    ADR-shaped record); `missed` = only the *what* was saved, no reasoning.
  - *Anchors:* weak = no rationale · developing = terse note · strong = why + context
    · elite = why + provenance + alternatives-rejected (a real ADR).
- **`recovery_discipline`** ➕NEW (T24, `mutation`+`verification`) — failures turned into durable guards?
  - *Count:* `applied` = after a failure, a distinct recover→diagnose→guard sequence
    (the loss becomes a guard/test), not just a blind retry; `verified_outcome` = the
    guard was verified; `missed` = retried without diagnosing.
  - *Anchors:* weak = blind retry · developing = diagnoses but no guard · strong =
    recover + diagnose + guard · elite = the guard is encoded so the class of failure
    can't recur.
- *Method:* evidence of durable memory + ≥1 demonstrated inheritance/non-repetition;
  scale by how *systematically* it happens. **Eligible-when:** window spans ≥2
  sessions OR a memory artifact exists. *Fairness:* automated cross-session memory
  scores *up* — the single-chat scorers are blind to it; that's the moat.

#### P7 — SYSTEM-DISCIPLINE  **[MEGA-BLIND — moat · fairness framing]** — capability: `configuration` (from disk)
- **`discipline_encoded`** 🛡️MOAT — standing conventions live in files, not the user's head?
  - *Count:* `applied` scaled by files + lines of encoded standing rules (`CLAUDE.md`
    root/.claude/nested, `AGENTS.md`, `.claude/skills/**`); `missed` = no standing
    convention.
  - *Anchors:* weak = none · developing = a thin README rule · strong = a real
    CLAUDE.md of conventions · elite = layered CLAUDE.md + skills + explicit
    gates/hooks.
- **`config_coverage`** 🛡️MOAT — CLAUDE.md / skills / hooks / gates exist & used?
  - *Count:* `applied` = `.claude/settings*.json` hooks / git hooks / CI / memory
    scripts present **and** sessions follow them (encoded gate → observed behavior);
    `missed` = config absent or ignored.
  - *Anchors:* weak = absent/ignored · developing = exists, partly followed · strong =
    exists and honored · elite = broad automation (hooks + CI + memory) consistently
    honored.
- **`automation_vs_retyping`** 🛡️MOAT — repeated instructions automated, not re-pasted?
  - *Count:* `applied` = rules that would be retyped each prompt live in
    config/skills/hooks; sparse per-prompt repetition + dense encoded config = the
    **fairness win** (`applied`); `missed` = re-pastes the same rules every prompt.
  - *Anchors:* weak = re-pastes rules every prompt (or has none) · developing = some
    automation · strong = most repetition automated · elite = nearly all standing
    discipline automated; prompts stay terse *because* the system carries it.
- *Method:* inventory the repo discipline surface; score by **breadth + depth of
  encoded discipline** and evidence the agent honored it. **Always measurable** (the
  `configuration` capability reads from disk) — an empty discipline surface is an
  honest LOW score (`missed`), not `unmeasured`. Apply the fairness anchor: do NOT
  reward per-prompt re-typing over automation.

### 4e. Containment consistency (SPEC §2d — the renderer validates this fail-loud)

Before you finalize, verify these hold — the renderer raises (exit 2) if they don't:
1. **Component-wise containment.** For every sub-signal `s` under pillar `P`, each of
   `{eligible, applied, declined, missed, verified_outcome}` for `s` is `<=` the
   pillar `P`'s corresponding roll-up. (Because the pillar `partition` is the SUM
   over its measured sub-signals, this holds by construction — check it anyway.)
2. **Partition holds at both levels.** `eligible == applied + declined + missed` for
   every sub-signal AND every pillar roll-up.
3. **Verification bound.** `verified_outcome <= applied` everywhere.
4. **Measurement containment.** A `measured` sub-signal requires a `measured` pillar;
   an `unmeasured` pillar has only `unmeasured` sub-signals.
5. **Episode ceiling.** No pillar's `partition.eligible` exceeds
   `coverage.task_episodes`.

If any fails, your counts are inconsistent — fix them, don't ship a fabricated-
consistent card.

---

## 5. STEP 4 — Meta-metrics + descriptive/synthesis blocks (shown, NOT graded)

### 5a. Meta-metrics (context — never folded into OVERALL; emit these exact JSON keys)
- **`outcome_rate`** — `{ "pct":<0-100>, "completed":<n>, "attempted":<n> }`. A task
  "completed" when it reached its stated "done when X".
- **`efficiency`** — `{ "index":<0-100>, "turns_per_outcome":<float>,
  "rework_ratio":<0-1>, "context_reuse":<0-1> }`. `rework_ratio` = redo/revert work
  ÷ total; `context_reuse` = prior context reused vs re-pasted (higher better —
  derivable from the `usage` cache signal, §2a). `index` = your compact roll-up.
- **`verified_rate`** — `{ "pct":<0-100>, "verified":<n>, "applied":<n> }` = the
  card's "% VERIFIED" stat = total `verified_outcome` ÷ total `applied` across
  sub-signals. This is prove-don't-declare rolled up to a headline.
- **`coverage`** — `{ "sessions":<n>, "episodes":<n>, "task_episodes":<n>,
  "distinct_active_days":<n>, "task_classes_covered":<0-9>, "window":{from,to},
  "confidence":"low|medium|high", "sub_sampled":<bool> }`. Derive `confidence` from
  volume AND read depth: thin history OR main-thread-only sidechain reads ⇒ `"low"`;
  a solid multi-session window with sidechains sampled ⇒ `"medium"`/`"high"`.

### 5b. Descriptive + synthesis blocks (SPEC §5b — all optional + descriptive)
Never folded into OVERALL. **Omit any block you cannot infer with evidence**
(prove-don't-declare) rather than guessing.
- **`profile`** — inferred, not asked: `{ role, experience, team, goal }`.
- **`style`** — `{ paradigm, typing, testing, architecture, error_handling,
  abstraction }` (free strings, e.g. `typing:"strict type-hints"`).
- **`work_mix`** — count map over 9 kinds summing ~= episode count: `feature`,
  `bugfix`, `refactor`, `debug`, `test`, `docs`, `ops`, `research`, `review`.
  Descriptive — a feature-heavy or bug-heavy mix is never a skill deficit.
- **`collaboration_shape`** — `{ corrections, re_instructions, restarts,
  median_turns, max_concurrency }`. Corrections/restarts are observations, not
  penalties.
- **`trend`** — per-week array `[ { week:"YYYY-Www", overall, P6, P7, ... } ]`. This
  is the block that lets the card **show P6/P7 compounding over weeks** — our whole
  thesis, made visible. Emit only weeks the window actually covers.
- **`practices[]`** — durable habits by area: `{ area:"P5", habit:"…", evidence:[…] }`.
- **`anti_patterns[]`** — recurring costs by area with a **cost token**:
  `{ area:"P3", cost:"rework", observation:"…", evidence:[…] }`,
  `cost ∈ { rework, wasted-context, undetected-defect, manual-toil, stalled-thread }`.
  Brave-honest in both directions — a specific counter-observation beats another
  compliment. Evidence-anchored (no evidence ⇒ do not assert).

---

## 6. STEP 5 — OVERALL, tier, and COACHING

**OVERALL** = weighted mean over **eligible (measured)** pillars only, using the
weights in `config`/SPEC §3, **renormalized** over the eligible set:
```
P1 0.16  P2 0.16  P3 0.15  P4 0.13  P5 0.16  P6 0.12  P7 0.12   (sum = 1.00)
overall.score = round( Σ(w_i · score_i) / Σ(w_i)  over eligible pillars )
```
Copy the (renormalized) weights actually used into the report's `weights` block so
the math is auditable. **This formula + these weights are UNCHANGED from v1** — the
partition is the *reason* for each pillar score, not a new averaging rule.

**Tier** from `overall.score` (SPEC §3 / `config.tier_bands`):
```
85–100 diamond · 75–84 gold · 65–74 silver · 0–64 bronze
```

**COACHING — the differentiator. You are a SKILL-DEVELOPMENT COACH.** AGENTCRAFT does not
tell the user how to tweak their agents, tools, hooks, or infra — it teaches **the
human** how to **level up their own skill** as an AI-coding collaborator. Every weak
pillar becomes **a skill YOU help them develop + a concrete PERSONAL practice they
adopt + WHY building it makes them a stronger collaborator + a behavior for them to
track in themselves next scan.** The habit is **transferable** — it carries to every
codebase, every model, every AI session — and it is something the *human* builds in
*themselves*, not a change to their setup. Warm, second-person, encouraging,
developmental. For **every eligible pillar with `score < config.target`** (default
target = 75, the gold line; let the user override if they name a tier), emit
**exactly one** coaching entry with **all** of these fields:
```
pillar          : "P3"
title           : short human label — a SKILL/HABIT to build (e.g. "Build your
                  read-before-edit reflex"), not a verdict
weak            : specific + evidence-anchored, from THEIR OWN work — name the
                  sub-signal + its partition counts AND what you saw in the curated
                  excerpt (about how THEY worked, not about their agents)
why             : WHY building this habit makes THEM a stronger AI-collaborator — the
                  transferable payoff across every codebase + every session, plus the
                  cost the current gap keeps costing them
how             : the concrete PERSONAL PRACTICE they adopt — a habit they build in
                  themselves, phrased in the second person ("your next 5 edits, Read
                  first"). NOT an infra/agent/tooling/hook/extractor change.
example         : how THEY phrase or sequence things differently next time — a line
                  they say/do themselves, adapted from their OWN curated excerpt
retest_tip      : a PERSONAL BEHAVIOR for them to watch IN THEMSELVES next scan
                  (a measurable signal they'll feel improve)
evidence_excerpt: (OPTIONAL) a short REDACTED paraphrase of the driving turn from the
                  curated evidence — no path, no verbatim body, no secret. The
                  renderer shows it as a small "from your work" quote-block under
                  `example`. Omit in lite mode (no excerpts read).
```

**Make coaching a growth plan — pin the SKILL to the sub-signal that dragged the
pillar AND to the curated excerpt that drove it (§2b.1).** A world-class entry does
five things, all grounded in the DEEP-READ of the weak sub-signal's
`evidence_excerpts` — and all framed as *the human building a habit in themselves*:
1. **`weak` — name the weakest sub-signal + its partition, and describe WHAT the user
   did in the curated excerpt** ("`inspect_before_edit`: `applied 9/14`, so in 3
   episodes you edited a core file straight after the task turn without reading it
   first — the diagnosis instinct was there, but you didn't lead with it yourself").
   Use the §4 catalog + the extractor counts so `weak` is *countable*, and the curated
   excerpt so it is *concrete* — countable anchor + seen-it depth, never a vibe. Keep
   it about **how the human worked**, not about their tooling.
2. **`why` — why building this habit makes THEM stronger.** State the *transferable*
   payoff first ("read-before-edit is the core diagnosis muscle — it transfers to
   every codebase and every AI session you'll run"), then the cost the current gap
   keeps costing them (regressions, burned turns, a change no reviewer can trust). Tie
   it to *their growth*, not to a metric this run.
3. **`how` — a specific PERSONAL practice, in the second person.** A habit they build
   in themselves, with the exact phrase/move, e.g. *"Your next 5 edits, read the
   relevant lines FIRST and say one sentence: 'I understand this does X; I'm changing
   it to Y because Z.' Only then edit — make it a reflex, not a rule you type."* NOT a
   change to their agents/tools/hooks. (See the DETECTION RULE below.)
4. **`example` — how THEY phrase/sequence it differently next time, from their OWN
   curated evidence.** Show a first-person line *they* say/do, adapted from the actual
   moment you deep-read — not a generic template, and not an instruction to their
   agent. e.g. *"Before your next fix, type to yourself: 'Read the lines I'm about to
   change first — what does this actually do?' then edit."* You MAY also set the
   optional `evidence_excerpt` to a short redacted paraphrase of the driving turn
   ("edited a core module right after the task turn with no prior Read") so the card
   can render a small "from your work" quote-block — keep it redacted (basename/
   paraphrase, no path, no verbatim body, no secret).
5. **`retest_tip` — a behavior for them to track IN THEMSELVES.** Re-express the same
   sub-signal as a personal next-scan signal they'll feel ("Next scan, watch your own
   `root_cause_depth` — aim to feel yourself state a cause before the fix in every
   debug episode you run"), so their progress is both measurable and *felt*.

> **THE DETECTION RULE (self-check every `how` and `example` before you ship it).**
> If a `how`/`example` prescribes changing the user's **agents, tools, hooks,
> settings, extractor, angels, orchestrator, TaskCreate, or any part of their
> setup** — rather than a **habit the human builds in themselves** — it is WRONG.
> Rewrite it into a personal practice.
> - ❌ FORBIDDEN as the coaching (infra-plumbing): "make your angels echo `file:line`
>   into the main thread", "add a `TaskCreate` to your wave", "wire your extractor
>   to…", "have your subagent paste the exit line". These tell the user to change
>   their *machine*, not to grow their *own* skill.
> - ✅ REQUIRED (a transferable human habit): "before you change a file, read the
>   relevant lines and state your understanding in one sentence — practice it your
>   next 5 edits", "state the cause yourself before you fix", "paste the verify
>   receipt yourself when you claim done", "write the 'done when ___' yourself before
>   you delegate". These are habits the *human* carries everywhere.
> - An infra tip MAY appear only as a brief **secondary aside** *after* the personal
>   practice ("(later, you can automate this in a hook — but build the reflex first)"),
>   never as the primary `how`/`example`.

> **In lite mode (§2.7)** there are no excerpts, so `weak` uses the partition alone,
> `example` is a general copy-adaptable *personal* line (say honestly it isn't from a
> read of their work), and `evidence_excerpt` is omitted. Everywhere else, coach the
> habit *from* the curated evidence — that is the product.

Voice = **warm, second-person skill-development coach — encouraging, developmental,
never a verdict.** Say "you". Be concrete, tied to what you actually saw, always about
a habit the human practices and carries forward. Never generic. For pillars **at or
above** target, add a one-line `strengths[]` affirmation (especially: high P7 with low
re-typing = a **win**, and automated P6 memory the chat-only scorers are blind to = a
**moat win**). `strengths[]` entries may be a plain string OR `{pillar, note}` — the
renderer tolerates both; do not regress that.

> **Unmeasured ≠ coachable-low.** Do NOT emit a coaching entry for a pillar/
> sub-signal that is `unmeasured` (`extraction-gap`/`no-opportunity`/etc.). You have
> no evidence of a weakness — coaching it would be a fabricated gap. Instead, note
> honestly in the summary that it wasn't observable this window and, if useful,
> suggest what would make it measurable next time (e.g. "delegation never happened,
> so orchestration couldn't be read — try one subagent spawn next sprint").

---

## 7. STEP 6 — Write the report file (LOCAL) and verify your own output

Emit **one JSON file** matching `../../SPEC.md` §7 (the v2 superset) **exactly**.
Then optionally emit the `.md` twin. Then tell the user the absolute path + a short
summary.

**Path selection:**
- Default: `./agentcraft-report.agentcraft.json` in the current working directory.
- If cwd is not writable or the user prefers isolation: OS temp dir
  (`%TEMP%\agentcraft-report.agentcraft.json` on Windows / `$TMPDIR` or `/tmp` on POSIX).
- Never write outside the user's machine (there is nowhere else — AGENTCRAFT is local).

**Schema invariants you MUST satisfy** (the renderer enforces these; SPEC §7):
1. `pillars` contains **all** keys `P1..P7`; an unmeasured/ineligible pillar ⇒
   `eligible:false`, `score:null`, `measurement_status:"unmeasured"`,
   `limitations:"<code>"`.
2. `overall.score` integer 0–100; `overall.tier` ∈ `{diamond,gold,silver,bronze}`
   consistent with `config.tier_bands`.
3. `meta_metrics`, `coverage`, and all §5b descriptive/synthesis blocks are
   **never** folded into `overall`.
4. Every **graded** pillar carries ≥1 `evidence` item; every **measured**
   sub-signal carries the partition + `measurement_status` + `capability`
   (+ `evidence` where you can point to it).
5. `coaching` has **exactly one** entry per eligible pillar with
   `score < config.target`. No coaching for `unmeasured` pillars.
6. `brand` mirrors the SPEC §0 `BRAND` value (`"AGENTCRAFT"`) — single rename source.
7. **v2 partition/containment** (§4e) hold for every v2 sub-signal OBJECT and every
   pillar `partition` roll-up. `agentcraft_version:"2"`.
8. `config.measurement_threshold` present (default 3); `measured ⇔ eligible >= it`.

**Top-level envelope you MUST emit (SPEC §7.1):**
```jsonc
"agentcraft_version": "2",                     // enables v2 blocks
"brand": "AGENTCRAFT",                         // mirror SPEC §0 BRAND
"generated_at": "<ISO-8601 UTC, e.g. 2026-09-11T00:00:00Z>",
"subject": { "label": "local-user", "repo_path": "<abs repo path or null>" }
```

**Sub-signal object shape (v2 — fill from the extractor counts):**
```jsonc
"inspect_before_edit": {
  "score": 68,                       // derived (§4a), or null if unmeasured
  "measurement_status": "measured",  // measured | unmeasured
  "capability": "mutation",          // the depended-on capability (§4c)
  "eligible": 14, "applied": 9, "declined": 2, "missed": 3,   // partition: sum == eligible
  "verified_outcome": 6,             // <= applied
  "limitations": null,               // null when measured; a §4b code when unmeasured
  "evidence": [ { "session": "s3", "turn": 12, "note": "Read x.py before Edit x.py" } ]
}
```
A pillar keeps its v1 fields (`name`, `eligible`, `score`, `evidence`, `moat`) and
ADDS `measurement_status`, `limitations`, and a `partition` roll-up (sum over its
measured sub-signals). See `../../examples/sample-report-v2.agentcraft.json` for a
complete, containment-valid example — mirror its shape.

**`config` block you MUST emit (records what this run used — SPEC §7.8):**
```jsonc
"config": {
  "target": 75,                          // coaching fires below this (override if the user names a tier)
  "tier_bands": { "diamond": 85, "gold": 75, "silver": 65 },
  "credit_positive": true,               // "declined a bad option" counts up (the declined bucket)
  "fairness_rule": true,                 // credit standing conventions even when not re-typed
  "measurement_threshold": 3             // measured requires eligible >= this (default 3)
}
```

**After writing, verify your own output (prove-don't-declare):**
```bash
# 1) Valid JSON + full v2 validation (all P1..P7, tier legal, partition + containment)
#    via the renderer's validator:
python ../../render/agentcraft_card.py --report agentcraft-report.agentcraft.json --summary-only
#    Exit 0 + a printed summary = the renderer accepts your file.

# 2) Independent containment self-check (mirrors SPEC §2d; adapt path):
python ../../examples/_v2_containment_check.py agentcraft-report.agentcraft.json
#    Prints "OK containment + partition + verified_outcome<=applied + ..." on success.

# 3) Quick invariant self-check:
python -c "import json;r=json.load(open('agentcraft-report.agentcraft.json',encoding='utf-8'));\
p=r['pillars'];assert all(k in p for k in ['P1','P2','P3','P4','P5','P6','P7']);\
assert r['overall']['tier'] in {'diamond','gold','silver','bronze'};\
assert all((p[k].get('eligible') is False) or p[k].get('evidence') for k in p),'graded pillar missing evidence';\
t=r['config']['target'];\
below=[k for k in p if p[k].get('eligible') and p[k].get('score') is not None and p[k]['score']<t];\
assert len(r['coaching'])==len(below),'coaching count != below-target eligible pillars';\
print('OK schema invariants')"
```
If any check fails, **fix the report**, don't declare success.

**Then tell the user:**
- The absolute path of the report file (and the `.md` twin if written).
- One-line headline: `OVERALL <n> (<tier>) · % VERIFIED <n>`.
- The 1–3 highest-leverage coaching moves (from `coaching`), phrased as a warm
  skill-development coach — each a **habit for the user to build in themselves**
  (a transferable personal practice), pinned to the sub-signal + partition that
  dragged its pillar. Growth framing, not a verdict.
- What was **unmeasured** this window and why (honest-empty), if anything.
- Reminder: nothing left the machine; to draw the card run
  `python render/agentcraft_card.py --report <path> --out card.png` (also offline).

---

## 7b. REDACTION CRAFT — the shareable summary (only if the user asks to share)

The **local report keeps full evidence** — paths, session ids, turn indices, exact
counts — because it never leaves the machine. But if the user wants something they
can post (a screenshot, a gist, a tweet), you write a **separate redacted file**
(`agentcraft-share.md`) that carries the *shape* of the result with **none** of the
private substrate. You still do not transmit it — you write it locally; the user
shares it manually.

**Redaction rules (a shareable artifact MUST NOT contain):**
- **No file paths** — not repo paths, not `path:line`, not directory names. Say "a
  core module", not `src/core/engine.py`.
- **No names / identifiers** — no repo name, no project slug, no session UUIDs, no
  usernames, no branch names, no company/product names.
- **No verbatim quotes** — never paste a prompt, a code snippet, an error string, or
  a `tool_result` line. Describe the behaviour in **your own sentences**.
- **No turn indices or session ids** — the evidence pointers stay in the local JSON
  only.

**What the shareable summary MAY contain:**
- The 7 pillar scores + OVERALL + tier + % VERIFIED (numbers reveal nothing private).
- The coaching **gist** in your own words (the *shape* of a gap, not the evidence):
  "verification closure is the biggest lever — completion claims sometimes shipped
  without a captured pass/fail receipt" — never the file it happened in.
- Descriptive blocks abstracted: `work_mix` as proportions, `style` as adjectives,
  the `trend` direction ("P6/P7 rising over three weeks") — no artifacts.

**Self-check the redaction before telling the user it's shareable:**
```bash
# Fail-loud grep: a shareable file must contain ZERO path-like or id-like leaks.
grep -nE "([A-Za-z]:[\\\\/]|/[Uu]sers/|\\.py:|\\.ts:|[0-9a-f]{8}-[0-9a-f]{4})" agentcraft-share.md \
  && echo "LEAK FOUND -> redact again, do NOT call it shareable" || echo "OK redacted (no path/uuid leak)"
```
If the grep finds anything, redact again. Own-sentences, no substrate — that is the
craft. (This is purely local text hygiene; still no network, ever.)

---

## 8. Guardrails (re-read before finishing)

- **Privacy is HONEST, not overclaimed.** Zero third-party egress — no transmission,
  no MEGA, no AGENTCRAFT server, no external API, no telemetry, ever. The report is the
  only artifact, and it stays local. But do NOT tell the user "the AI never sees your
  data" — that is false: your own Claude deep-reads curated slices of their work to
  coach them (§0). The honest contract is: your own Claude reads your work to coach
  you; the extractor curates so it reads relevant slices not everything; nothing goes
  to any third party; a counts-only lite mode (§2.7) exists for the privacy-paranoid.
- **Judge from curated evidence — do NOT re-read the raw multi-GB history.** Coaching
  depth comes from DEEP-READING the curated `evidence_excerpts` (§2b.1), plus at most
  a few targeted cited turns for ambiguity — never from slurping the whole history
  into context (privacy + cost). Excerpts stay redacted; never quote a secret/.env/
  raw body.
- **Extractor-first (v2).** Run `agentcraft_extract.py` before scoring; score *from
  counts* (the falsifiable anchor) and coach *from the curated excerpts* (the depth).
  If it's missing, fall back to the manual read and say so — never fabricate counts.
- **Coach the HUMAN's skill, not their infra.** Every `how`/`example` is a
  **transferable personal habit the user builds in themselves** (read-first, name-the-
  cause, paste-the-receipt-yourself, write-the-'done when'-yourself), NOT a change to
  their agents/tools/hooks/extractor/orchestrator. Run the DETECTION RULE (§6): if the
  prescription tells them to change their *setup* instead of grow their *own* skill,
  rewrite it. An infra tip is allowed only as a brief secondary aside after the habit.
  Voice = warm, second-person, developmental. This is the North-Star — don't regress it.
- **Own-work example.** Every coaching `example` is drawn from the user's OWN curated
  evidence, phrased as a line *they* say/do differently next time (except in lite
  mode, where you say honestly it is a general personal line). A generic template — or
  an instruction aimed at their agent — when an own-work excerpt was available is the
  shallow sin.
- **prove-don't-declare.** Every graded pillar cites evidence AND fills its
  sub-signal partitions from countable cues. `verified_outcome` surfaces it per
  behaviour. If you can't point to it (session/turn/file/count), you can't score it
  high.
- **Depth over vibes.** Score sub-signals via the §4 partition + catalog; a pillar
  score is the average of *measured* sub-signal scores, never a gut number.
- **Honest-empty is structural.** Thin/gated signal ⇒ `unmeasured` + a `limitations`
  code, `score:null`, excluded from the average — NEVER a fabricated low number, and
  NEVER coached as a gap.
- **Never score-low what the harness can't show.** Gated-out capability ⇒
  `extraction-gap`, not 0. (The fairness fix.)
- **Containment holds** (§4e) — partition sums, `verified_outcome <= applied`,
  component-wise ≤ pillar, episode ceiling. The renderer fails loud otherwise.
- **Read the sidechains.** Delegated work's inspect/verify evidence lives in
  subagent returns — sample them (§2b) so P3/P4/P5 aren't under-read. Conservative is
  fine; blind is not.
- **Fairness.** Credit encoded discipline even when not re-typed. Reward automation
  over re-pasting (`applied`, not `missed`). This is the MEGA fix — don't regress it.
- **Meta ≠ grade.** Never fold OUTCOME/EFFICIENCY/COVERAGE/verified_rate or any §5b
  descriptive block into OVERALL.
- **Coach, not judge — a skill-development coach.** End on concrete, kind, testable
  **habits the user builds in themselves**, pinned to the weakest sub-signal partition
  AND to the curated excerpt you deep-read — not a verdict, not an infra to-do list.
  The counts say *where*; the excerpt says *what you saw*; the prescription says *how
  YOU level up your own skill and carry it to every future session*.
- **You are the judge.** No external judge, no API key required. Local reasoning by
  the user's own agent, following this runbook.

---

*AGENTCRAFT v2 — deeper than a chat-only quiz. Reads chat **and** system. Seven axes,
two of them MEGA-blind. All 24 MEGA traits mapped under a cleaner card via ~40
sub-signals, each scored as a countable partition (`eligible = applied + declined +
missed`, declined positive, `verified_outcome <= applied`). Honest-empty is
structural. Meta-metrics that inform without punishing. A coach, not a verdict.
100% local. Backward-tolerant to v1. Inspired by MEGA.dev — we win by building
deeper, open, and private.*
