#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGENTCRAFT signal extractor  --  the mandatory Step 1 of the assessment runbook.

WHAT IT IS
  A pure-stdlib, streaming, 100% LOCAL reader of your Claude Code session
  history (~/.claude/projects/<slug>/*.jsonl). It segments the transcript into
  TASK EPISODES and counts the observable cues AGENTCRAFT v2 scores from -- so the
  judging agent scores FROM COUNTS (a falsifiable partition), never from vibes.

WHAT IT IS NOT
  It does NOT score, grade, or judge -- that is the agent's job (SKILL.md).
  It NEVER sends a byte anywhere. There is no network primitive in this file.
  Grep it yourself:  grep -niE "requests|urllib|socket|http|urlopen" agentcraft_extract.py

CONTRACT (SPEC.md v2 sections 1b/1c/1d/2c/2d)
  * task_episodes  -- THE denominator + hard upper bound for every sub-signal's
                      `eligible`. Segmented from real task-initiating user turns.
  * partition      -- per sub-signal, per episode: applied / declined / missed and
                      verified_outcome<=applied. Emitted as per-episode facts +
                      pre-tallied aggregate counts; the agent maps counts->score.
  * capability_gating -- which Claude Code capabilities were observable this window,
                      so a gated-out capability yields `unmeasured`+`extraction-gap`,
                      NEVER a low score (the fairness fix).

DESIGN
  A single-file, argparse-driven, portable tool: it auto-detects your Claude Code
  project slug, streams every session line by line, segments task episodes, and
  tallies the observable cues -- with a built-in --self-test that validates the
  counting math on a synthetic transcript so you can trust the numbers.

LOAD-BEARING: the N LARGEST sessions are streamed IN FULL (line by line, memory-
  safe). We do NOT byte-cap the largest session -- that is where the real work lives.

Windows: run with `python` (not python3). ASCII-only. No third-party imports.
License: MIT (same as the project).
"""

import argparse
import collections
import glob
import json
import os
import re
import sys
import tempfile


# --------------------------------------------------------------------------- #
# Evidence curation bounds -- the depth-WITHOUT-total-dump contract.           #
# The extractor pre-digests the whole history and CURATES a small set of       #
# REPRESENTATIVE, REDACTED excerpts (the episodes/turns that drove each WEAK    #
# sub-signal) so the judging agent DEEP-READS the RELEVANT slices, not the raw  #
# GBs. Bounded + minimal + redacted (no secrets/.env/keys/paths in excerpts).  #
# --------------------------------------------------------------------------- #
MAX_EXCERPTS_PER_SIGNAL = 6      # per WEAK (missed>0) sub-signal (--max-excerpts)
GLOBAL_EXCERPT_CAP = 60          # hard ceiling across ALL sub-signals, always


# --------------------------------------------------------------------------- #
# Constants -- the observable-cue vocabulary (mirrors SPEC 1b). Data, not code. #
# --------------------------------------------------------------------------- #

# Tools that constitute an INSPECT of a path (a Read/Grep/Glob primes a later Edit).
READ_TOOLS = ("Read", "Grep", "Glob", "NotebookRead")
# Tools that constitute a MUTATION of a path.
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
# Tools that constitute DELEGATION (spawning a sub-agent / sidechain).
DELEGATE_TOOLS = ("Task", "Agent")
# Substrings in a Bash command that make it an independent VERIFICATION run.
VERIFY_CMD_KEYS = (
    "test", "pytest", "tsc", "py_compile", "--check", "node --check",
    "npm run build", "npm test", "vitest", "jest", "lint", "ruff",
    "mypy", "bash -n", "cargo test", "go test", "--selftest", "--self-test",
)
# Substrings that signal an explicit root-cause diagnosis (multilingual: PL+EN).
ROOT_CAUSE_KEYS = ("root cause", "root-cause", "przyczyna", "because the bug",
                   "the cause is", "reproduc")
# Task-class hint keywords -> the 9 work_mix kinds (SPEC 5b). First hit wins.
TASK_CLASS_HINTS = (
    ("bugfix", ("fix", "bug", "broken", "napraw", "błąd", "blad", "error", "crash")),
    ("debug", ("debug", "why is", "investigate", "diagnose", "trace", "dlaczego")),
    ("refactor", ("refactor", "clean up", "cleanup", "rename", "restructure", "simplify")),
    ("test", ("test", "coverage", "pytest", "vitest", "assert")),
    ("docs", ("readme", "document", "docs", "comment", "spec", "changelog")),
    ("ops", ("deploy", "ci", "pipeline", "docker", "build", "release", "migration")),
    ("research", ("research", "explore", "compare", "evaluate", "options", "zbadaj")),
    ("review", ("review", "audit", "check the", "look over", "critique")),
    ("feature", ("add", "build", "implement", "create", "new ", "zbuduj", "dodaj")),
)


# --------------------------------------------------------------------------- #
# JSONL line parsing (tolerant; a bad line is skipped, never fatal).           #
# --------------------------------------------------------------------------- #

def _content_blocks(obj):
    """Return (type, [blocks]) from a transcript record. Normalizes str content."""
    t = obj.get("type")
    msg = obj.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        c = [{"type": "text", "text": c}]
    return t, (c or [])


def _text_of(blocks):
    """Concatenate all text-block text in a message (lowercased for cue matching)."""
    out = []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text") or "")
    return "".join(out)


def _is_real_user_turn(obj, blocks):
    """A genuine task-initiating user turn: has text, not a meta/caveat, not a
    pure tool_result echo. Mirrors the proven prototype's real_prompts gate."""
    txt = _text_of(blocks)
    is_meta = (obj.get("isMeta") or txt.startswith("<local-command-caveat>")
               or txt.startswith("Caveat:") or txt.startswith("<command-"))
    has_tool_result = any(isinstance(b, dict) and b.get("type") == "tool_result"
                          for b in blocks)
    return bool(txt.strip()) and not is_meta and not has_tool_result


def _classify_task(text):
    low = text.lower()
    for name, keys in TASK_CLASS_HINTS:
        if any(k in low for k in keys):
            return name
    return "feature"


# --------------------------------------------------------------------------- #
# REDACTION -- deterministic, pure-stdlib. Applied AT CAPTURE TIME so a raw     #
# secret/path/body NEVER enters an excerpt candidate in the first place.        #
# Contract (North-Star privacy = honest transparency, not overclaim): the       #
# curated excerpts are what the user's OWN Claude deep-reads to coach; we keep   #
# them bounded + minimal + redacted so no secret/.env/key/home-path leaks.      #
# --------------------------------------------------------------------------- #

# A candidate is HARD-DROPPED if its command/text looks like it carries a secret.
# Conservative: token-shaped runs, key/secret/password words, .env, auth headers.
_SECRET_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret|password|passwd|token|bearer|authorization"
    r"|\.env\b|-----BEGIN|[A-Za-z0-9_\-]{32,})")

# Verb classification for a Bash command's FIRST token -> a safe category word.
_BASH_VERB = {
    "pytest": "pytest", "python": "python", "python3": "python", "py": "python",
    "node": "node", "npm": "npm", "npx": "npx", "pnpm": "npm", "yarn": "npm",
    "tsc": "tsc", "git": "git", "cargo": "cargo", "go": "go", "ruff": "ruff",
    "mypy": "mypy", "vitest": "vitest", "jest": "jest", "eslint": "lint",
    "bash": "bash", "sh": "sh", "make": "make", "docker": "docker",
    "curl": "curl", "ls": "ls", "cat": "cat", "grep": "grep",
}


def _basename(path):
    """Path -> basename only. Strips every directory + home dir + drive letter,
    so `C:\\Users\\me\\src\\core\\engine.py` -> `engine.py`. Never leaks a dir."""
    if not path:
        return ""
    s = str(path).replace("\\", "/")
    base = s.rsplit("/", 1)[-1]
    # A bare pattern (Grep) may have no separator; keep it short + secret-safe.
    if not base:
        base = s
    if _SECRET_RE.search(base):
        return "[redacted]"
    return base[:48]


def _bash_verb(command):
    """A Bash command -> its FIRST token classified to a safe verb word ONLY.
    NEVER returns the full command (may hold secrets/tokens/paths). Returns None
    if the command looks secret-shaped (caller then drops the candidate)."""
    if not command:
        return None
    if _SECRET_RE.search(command):
        return None
    first = command.strip().split()[0] if command.strip().split() else ""
    first = first.replace("\\", "/").rsplit("/", 1)[-1]  # strip any path prefix
    return _BASH_VERB.get(first.lower(), "cmd")


def _safe(text, limit=160):
    """A short machine paraphrase string -> secret-scrubbed + length-capped.
    We build paraphrases from tool METADATA (never raw prompt/code bodies), but
    scrub defensively anyway so nothing secret-shaped ever survives.

    The cap is generous enough (default 160) that our fixed metadata sentences
    survive WHOLE -- a mid-word chop ('...with no ') would drop the diagnostic
    tail the judging agent deep-reads to coach, hurting depth for zero privacy
    gain (the sentence is already redacted). If a paraphrase does exceed the
    cap, we trim at the last WORD BOUNDARY and append an ellipsis so the excerpt
    stays a clean, readable, honest slice -- never a truncated fragment."""
    if not text:
        return ""
    t = " ".join(str(text).split())          # collapse whitespace
    if _SECRET_RE.search(t):
        return "[redacted]"
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0]        # trim at last whole word
    return (cut or t[:limit]).rstrip() + "..."


# --------------------------------------------------------------------------- #
# Episode segmentation + counting.                                             #
# --------------------------------------------------------------------------- #

class Episode(object):
    """A contiguous objective span: real user turn -> work -> next real user turn.
    Holds the per-episode partition facts the agent needs."""

    __slots__ = ("idx", "session", "task_class", "first_ts",
                 "reads", "edits", "read_before_edit", "edit_after_read_miss",
                 "verify_runs", "agent_spawns", "taskcreate",
                 "thinking_turns", "root_cause_hits", "tools",
                 "blind_edits", "edited_names")

    def __init__(self, idx, session, task_class, ts):
        self.idx = idx
        self.session = session
        self.task_class = task_class
        self.first_ts = ts
        self.reads = 0
        self.edits = 0
        self.read_before_edit = 0       # edits where the same path was read first
        self.edit_after_read_miss = 0   # edits where the path was NOT read first
        self.verify_runs = 0
        self.agent_spawns = 0
        self.taskcreate = 0
        self.thinking_turns = 0
        self.root_cause_hits = 0
        self.tools = 0
        # Redacted-at-capture evidence-curation state (basenames only, no dirs):
        self.blind_edits = []           # basenames Edited with NO prior Read
        self.edited_names = []          # basenames Edited (for the closure paraphrase)

    def facts(self):
        """Per-episode boolean/near-boolean facts feeding sub-signal partitions.
        Each fact maps to an applied/missed/n-a call the agent makes per episode.
        We report the raw episode state; the agent buckets it (SPEC 1c)."""
        return {
            "idx": self.idx,
            "session": self.session,
            "task_class": self.task_class,
            "ts": self.first_ts,
            "tools": self.tools,
            "reads": self.reads,
            "edits": self.edits,
            "read_before_edit": self.read_before_edit,
            "edit_after_read_miss": self.edit_after_read_miss,
            # inspect_before_edit: eligible iff the episode has >=1 edit.
            "has_edit": self.edits > 0,
            "inspect_applied": self.edits > 0 and self.edit_after_read_miss == 0,
            "verify_runs": self.verify_runs,
            # closure/independent verification: applied iff a verify ran after edits.
            "verify_applied": self.edits > 0 and self.verify_runs > 0,
            "verify_missed": self.edits > 0 and self.verify_runs == 0,
            "agent_spawns": self.agent_spawns,
            "delegated": self.agent_spawns > 0,
            "taskcreate": self.taskcreate,
            "decomposed": self.taskcreate > 0,
            "thinking_turns": self.thinking_turns,
            "thought_first": self.thinking_turns > 0,
            "root_cause_hits": self.root_cause_hits,
            # root_cause: eligible iff a debug/bugfix episode; applied iff a cause named.
            "diagnosis_eligible": self.task_class in ("bugfix", "debug"),
            "root_cause_named": self.root_cause_hits > 0,
        }


def _iter_jsonl(path):
    """Stream a JSONL file line by line -- memory-safe even for a multi-GB session."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue  # tolerant: a malformed line is skipped, never fatal


def scan_files(files, window_days=None):
    """Stream the given session files, segment episodes, tally counts.
    Returns (episodes, aggregate_counter, session_meta, capability_seen, ts_bounds)."""
    episodes = []
    agg = collections.Counter()
    tool_hist = collections.Counter()
    task_class_hist = collections.Counter()
    cap_seen = set()                 # capabilities actually observed this window
    first_ts = last_ts = None
    active_days = set()
    ep_idx = 0

    for path in files:
        session = os.path.basename(path)[:10]
        # Per-session state for read->edit ordering (SPEC 1b inspect_before_edit).
        recently_read = set()
        cur = None

        for obj in _iter_jsonl(path):
            t, blocks = _content_blocks(obj)
            ts = obj.get("timestamp")
            if ts:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts
                active_days.add(ts[:10])

            # ---- user turn: maybe a NEW episode boundary ----
            if t == "user":
                agg["total_user_turns"] += 1
                if _is_real_user_turn(obj, blocks):
                    agg["real_prompts"] += 1
                    cap_seen.add("message")
                    task_class = _classify_task(_text_of(blocks))
                    task_class_hist[task_class] += 1
                    ep_idx += 1
                    cur = Episode(ep_idx, session, task_class, ts)
                    episodes.append(cur)
                    recently_read = set()  # reset inspection memory at task boundary

            # ---- walk content blocks: count cues into the current episode ----
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")

                if bt == "thinking":
                    if cur:
                        cur.thinking_turns += 1
                    agg["thinking_turns"] += 1

                elif bt == "text":
                    low = (b.get("text") or "").lower()
                    if any(k in low for k in ROOT_CAUSE_KEYS):
                        if cur:
                            cur.root_cause_hits += 1
                        agg["root_cause_mentions"] += 1

                elif bt == "tool_use":
                    name = b.get("name")
                    inp = b.get("input") or {}
                    tool_hist[name] += 1
                    agg["total_tool_uses"] += 1
                    if cur:
                        cur.tools += 1

                    if name in READ_TOOLS:
                        cap_seen.add("retrieval")
                        fp = inp.get("file_path") or inp.get("path") or inp.get("pattern")
                        if fp:
                            recently_read.add(str(fp))
                        if cur:
                            cur.reads += 1

                    elif name in EDIT_TOOLS:
                        cap_seen.add("mutation")
                        agg["edits"] += 1
                        if cur:
                            cur.edits += 1
                            cur.edited_names.append(_basename(inp.get("file_path")))
                        fp = inp.get("file_path")
                        if fp and str(fp) in recently_read:
                            agg["read_before_edit"] += 1
                            if cur:
                                cur.read_before_edit += 1
                        else:
                            if cur:
                                cur.edit_after_read_miss += 1
                                # miss-driver captured redacted (basename only):
                                cur.blind_edits.append(_basename(fp))

                    elif name in DELEGATE_TOOLS:
                        cap_seen.add("delegation")
                        agg["agent_spawns"] += 1
                        if cur:
                            cur.agent_spawns += 1

                    elif name == "TaskCreate":
                        cap_seen.add("delegation")
                        agg["taskcreate"] += 1
                        if cur:
                            cur.taskcreate += 1

                    elif name == "Bash":
                        cmd = (inp.get("command") or "").lower()
                        if any(k in cmd for k in VERIFY_CMD_KEYS):
                            cap_seen.add("verification")
                            agg["verify_runs"] += 1
                            if cur:
                                cur.verify_runs += 1

                    elif name in ("Read", "Write") and str(inp.get("file_path", "")).endswith(
                            (".claude/settings.json", "CLAUDE.md")):
                        cap_seen.add("configuration")

    session_meta = {
        "top_tools": tool_hist.most_common(15),
        "task_class_hist": dict(task_class_hist),
        "distinct_active_days": len(active_days),
    }
    ts_bounds = ((first_ts or "")[:10], (last_ts or "")[:10])
    return episodes, agg, session_meta, cap_seen, ts_bounds


# --------------------------------------------------------------------------- #
# Capability gating (SPEC 2c): observable / partial / gated_out for the window. #
# --------------------------------------------------------------------------- #

# Every capability AGENTCRAFT sub-signals can depend on. Default class if never seen.
ALL_CAPABILITIES = (
    "message", "retrieval", "mutation", "verification", "delegation",
    "configuration", "attachment", "compaction", "branch",
)
# Capabilities whose absence in a window is a LOSSY-history fact (partial), not a
# developer failure -- these are hard to observe from JSONL alone.
INHERENTLY_PARTIAL = ("compaction", "branch", "attachment")


def capability_gating(cap_seen):
    """Classify each capability observable/partial/gated_out for this window.
    A capability never seen is gated_out (its dependent sub-signals become
    unmeasured + extraction-gap -- NEVER a low score). Inherently-lossy ones are
    reported as partial rather than a hard gate."""
    observable, partial, gated_out = [], [], []
    for cap in ALL_CAPABILITIES:
        if cap in cap_seen:
            observable.append(cap)
        elif cap in INHERENTLY_PARTIAL:
            partial.append(cap)
        else:
            gated_out.append(cap)
    return {"observable": observable, "partial": partial, "gated_out": gated_out}


def scan_discipline_surface(repo_path):
    """Inventory the on-disk discipline surface for P6/P7 -- repo-local AND the
    GLOBAL ~/.claude config -- so `configuration` is MEASURED from real files,
    not from whether the chat happened to open CLAUDE.md. 100% local: reads line
    counts + names only, nothing leaves. (SPEC: P7 System-Discipline, P6 memory.)"""
    import glob as _glob
    home = os.path.expanduser("~")

    def short(p):
        ab = os.path.abspath(p)
        return "~" + ab[len(home):] if ab.startswith(home) else ab

    def linecount(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                return sum(1 for _ in fh)
        except OSError:
            return 0

    files, total_lines, skills, hooks, memory = [], 0, 0, False, []
    for c in (os.path.join(repo_path, "CLAUDE.md"),
              os.path.join(repo_path, ".claude", "CLAUDE.md"),
              os.path.join(repo_path, "AGENTS.md"),
              os.path.join(home, ".claude", "CLAUDE.md")):        # GLOBAL standing rules
        if os.path.isfile(c):
            n = linecount(c)
            total_lines += n
            files.append({"path": short(c), "lines": n})
    for sk in (os.path.join(repo_path, ".claude", "skills"),
               os.path.join(home, ".claude", "skills")):          # repo + GLOBAL skills
        if os.path.isdir(sk):
            try:
                n = sum(1 for d in os.listdir(sk) if not d.startswith("."))
            except OSError:
                n = 0
            skills += n
            if n:
                files.append({"path": short(sk), "skills": n})
    for st in (os.path.join(repo_path, ".claude", "settings.json"),
               os.path.join(repo_path, ".claude", "settings.local.json"),
               os.path.join(home, ".claude", "settings.json")):   # hooks/gates
        if os.path.isfile(st):
            hooks = True
            files.append({"path": short(st), "settings": True})
    for pat in ("MEMORY.md", "SESSION_HANDOFF*.md", "*ADR*.md"):   # P6 memory artifacts
        for m in _glob.glob(os.path.join(repo_path, pat)):
            memory.append(short(m))
    return {
        "repo": short(repo_path),
        "has_config": bool(files),
        "standing_rule_lines": total_lines,
        "skills_count": skills,
        "hooks_present": hooks,
        "memory_artifacts": memory[:20],
        "files": files[:30],
        "scanned": "repo-local (CLAUDE.md/.claude/skills/settings/AGENTS.md) + GLOBAL ~/.claude",
    }


# --------------------------------------------------------------------------- #
# Evidence curation -- the DEPTH enabler. For each WEAK (missed>0) sub-signal,  #
# curate a bounded, REPRESENTATIVE, REDACTED set of excerpts (the episodes that #
# drove the miss) so the judging agent DEEP-READS the relevant slices, not the  #
# raw GBs. Depth WITHOUT the total dump. Additive: never touches any count.     #
# --------------------------------------------------------------------------- #

def _spread_pick(items, k):
    """Pick <=k items SPREAD across sessions so the sample is representative
    (not the first k from one giant file). Round-robins over sessions in order,
    preserving determinism. `items` = list of (episode, payload) candidates."""
    if k <= 0 or not items:
        return []
    buckets = collections.OrderedDict()
    for ep, payload in items:
        buckets.setdefault(ep.session, []).append((ep, payload))
    picked, i = [], 0
    # round-robin across sessions until we have k or run dry
    while len(picked) < k and any(buckets.values()):
        for sess in list(buckets.keys()):
            if not buckets[sess]:
                continue
            picked.append(buckets[sess].pop(0))
            if len(picked) >= k:
                break
        i += 1
        if i > len(items) + 1:  # safety: never loop forever
            break
    return picked


def curate_evidence_excerpts(episodes, max_per_signal):
    """Build {sub_signal: [excerpt, ...]} for WEAK sub-signals only (missed>0).

    Each excerpt = {episode_id, session, task_class, kind, paraphrase, ts} where
    `paraphrase` is a SHORT redacted machine description built from tool METADATA
    (basenames + verb classes) -- NEVER a raw code/prompt body, never a full path,
    never a secret. Bounded by `max_per_signal` per signal AND a hard global cap.

    Returns {} when max_per_signal <= 0 (the counts-only LITE MODE, for the
    privacy-paranoid -- honest, shallower, the user's explicit choice)."""
    if max_per_signal <= 0:
        return {}

    # Candidate builders per sub-signal. Each yields (episode, {kind, paraphrase})
    # for the episodes that DROVE that sub-signal's miss. Redacted at source.
    def inspect_cands():
        for e in episodes:
            if e.edits > 0 and e.edit_after_read_miss > 0:
                names = [n for n in e.blind_edits if n]
                shown = ", ".join(names[:3]) if names else "a file"
                extra = "" if len(names) <= 3 else " (+%d more)" % (len(names) - 3)
                yield e, {
                    "kind": "edit-without-read",
                    "paraphrase": _safe("edited %s%s with no prior Read/Grep on "
                                        "the same path" % (shown, extra)),
                }

    def closure_cands():
        for e in episodes:
            if e.edits > 0 and e.verify_runs == 0:
                names = [n for n in e.edited_names if n]
                cnt = e.edits
                where = (" (e.g. %s)" % ", ".join(names[:2])) if names else ""
                yield e, {
                    "kind": "claim-without-verify",
                    "paraphrase": _safe("edited %d file(s)%s but ran no "
                                        "test/compile/lint verification"
                                        % (cnt, where)),
                }

    def root_cause_cands():
        for e in episodes:
            if e.task_class in ("bugfix", "debug") and e.root_cause_hits == 0:
                yield e, {
                    "kind": "fix-without-root-cause",
                    "paraphrase": _safe("%s episode with no explicit 'Root cause:' "
                                        "statement before the fix" % e.task_class),
                }

    def decomposition_cands():
        for e in episodes:
            if e.agent_spawns > 0 and e.taskcreate == 0:
                yield e, {
                    "kind": "delegated-not-decomposed",
                    "paraphrase": _safe("spawned %d sub-agent(s) with no TaskCreate "
                                        "task breakdown" % e.agent_spawns),
                }

    builders = {
        "inspect_before_edit": inspect_cands,
        "closure": closure_cands,
        "root_cause_depth": root_cause_cands,
        "decomposition": decomposition_cands,
    }

    out = {}
    total = 0
    for signal, gen in builders.items():
        if total >= GLOBAL_EXCERPT_CAP:
            break
        cands = list(gen())
        if not cands:
            continue  # not a WEAK signal for this window (missed==0) -> no excerpts
        room = min(max_per_signal, GLOBAL_EXCERPT_CAP - total)
        chosen = _spread_pick(cands, room)
        rows = []
        for ep, payload in chosen:
            rows.append({
                "episode_id": ep.idx,
                "session": ep.session,
                "task_class": ep.task_class,
                "kind": payload["kind"],
                "paraphrase": payload["paraphrase"],
                "ts": ep.first_ts,
            })
        if rows:
            out[signal] = rows
            total += len(rows)
    return out


# --------------------------------------------------------------------------- #
# Aggregate roll-up the agent consumes.                                        #
# --------------------------------------------------------------------------- #

def build_output(episodes, agg, session_meta, cap_seen, ts_bounds,
                 sampled, sub_sampled, sessions_read, sessions_total,
                 max_excerpts=MAX_EXCERPTS_PER_SIGNAL):
    edits = agg["edits"]
    # Episode-level aggregate facts (the partition seeds the agent buckets).
    inspect_eligible = sum(1 for e in episodes if e.edits > 0)
    inspect_applied = sum(1 for e in episodes if e.edits > 0 and e.edit_after_read_miss == 0)
    verify_eligible = inspect_eligible  # verification is eligible when an edit exists
    verify_applied = sum(1 for e in episodes if e.edits > 0 and e.verify_runs > 0)
    diag_eligible = sum(1 for e in episodes if e.task_class in ("bugfix", "debug"))
    diag_applied = sum(1 for e in episodes
                       if e.task_class in ("bugfix", "debug") and e.root_cause_hits > 0)
    deleg_applied = sum(1 for e in episodes if e.agent_spawns > 0)
    decomp_applied = sum(1 for e in episodes if e.taskcreate > 0)

    return {
        "agentcraft_extract_version": "2",
        "note": ("counts only -- NOT a score. Feed to the AGENTCRAFT assessment agent "
                 "(SKILL.md) which derives the partition score per SPEC 1c."),
        "window": {"from": ts_bounds[0], "to": ts_bounds[1],
                   "distinct_active_days": session_meta["distinct_active_days"]},
        "coverage": {
            "sessions_read": sessions_read,
            "sessions_total": sessions_total,
            "sub_sampled": sub_sampled,        # True if not all sessions were read
            "sampled_files_MB": sampled,
            "task_episodes": len(episodes),    # SPEC 1c: THE denominator
        },
        "aggregate_counts": {
            "total_tool_uses": agg["total_tool_uses"],
            "top_tools": session_meta["top_tools"],
            "real_prompts": agg["real_prompts"],
            "total_user_turns": agg["total_user_turns"],
            "edits": edits,
            "read_before_edit": agg["read_before_edit"],
            "inspect_before_edit_ratio": (round(agg["read_before_edit"] / edits, 3)
                                          if edits else None),
            "verify_runs": agg["verify_runs"],
            "agent_spawns": agg["agent_spawns"],
            "taskcreate": agg["taskcreate"],
            "thinking_turns": agg["thinking_turns"],
            "root_cause_mentions": agg["root_cause_mentions"],
        },
        # Pre-bucketed episode partitions the agent maps 1:1 to sub-signals.
        # eligible = applied + declined + missed (declined defaults 0 here; the
        # agent promotes correct-not-to-do episodes to `declined` on inspection).
        "episode_partitions": {
            "inspect_before_edit": {
                "eligible": inspect_eligible, "applied": inspect_applied,
                "missed": inspect_eligible - inspect_applied, "declined": 0,
                "capability": "mutation"},
            "closure": {
                "eligible": verify_eligible, "applied": verify_applied,
                "missed": verify_eligible - verify_applied, "declined": 0,
                "capability": "verification"},
            "root_cause_depth": {
                "eligible": diag_eligible, "applied": diag_applied,
                "missed": diag_eligible - diag_applied, "declined": 0,
                "capability": "mutation"},
            "delegation_judgment": {
                "eligible": len(episodes), "applied": deleg_applied,
                "missed": 0, "declined": len(episodes) - deleg_applied,
                "capability": "delegation"},
            "decomposition": {
                "eligible": deleg_applied, "applied": decomp_applied,
                "missed": max(0, deleg_applied - decomp_applied), "declined": 0,
                "capability": "delegation"},
        },
        "task_class_hist": session_meta["task_class_hist"],
        "capability_gating": capability_gating(cap_seen),
        # CURATED EVIDENCE (the depth enabler): per WEAK sub-signal (missed>0), a
        # bounded set of REPRESENTATIVE, REDACTED excerpts -- the specific episodes
        # that drove the miss -- so the judging agent (the user's OWN Claude) can
        # DEEP-READ the relevant slices to coach WHAT/HOW/WHY, without a total dump.
        # Bounded (<=max_excerpts/signal, hard global cap), redacted (basenames +
        # verb classes only, no secrets/.env/keys/paths/bodies), 100% local.
        # Empty in counts-only LITE MODE (--max-excerpts 0).
        "evidence_excerpts": curate_evidence_excerpts(episodes, max_excerpts),
        "evidence_excerpts_note": ("redacted, bounded curation of the episodes that "
                                   "drove each WEAK sub-signal -- for the agent to "
                                   "deep-read relevant slices, NOT the raw history. "
                                   "counts-only lite mode: --max-excerpts 0."),
        # Per-episode raw facts -- the auditable evidence trail (bounded to keep
        # the file readable; the aggregate above is exhaustive).
        "episodes": [e.facts() for e in episodes[:500]],
        "episodes_truncated": len(episodes) > 500,
    }


# --------------------------------------------------------------------------- #
# Project / file discovery.                                                    #
# --------------------------------------------------------------------------- #

def projects_root():
    return os.path.expanduser(os.path.join("~", ".claude", "projects"))


def resolve_project(project):
    """Resolve a project slug. 'auto' picks the most-recently-active project dir."""
    root = projects_root()
    if not os.path.isdir(root):
        return None, []
    if project and project != "auto":
        cand = os.path.join(root, project)
        if not os.path.isdir(cand):
            # tolerate a substring match on the slug
            hits = [d for d in glob.glob(os.path.join(root, "*")) if project in os.path.basename(d)]
            cand = hits[0] if hits else cand
        return cand, sorted(glob.glob(os.path.join(cand, "*.jsonl")))
    # auto: the project dir whose newest jsonl is most recent
    best_dir, best_mtime = None, -1
    for d in glob.glob(os.path.join(root, "*")):
        js = glob.glob(os.path.join(d, "*.jsonl"))
        if not js:
            continue
        m = max(os.path.getmtime(p) for p in js)
        if m > best_mtime:
            best_dir, best_mtime = d, m
    if best_dir is None:
        return None, []
    return best_dir, sorted(glob.glob(os.path.join(best_dir, "*.jsonl")))


def pick_files(all_files, max_sessions):
    """Sort by size DESC and take the N LARGEST -- they hold the load-bearing work.
    CRITICAL: we do NOT byte-cap the giant session; it is streamed in full."""
    ordered = sorted(all_files, key=os.path.getsize, reverse=True)
    if max_sessions and max_sessions > 0:
        return ordered[:max_sessions]
    return ordered


# --------------------------------------------------------------------------- #
# Self-test on a SYNTHETIC fixture (no real data) -- proves partition math +   #
# containment invariants, offline, deterministic.                             #
# --------------------------------------------------------------------------- #

def _synthetic_lines():
    """Return a tiny synthetic JSONL transcript with KNOWN counts. 4 episodes:
      EP1 bugfix: Read a.py -> Edit a.py (inspect applied) + Bash pytest (verify) +
                  root-cause text + thinking. 1 agent spawn.
      EP2 feature: Edit b.py with NO prior Read (inspect MISSED), no verify.
      EP3 debug: Grep + text 'root cause' but NO edit (diagnosis applied, inspect n/a).
      EP4 feature: TaskCreate + Task (delegated + decomposed), no edits.
    Expected: episodes=4, edits=2, read_before_edit=1, inspect_ratio=0.5,
      verify_runs=1, agent_spawns=2, taskcreate=1, root_cause=2, thinking=1."""
    def user(text):
        return {"type": "user", "timestamp": "2026-09-01T10:00:00Z",
                "message": {"content": [{"type": "text", "text": text}]}}

    def asst(blocks):
        return {"type": "assistant", "timestamp": "2026-09-01T10:00:01Z",
                "message": {"content": blocks}}

    def tool(name, inp):
        return {"type": "tool_use", "name": name, "input": inp}

    recs = [
        # EP1
        user("fix the broken parser bug in a.py"),
        asst([{"type": "thinking", "text": "trace it"}]),
        asst([tool("Read", {"file_path": "a.py"})]),
        asst([{"type": "text", "text": "Root cause: off-by-one; reproduced it."}]),
        asst([tool("Edit", {"file_path": "a.py"})]),
        asst([tool("Bash", {"command": "python -m pytest tests/ -q"})]),
        asst([tool("Task", {"description": "spawn helper"})]),
        # EP2 -- blind edit uses a FULL Windows home path so the self-test can prove
        # redaction strips the dir + home + drive to a bare basename in the excerpt.
        # (Still ONE edit -> counts identical to the pre-curation fixture.)
        user("add a new feature to b.py"),
        asst([tool("Edit", {"file_path":
                            "C:\\Users\\someone\\Desktop\\proj\\src\\core\\b.py"})]),
        # EP3
        user("debug why the import fails"),
        asst([tool("Grep", {"pattern": "import"})]),
        asst([{"type": "text", "text": "the cause is a circular import"}]),
        # EP4
        user("build the new dashboard module"),
        asst([tool("TaskCreate", {"title": "unit A"})]),
        asst([tool("Task", {"description": "build unit A"})]),
        # a meta/caveat user turn that must NOT open an episode:
        {"type": "user", "message": {"content": [
            {"type": "text", "text": "<local-command-caveat>ignore me"}]}},
    ]
    return [json.dumps(r) for r in recs]


def run_selftest():
    tmpdir = tempfile.mkdtemp(prefix="agentcraft_selftest_")
    fpath = os.path.join(tmpdir, "synthetic.jsonl")
    with open(fpath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_synthetic_lines()) + "\n")

    episodes, agg, meta, cap_seen, ts = scan_files([fpath])
    out = build_output(episodes, agg, meta, cap_seen, ts,
                       sampled=[("synthetic", 0.0)], sub_sampled=False,
                       sessions_read=1, sessions_total=1)

    ac = out["aggregate_counts"]
    ep = out["coverage"]["task_episodes"]
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append("%s: got %r want %r" % (label, got, want))

    # ---- known-answer counts ----
    check("task_episodes", ep, 4)
    check("edits", ac["edits"], 2)
    check("read_before_edit", ac["read_before_edit"], 1)
    check("inspect_before_edit_ratio", ac["inspect_before_edit_ratio"], 0.5)
    check("verify_runs", ac["verify_runs"], 1)
    check("agent_spawns", ac["agent_spawns"], 2)
    check("taskcreate", ac["taskcreate"], 1)
    check("root_cause_mentions", ac["root_cause_mentions"], 2)
    check("thinking_turns", ac["thinking_turns"], 1)
    check("real_prompts", ac["real_prompts"], 4)  # the caveat turn excluded

    # ---- partition invariant: eligible == applied + declined + missed (SPEC 1c) ----
    for name, p in out["episode_partitions"].items():
        s = p["applied"] + p["declined"] + p["missed"]
        if s != p["eligible"]:
            fails.append("partition[%s]: applied+declined+missed=%d != eligible=%d"
                         % (name, s, p["eligible"]))
        # containment / ceiling: a sub-signal is never eligible in more episodes
        # than exist (SPEC 2d episode ceiling).
        if p["eligible"] > ep:
            fails.append("ceiling[%s]: eligible=%d > task_episodes=%d"
                         % (name, p["eligible"], ep))
        # applied is a non-negative subset of eligible.
        if not (0 <= p["applied"] <= p["eligible"]):
            fails.append("bound[%s]: applied=%d not in [0,%d]"
                         % (name, p["applied"], p["eligible"]))

    # ---- specific partition values (known-answer) ----
    ipe = out["episode_partitions"]["inspect_before_edit"]
    check("inspect eligible", ipe["eligible"], 2)   # EP1 + EP2 have edits
    check("inspect applied", ipe["applied"], 1)     # only EP1 read-before-edit
    check("inspect missed", ipe["missed"], 1)       # EP2 edited blind
    dcd = out["episode_partitions"]["root_cause_depth"]
    check("diagnosis eligible", dcd["eligible"], 2)  # EP1 bugfix + EP3 debug
    check("diagnosis applied", dcd["applied"], 2)    # both named a cause

    # ---- capability gating sanity (SPEC 2c): observed caps are observable ----
    cg = out["capability_gating"]
    for must in ("message", "retrieval", "mutation", "verification", "delegation"):
        if must not in cg["observable"]:
            fails.append("capability_gating: %s should be observable" % must)

    # ---- CURATED EVIDENCE: bounded + redacted + references real episodes ----
    ev = out["evidence_excerpts"]
    if not isinstance(ev, dict):
        fails.append("evidence_excerpts: not a dict")
    else:
        # (a) EP2 (blind edit b.py) drives inspect_before_edit AND closure (no verify).
        ib = ev.get("inspect_before_edit", [])
        if not any(x["episode_id"] == 2 for x in ib):
            fails.append("evidence: EP2 missing from inspect_before_edit excerpts")
        cl = ev.get("closure", [])
        if not any(x["episode_id"] == 2 for x in cl):
            fails.append("evidence: EP2 missing from closure excerpts")
        # (b) ONLY WEAK (missed>0) signals appear. EP1+EP2 both edit -> inspect
        #     eligible; EP1 read-first so ONLY EP2 is the inspect miss.
        if any(x["episode_id"] == 1 for x in ib):
            fails.append("evidence: EP1 (read-first) should NOT be an inspect miss")
        # decomposition weak: EP1 spawned a Task with NO TaskCreate -> a real miss;
        #   EP4 HAS a TaskCreate -> NOT a miss. So EP1 in, EP4 out.
        dc = ev.get("decomposition", [])
        if not any(x["episode_id"] == 1 for x in dc):
            fails.append("evidence: EP1 (delegated, no TaskCreate) missing from "
                         "decomposition excerpts")
        if any(x["episode_id"] == 4 for x in dc):
            fails.append("evidence: EP4 (has TaskCreate) should NOT be a "
                         "decomposition miss")
        # (c) every excerpt references a REAL episode (1..4) + carries kind+paraphrase.
        real_ids = {e.idx for e in episodes}
        for sig, rows in ev.items():
            if len(rows) > MAX_EXCERPTS_PER_SIGNAL:
                fails.append("evidence[%s]: %d exceeds per-signal cap %d"
                             % (sig, len(rows), MAX_EXCERPTS_PER_SIGNAL))
            for r in rows:
                if r["episode_id"] not in real_ids:
                    fails.append("evidence[%s]: episode_id %r not a real episode"
                                 % (sig, r["episode_id"]))
                if not r.get("kind") or not r.get("paraphrase"):
                    fails.append("evidence[%s]: excerpt missing kind/paraphrase" % sig)
        # (d) REDACTION proven: NO full path / home dir / drive / secret in any
        #     paraphrase. EP2 edited a full Windows home path -> must be basename-only.
        leak_re = re.compile(
            r"([A-Za-z]:[\\/]|/[Uu]sers/|/home/|\\Users\\|[0-9a-f]{8}-[0-9a-f]{4}"
            r"|\.env\b|AKIA[0-9A-Z]{8}|[A-Za-z0-9_\-]{32,})")
        for sig, rows in ev.items():
            for r in rows:
                if leak_re.search(r["paraphrase"]):
                    fails.append("evidence[%s]: REDACTION LEAK in paraphrase: %r"
                                 % (sig, r["paraphrase"]))
        # EP2's blind-edit basename must be present + stripped to bare 'b.py'.
        if not any("b.py" in r["paraphrase"] for r in ib):
            fails.append("evidence: inspect excerpt should name basename 'b.py'")
        # (e) global cap respected.
        total_ex = sum(len(v) for v in ev.values())
        if total_ex > GLOBAL_EXCERPT_CAP:
            fails.append("evidence: total %d exceeds global cap %d"
                         % (total_ex, GLOBAL_EXCERPT_CAP))

    # ---- redaction helper unit checks (path strip + bash verb + secret drop) ----
    if _basename("C:\\Users\\me\\src\\core\\engine.py") != "engine.py":
        fails.append("redact: _basename failed to strip Windows home path")
    if _basename("/home/me/proj/config/x.ts") != "x.ts":
        fails.append("redact: _basename failed to strip POSIX home path")
    if _bash_verb("python -m pytest tests/ -q") != "python":
        fails.append("redact: _bash_verb misclassified python")
    if _bash_verb("export API_KEY=sk-abc1234567890abcdef1234567890abcd") is not None:
        fails.append("redact: _bash_verb did NOT drop a secret-shaped command")
    if _safe("token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") != "[redacted]":
        fails.append("redact: _safe did NOT scrub a secret-shaped token")

    # ---- LITE MODE: --max-excerpts 0 yields ZERO excerpts (counts unchanged) ----
    out_lite = build_output(episodes, agg, meta, cap_seen, ts,
                            sampled=[("synthetic", 0.0)], sub_sampled=False,
                            sessions_read=1, sessions_total=1, max_excerpts=0)
    if out_lite["evidence_excerpts"] != {}:
        fails.append("lite-mode: --max-excerpts 0 must yield {} excerpts")
    # counts are ADDITIVE-invariant: lite vs full agree bit-for-bit on all counts.
    if out_lite["aggregate_counts"] != out["aggregate_counts"]:
        fails.append("lite-mode: aggregate_counts differ from full run (not additive)")
    if out_lite["episode_partitions"] != out["episode_partitions"]:
        fails.append("lite-mode: episode_partitions differ from full run")

    if fails:
        sys.stderr.write("SELFTEST FAILED:\n  " + "\n  ".join(fails) + "\n")
        return 1
    print("OK agentcraft_extract self-test: 4 episodes, partition sums, containment, "
          "ceiling, capability-gating, known-answer counts, curated evidence "
          "(bounded + redacted + real episodes), lite-mode, redaction helpers all hold")
    return 0


# --------------------------------------------------------------------------- #
# CLI.                                                                          #
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="agentcraft_extract.py",
        description="AGENTCRAFT local signal extractor (Step 1). Streams your Claude "
                    "Code history and emits per-episode partition counts. 100%% "
                    "local, zero network.")
    ap.add_argument("--project", default="auto",
                    help="project slug under ~/.claude/projects (or 'auto' to pick "
                         "the most recently active). A substring is tolerated.")
    ap.add_argument("--window-days", type=int, default=None,
                    help="(reserved) informational window hint; scanning is by "
                         "session file, timestamps are reported as-found.")
    ap.add_argument("--max-sessions", type=int, default=8,
                    help="how many of the LARGEST sessions to stream in full "
                         "(0 = all). The giant session is NEVER byte-capped.")
    ap.add_argument("--repo", default=None,
                    help="path to the repo whose discipline surface (CLAUDE.md / "
                         ".claude/skills / hooks / memory) to inventory for P6/P7. "
                         "Default: current dir. The GLOBAL ~/.claude config is ALWAYS "
                         "also scanned, so P7 is measured from real files.")
    ap.add_argument("--max-excerpts", type=int, default=MAX_EXCERPTS_PER_SIGNAL,
                    help="max curated REDACTED evidence excerpts per WEAK "
                         "sub-signal (default %d; a hard global cap of %d always "
                         "applies). 0 = counts-only LITE MODE (no excerpts curated) "
                         "for the privacy-paranoid -- honest, shallower, your choice."
                         % (MAX_EXCERPTS_PER_SIGNAL, GLOBAL_EXCERPT_CAP))
    ap.add_argument("--out", default="-",
                    help="output JSON path, or '-' for stdout (default).")
    ap.add_argument("--selftest", "--self-test", dest="selftest",
                    action="store_true",
                    help="run the offline synthetic self-test and exit.")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    proj_dir, all_files = resolve_project(args.project)
    if not all_files:
        root = projects_root()
        sys.stderr.write(
            "No session history found.\n"
            "  Looked under: %s\n"
            "  Pass --project <slug> or run from a machine with Claude Code history.\n"
            "  (Run `python agentcraft_extract.py --selftest` to verify the tool itself.)\n"
            % root)
        return 3

    files = pick_files(all_files, args.max_sessions)
    sampled = [(os.path.basename(p)[:10], round(os.path.getsize(p) / 1e6, 1))
               for p in files]
    sub_sampled = len(files) < len(all_files)

    episodes, agg, meta, cap_seen, ts = scan_files(files, args.window_days)

    # Discipline surface (P6/P7): inventory the REAL on-disk config -- repo-local +
    # GLOBAL ~/.claude -- so `configuration` is measured from files, not from whether
    # the chat happened to open CLAUDE.md. This decouples the config scan from the
    # chat-project slug (closes the "P7 gated-out when run outside the repo" gap).
    repo_path = os.path.abspath(args.repo) if args.repo else os.getcwd()
    surface = scan_discipline_surface(repo_path)
    if surface["has_config"]:
        cap_seen.add("configuration")   # P7 now measurable from real files

    out = build_output(episodes, agg, meta, cap_seen, ts,
                       sampled=sampled, sub_sampled=sub_sampled,
                       sessions_read=len(files), sessions_total=len(all_files),
                       max_excerpts=args.max_excerpts)
    out["subject"] = {"project_slug": os.path.basename(proj_dir)}
    out["discipline_surface"] = surface

    payload = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(payload)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        sys.stderr.write("wrote %s (%d episodes, %d sessions)\n"
                         % (args.out, len(episodes), len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
