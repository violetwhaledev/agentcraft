# The build story — v1 → v2, in the open

AGENTCRAFT started with a small, honest itch.

## The spark

A developer ran one of those *"how good are you with AI agents?"* quizzes. It handed
back a shiny card, a tier, and a number to screenshot. Fun — but three things nagged:

1. **It was shallow.** It graded a single chat. It never saw the *system* — the
   `CLAUDE.md`, the skills, the hooks, the memory files — the exact places where a
   serious builder *encodes* their discipline so they never have to re-type it.
2. **It judged, but it didn't coach.** A number tells you *where* you are. It doesn't
   tell you *how to get better by Friday.*
3. **It wanted to ship your data off your machine.** Your session history is the most
   intimate record of how you actually think and build. Uploading it to a stranger's
   server to get a score felt backwards.

So the itch became a project: build a coach that reads your work the way a mentor
would — locally, on your own agent — and teaches you *how to level up your own skill*.

## v1 — the 7-pillar baseline

The first version was the smallest honest thing that answered the three complaints:

- **7 pillars** instead of a single-chat trait set: Intent & Framing, Context &
  Grounding, Execution & Diagnosis, Orchestration, Verification, Memory & Continuity,
  System-Discipline.
- **Reads your system**, not just one conversation — `CLAUDE.md`, `.claude/skills`,
  hooks, gates, scripts.
- **A falsifiable partition** per signal — `applied + declined + missed`, with
  `verified_outcome ≤ applied` — so a score is *countable*, not a vibe.
- **Runs on your own Claude Code agent**, offline. No account, no key, no upload.

It rendered a clean card and produced a report that stayed on your disk. Silver-72 on
the synthetic sample, with System-Discipline as a strength — the fairness rule in
action (encoding rigor into your system should score *higher*, not lower, than
re-pasting rules into every prompt).

## v2 — deeper, broader, and an actual coach

v1 proved the shape. v2 made it a superset and taught it to teach:

- **MEGA-superset (breadth).** v2 maps **every axis the category leader
  ([MEGA.dev](https://mega.dev)) measures — all 24 traits** — under 7 cleaner pillars.
  Each trait is *mapped*, not approximated (see [`CROSSWALK.md`](./CROSSWALK.md)),
  **plus two axes that a chat-only scorer is structurally blind to**: Memory &
  Continuity, and System-Discipline.
- **Depth.** 7 pillars fan out into ~40 sub-signals, each its own countable partition,
  streamed from your real history (the largest session is read *in full*, line by line,
  memory-safe — never byte-capped, because that's where the real work lives).
- **A coach, not a verdict.** Every below-target pillar gets a growth entry:
  *weak → why it costs you → how to fix it → an example pulled from your own history →
  a behavior to retest next scan.* The prescription is always **you** getting stronger
  as an AI-collaborator — never a tweak to your tooling.
- **Two pages.** A redacted, screenshot-able **share card** (page 1) and a **private
  depth dashboard** (page 2). The share card is passed through a fail-loud redaction
  guard so it can never carry a path, filename, or secret. The depth page stays local
  and is git-ignored by default.
- **Local, the honest way.** Still zero third-party egress — grep the code yourself
  (there is no `requests`, `urllib`, `socket`, `fetch`; the only subprocess is a local
  headless Chrome to draw the PNG). No telemetry, no server, no key.

## Credit where it's due

AGENTCRAFT was **inspired by [MEGA.dev](https://mega.dev)**, which opened this category
and made scoring AI-collaboration skill a thing people care about. We're not here to
dunk on MEGA — we're here to push the idea further, in the open (MIT), and keep your
data on your machine. Standing on shoulders, not stepping on toes.

## What "build in public" means here

- The brand is single-sourced in [`SPEC.md`](./SPEC.md) §0, and renaming is one command
  (`python rename.py NEWNAME`) — no aspirational grep-sweep.
- The rubric ([`RUBRIC.md`](./RUBRIC.md)) and the crosswalk are open, so every claim can
  be checked trait by trait.
- v1 reports still render untouched under v2 (backward-tolerant superset — see
  [`MIGRATION.md`](./MIGRATION.md)).

It's still improving in the open. PRs welcome — be kind, be specific, and prove it
before you say it's done.
