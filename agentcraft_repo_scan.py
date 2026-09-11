#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGENTCRAFT repo scanner  --  Lens B (your CODE) Step 1, the mechanical COUNTS pass.

WHAT IT IS
  A pure-stdlib, 100% LOCAL walker of ANY repo on disk. It streams every source
  file line by line and tallies observable code-quality CUES across 8 axes
  (C1..C8, grounded in ISO/IEC 25010 + SonarQube's bug/coverage/maintainability
  lenses) -- so the judging agent scores FROM COUNTS (a falsifiable partition),
  never from vibes. It is the CODE twin of `agentcraft_extract.py` (which does the
  same COUNTS-only pass for Lens A: how you WORK with agents).

WHAT IT IS NOT
  It does NOT score, grade, or judge -- that is the agent's job (SKILL.md, Lens B).
  It NEVER sends a byte anywhere. There is no network primitive in this file.
  It NEVER echoes a secret VALUE -- C3 reports secret COUNTS only, never the text.
  Grep it yourself:  grep -niE "requests|urllib|socket|http|urlopen|fetch" agentcraft_repo_scan.py

CONTRACT
  * Emits a mechanical COUNTS JSON: top-level `languages`, `total_files`,
    `total_loc`, plus a per-axis dict of raw counts (`axes.C1`..`axes.C8`).
  * Deterministic: no `Date.now`, no wall-clock in the numbers. `scanned_at` is a
    caller-filled placeholder (default null) so two runs on the same tree agree
    bit-for-bit -- exactly the determinism discipline of the Lens-A extractor.
  * SCORES NOTHING. Counts -> score mapping is the user's own Claude (privacy +
    determinism), same division of labour as Lens A.

DESIGN
  A single-file, argparse-driven, portable tool: point it at a repo path, it walks
  the tree (skipping .git / node_modules / .venv / dist / build / __pycache__ and
  friends), classifies each file by extension, streams it once collecting the cues,
  and emits the counts -- with a built-in --self-test that builds a tiny synthetic
  fixture repo with KNOWN counts, scans it, and asserts the math (incl. that a fake
  secret is COUNTED but never ECHOED).

  Heuristics are language-agnostic where possible and special-cased for
  py/js/ts/jsx/tsx/go/rust/java. Python complexity uses the stdlib `ast` module,
  guarded so a non-Python repo (or an unparseable file) still scans cleanly.

Imports (stdlib ONLY, zero-egress): argparse, ast, collections, json, os, re, sys,
  tempfile. There is NO network primitive anywhere in this file -- no requests,
  urllib, socket, http.client, urlopen, or fetch.

Windows: run with `python` (not python3). ASCII-only output. No third-party imports.
License: MIT (same as the project).
"""

import argparse
import ast
import collections
import json
import os
import re
import sys
import tempfile


# --------------------------------------------------------------------------- #
# Tunables -- the "> N lines" thresholds (data, not code). The agent may re-band #
# on read; these are just where the extractor draws a mechanical tally line.     #
# --------------------------------------------------------------------------- #
LARGE_FILE_LINES = 400        # a file over this many lines is a "large file" count
LARGE_FUNC_LINES = 50         # a function/def over this many lines is a "large func"
DEEP_NESTING_COLS = 24        # leading-indent columns treated as "deep nesting"
DUP_BLOCK_LINES = 6           # sliding window size for the duplication heuristic
README_SMALL_BYTES = 400      # a README below this is a "stub" (present-but-thin)


# --------------------------------------------------------------------------- #
# Directory + file classification (data-driven; mirrors the Lens-A cue vocab).  #
# --------------------------------------------------------------------------- #

# Noise dirs skipped wholesale (never walked). Mirrors .gitignore-style noise.
SKIP_DIRS = frozenset((
    ".git", "node_modules", ".venv", "venv", "env", "dist", "build",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".cache",
    ".next", ".nuxt", ".svelte-kit", "out", "coverage", ".turbo", ".parcel-cache",
    "vendor", "target", "bin", "obj", ".idea", ".vscode", ".gradle",
    "site-packages", ".tox", ".eggs", "bower_components", ".terraform",
))

# Extension -> language label. Anything else is "other" (still counted in totals).
EXT_LANG = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin",
    ".rb": "ruby", ".php": "php", ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".swift": "swift", ".scala": "scala", ".sh": "shell", ".bash": "shell",
    ".sql": "sql", ".vue": "vue", ".svelte": "svelte",
    ".css": "css", ".scss": "css", ".less": "css",
    ".html": "html", ".md": "markdown", ".json": "json",
    ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
}

# The extensions we treat as "source code" for LOC/complexity heuristics (as
# opposed to markup/config which we still count in totals but don't complexity-scan).
CODE_LANGS = frozenset((
    "python", "javascript", "typescript", "go", "rust", "java", "kotlin",
    "ruby", "php", "c", "cpp", "csharp", "swift", "scala", "shell", "vue",
    "svelte",
))

# A file is a TEST file if its path/name matches any of these (language-agnostic).
_TEST_NAME_RE = re.compile(
    r"(?i)(?:^|[\\/])(?:tests?|__tests__|spec|specs)[\\/]"
    r"|(?:\.|_|-)(?:test|spec)\.[a-z0-9]+$"
    r"|(?:^|[\\/])test_[^\\/]+\.py$"
    r"|_test\.(?:go|py|rb)$")

# Dependency manifests we look for at the repo root (presence + rough dep count).
MANIFESTS = (
    "package.json", "requirements.txt", "pyproject.toml", "setup.py",
    "setup.cfg", "Pipfile", "go.mod", "Cargo.toml", "pom.xml",
    "build.gradle", "Gemfile", "composer.json",
)
# Lockfiles -> pinned-dependency discipline signal.
LOCKFILES = (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "go.sum", "Cargo.lock", "composer.lock", "Gemfile.lock",
    "requirements.lock",
)
# CI config globs -> a CI pipeline exists (feeds C4 tests + C8 techdebt).
CI_GLOBS = (
    ".github/workflows", ".gitlab-ci.yml", ".circleci", "azure-pipelines.yml",
    "Jenkinsfile", ".travis.yml", "bitbucket-pipelines.yml",
)
# Test-framework config hints (presence anywhere feeds C4).
TEST_CONFIG_NAMES = (
    "pytest.ini", "tox.ini", "jest.config.js", "jest.config.ts",
    "vitest.config.ts", "vitest.config.js", "karma.conf.js",
    "phpunit.xml", ".mocharc.json", "conftest.py",
)


# --------------------------------------------------------------------------- #
# C2 -- risky error-handling cues (language-agnostic regexes over source lines). #
# COUNTS ONLY. We tally risky constructs vs handling constructs.                 #
# --------------------------------------------------------------------------- #
_RE_BARE_EXCEPT = re.compile(r"^\s*except\s*:")                    # python bare except
_RE_BROAD_EXCEPT = re.compile(r"^\s*except\s+(?:Exception|BaseException)\b")
_RE_EMPTY_CATCH = re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}")       # js/ts/java empty catch
_RE_CATCH = re.compile(r"\bcatch\s*\(")                           # any catch site
_RE_TRY = re.compile(r"^\s*try\b|\btry\s*\{")                     # any try site
_RE_TS_IGNORE = re.compile(r"@ts-ignore|@ts-nocheck")
_RE_NOQA_BLANKET = re.compile(r"#\s*noqa(?!:)")                   # blanket noqa (no code)
_RE_ESLINT_DISABLE = re.compile(r"eslint-disable(?!-next-line-[a-z])")
_RE_SWALLOW = re.compile(r"except[^\n:]*:\s*pass\b|catch\s*\([^)]*\)\s*\{\s*(?:/\*.*?\*/\s*)?\}")
_RE_PANIC_UNWRAP = re.compile(r"\.unwrap\(\)|\.expect\(")         # rust risky unwrap
_RE_ERR_IGNORE_GO = re.compile(r"_\s*[,)]?\s*[:=]\s*[^=].*\berr\b|_\s*=\s*.*\(")  # loose

# Risky call sites: I/O / parse / network-ish calls that WANT a guard.
_RE_RISKY_CALL = re.compile(
    r"\b(?:open|json\.loads|json\.load|requests\.\w+|fetch|axios|"
    r"parseInt|parseFloat|JSON\.parse|int\(|float\(|subprocess\.|os\.remove|"
    r"os\.system|readFileSync|writeFileSync)\s*\(")


# --------------------------------------------------------------------------- #
# C3 -- secret + dangerous-primitive cues. COUNTS ONLY -- NEVER the value.       #
# The regexes MATCH secret-shaped strings but we emit ONLY a count; the matched  #
# text never leaves this process. This is the C3 privacy invariant.             #
# --------------------------------------------------------------------------- #
# Secret-shaped assignments / literals (broad, conservative -> counts, not proof).
_RE_SECRET = re.compile(
    r"(?i)(?:api[_-]?key|secret|passwd|password|access[_-]?token|auth[_-]?token"
    r"|client[_-]?secret|private[_-]?key)\s*[:=]\s*['\"][^'\"]{6,}['\"]"
    r"|AKIA[0-9A-Z]{16}"                                    # AWS access key id
    r"|sk-[A-Za-z0-9]{16,}"                                 # openai-style key
    r"|gh[pousr]_[A-Za-z0-9]{20,}"                          # github token
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"                  # PEM private key
    r"|xox[baprs]-[A-Za-z0-9-]{10,}")                       # slack token
# Dangerous execution / injection primitives.
_RE_EVAL = re.compile(r"\beval\s*\(")
_RE_EXEC = re.compile(r"\bexec\s*\(")
_RE_SHELL_TRUE = re.compile(r"shell\s*=\s*True")
_RE_DANGEROUS_HTML = re.compile(r"dangerouslySetInnerHTML")
_RE_CHILD_PROCESS = re.compile(
    r"\bchild_process\b|\bsubprocess\.(?:call|run|Popen)|\bos\.system\s*\(")


# --------------------------------------------------------------------------- #
# C6 -- performance-efficiency cues (best-effort, per-line + small look-around). #
# --------------------------------------------------------------------------- #
_RE_LOOP = re.compile(r"^\s*(?:for|while)\b|\.forEach\s*\(|\.map\s*\(")
_RE_AWAIT = re.compile(r"\bawait\b")
_RE_QUERY_CALL = re.compile(
    r"(?i)\b(?:query|execute|fetch|select|find|findOne|get|aggregate|"
    r"request|axios|http)\s*\(")


# C5/C8 -- TODO/FIXME density.
_RE_TODO = re.compile(r"(?i)\b(?:TODO|FIXME|XXX|HACK)\b")

# C7 -- comment + docstring density (language-agnostic single-line comment starts).
_RE_LINE_COMMENT = re.compile(r"^\s*(?://|#|--|;|/\*|\*)")
# Single-character identifier density (naming signal), excluding common loop vars.
_RE_SINGLE_CHAR_ID = re.compile(r"\b([a-z])\s*=(?!=)")


# --------------------------------------------------------------------------- #
# File streaming.                                                               #
# --------------------------------------------------------------------------- #

def _iter_lines(path):
    """Stream a file line by line -- memory-safe even for a large source file.
    Tolerant: an unreadable file yields nothing, never fatal."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                yield line.rstrip("\n")
    except OSError:
        return


def classify_ext(name):
    """basename -> (ext, language_label). Unknown ext -> ('', 'other')."""
    ext = os.path.splitext(name)[1].lower()
    return ext, EXT_LANG.get(ext, "other")


def is_test_file(relpath):
    """Language-agnostic test-file detection from the RELATIVE path."""
    return bool(_TEST_NAME_RE.search(relpath.replace("\\", "/")))


def _leading_cols(line):
    """Leading indentation width in columns (a tab counts as 4). For nesting est."""
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += 4
        else:
            break
    return n


# --------------------------------------------------------------------------- #
# Python-specific complexity via ast (guarded -- non-Python or unparseable       #
# files silently contribute nothing here, so the scanner is language-agnostic).  #
# --------------------------------------------------------------------------- #

def _python_ast_metrics(source):
    """Return (functions, large_functions, max_func_lines, circular_hint_names).
    circular_hint_names = the module-name prefixes this file imports FROM (for a
    cheap intra-repo circular-import hint at the aggregate level). Never raises."""
    funcs = 0
    large = 0
    max_len = 0
    imports = set()
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return funcs, large, max_len, imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs += 1
            end = getattr(node, "end_lineno", None)
            if end is not None:
                length = end - node.lineno + 1
                max_len = max(max_len, length)
                if length > LARGE_FUNC_LINES:
                    large += 1
        elif isinstance(node, ast.Import):
            for a in node.names:
                imports.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return funcs, large, max_len, imports


def _generic_func_count(lines, lang):
    """Best-effort function tally for non-Python code (brace/keyword heuristic).
    Returns (functions, large_functions, max_func_lines). Never exact -- a COUNT."""
    funcs = 0
    large = 0
    max_len = 0
    # Function-declaration line patterns per broad language family.
    if lang in ("javascript", "typescript", "vue", "svelte"):
        decl = re.compile(
            r"\bfunction\b|\)\s*=>\s*\{|\b(?:async\s+)?[A-Za-z_$][\w$]*\s*\([^)]*\)\s*\{")
    elif lang in ("go",):
        decl = re.compile(r"^\s*func\b")
    elif lang in ("rust",):
        decl = re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\b")
    elif lang in ("java", "csharp", "kotlin", "scala", "swift", "cpp", "c"):
        decl = re.compile(
            r"^\s*(?:public|private|protected|static|final|override|func|def|fun|"
            r"[A-Za-z_][\w<>\[\]]*)\s+[A-Za-z_]\w*\s*\([^;]*\)\s*\{?")
    else:
        decl = None
    if decl is None:
        return funcs, large, max_len
    # Track brace balance to estimate each function's line span.
    open_at = None
    depth = 0
    for i, ln in enumerate(lines):
        if decl.search(ln) and open_at is None and "{" in ln:
            open_at = i
            depth = ln.count("{") - ln.count("}")
            funcs += 1
            if depth <= 0:  # one-liner
                open_at = None
            continue
        if open_at is not None:
            depth += ln.count("{") - ln.count("}")
            if depth <= 0:
                length = i - open_at + 1
                max_len = max(max_len, length)
                if length > LARGE_FUNC_LINES:
                    large += 1
                open_at = None
    return funcs, large, max_len


def _dup_ratio(lines):
    """Duplication heuristic: fraction of DUP_BLOCK_LINES-windows that repeat a
    previously-seen normalized block. A COUNT-derived ratio (0..1), best-effort."""
    norm = [re.sub(r"\s+", " ", ln).strip() for ln in lines
            if ln.strip() and not _RE_LINE_COMMENT.match(ln)]
    if len(norm) < DUP_BLOCK_LINES * 2:
        return 0.0, 0
    seen = set()
    dup_windows = 0
    total_windows = 0
    for i in range(len(norm) - DUP_BLOCK_LINES + 1):
        block = "\n".join(norm[i:i + DUP_BLOCK_LINES])
        total_windows += 1
        if block in seen:
            dup_windows += 1
        else:
            seen.add(block)
    ratio = round(dup_windows / total_windows, 4) if total_windows else 0.0
    return ratio, dup_windows


# --------------------------------------------------------------------------- #
# The 8-axis accumulator.                                                       #
# --------------------------------------------------------------------------- #

class Counts(object):
    """Mutable bag of the mechanical tallies for every axis. Flat + additive so
    the self-test can assert on it and the agent can read it 1:1."""

    def __init__(self):
        self.c = collections.Counter()
        self.languages = collections.Counter()
        self.dir_files = collections.Counter()          # files per directory
        self.max_dir_depth = 0
        self.total_files = 0
        self.total_loc = 0
        self.largest_files = []                          # (loc, relpath) heap-ish
        self.py_imports = collections.Counter()          # module -> times imported
        self.py_modules = set()                          # top-level python module names
        self.import_edges = []                           # (file_module, imported) for circ hint

    def note_large_file(self, loc, relpath):
        self.largest_files.append((loc, relpath))
        # keep only the top 10 by loc (bounded output)
        self.largest_files.sort(reverse=True)
        del self.largest_files[10:]


def scan_repo(repo_path):
    """Walk `repo_path`, stream every file once, and return a Counts bag.
    Skips SKIP_DIRS. 100% local, read-only, streaming."""
    counts = Counts()
    repo_path = os.path.abspath(repo_path)

    for root, dirs, files in os.walk(repo_path):
        # prune noise dirs in-place (exact-match only -- do NOT prune .github etc.)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = os.path.relpath(root, repo_path)
        depth = 0 if rel_root == "." else rel_root.replace("\\", "/").count("/") + 1
        counts.max_dir_depth = max(counts.max_dir_depth, depth)

        for name in files:
            fpath = os.path.join(root, name)
            relpath = os.path.relpath(fpath, repo_path).replace("\\", "/")
            ext, lang = classify_ext(name)
            counts.total_files += 1
            counts.languages[lang] += 1
            counts.dir_files[rel_root] += 1

            # C1: layering hint dirs (presence of common architecture folders).
            _accumulate_file(counts, fpath, relpath, name, ext, lang)

    _finalize_layering_and_circular(counts, repo_path)
    return counts


def _accumulate_file(counts, fpath, relpath, name, ext, lang):
    """Stream ONE file and fold its cues into `counts`. The heart of the scanner."""
    is_code = lang in CODE_LANGS
    is_test = is_test_file(relpath)
    lines = list(_iter_lines(fpath)) if (is_code or ext in (".json", ".md")) else None

    loc = len(lines) if lines is not None else _quick_linecount(fpath)
    counts.total_loc += loc

    if is_code:
        counts.c["code_files"] += 1
        counts.c["code_loc"] += loc
        if is_test:
            counts.c["test_files"] += 1
            counts.c["test_loc"] += loc
        else:
            counts.c["source_files"] += 1
            counts.c["source_loc"] += loc
        if loc > LARGE_FILE_LINES:
            counts.c["large_files"] += 1
            counts.note_large_file(loc, relpath)

    if lines is None:
        return

    # ---- per-line cue sweep (single pass over the file's lines) ----
    blank = 0
    comment_lines = 0
    single_char_ids = 0
    deep_nesting = 0
    todo = 0
    loop_stack = []          # indent cols where a loop opened (nested-loop est.)
    nested_loops = 0
    await_in_loop = 0
    query_in_loop = 0

    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            blank += 1
            continue

        # C7 comments + naming (code files only -- a markdown '#' is a heading,
        # not a code comment, and would pollute the comment-to-code ratio).
        if is_code:
            if _RE_LINE_COMMENT.match(ln):
                comment_lines += 1
            if _RE_SINGLE_CHAR_ID.search(ln):
                single_char_ids += 1

        # C5/C8 TODO -- language-agnostic (a TODO in a doc is still tech debt).
        if _RE_TODO.search(ln):
            todo += 1

        # ---- the code-quality cue sweep runs ONLY on actual source files. ----
        # Markdown/JSON/HTML are streamed for LOC + comments + TODO only; running
        # the error-handling/security/loop regexes over prose or inline-code spans
        # produces false positives (a `catch` in a README is not a swallowed error).
        if not is_code:
            continue

        # C5 nesting (source only)
        cols = _leading_cols(ln)
        if cols >= DEEP_NESTING_COLS:
            deep_nesting += 1

        # C6 loop / nested-loop / sync-in-async / N+1 hints
        if _RE_LOOP.search(ln):
            # a loop opening deeper than an existing loop => nested
            while loop_stack and cols <= loop_stack[-1]:
                loop_stack.pop()
            if loop_stack:
                nested_loops += 1
            loop_stack.append(cols)
        elif loop_stack and cols <= loop_stack[-1] and stripped:
            while loop_stack and cols <= loop_stack[-1]:
                loop_stack.pop()
        if loop_stack:
            if _RE_AWAIT.search(ln):
                await_in_loop += 1
            if _RE_QUERY_CALL.search(ln):
                query_in_loop += 1

        # ---- C2 error handling ----
        if _RE_BARE_EXCEPT.search(ln):
            counts.c["c2_bare_except"] += 1
        if _RE_BROAD_EXCEPT.search(ln):
            counts.c["c2_broad_except"] += 1
        if _RE_EMPTY_CATCH.search(ln):
            counts.c["c2_empty_catch"] += 1
        if _RE_CATCH.search(ln):
            counts.c["c2_catch_sites"] += 1
        if _RE_TRY.search(ln):
            counts.c["c2_try_sites"] += 1
        if _RE_TS_IGNORE.search(ln):
            counts.c["c2_ts_ignore"] += 1
        if _RE_NOQA_BLANKET.search(ln):
            counts.c["c2_noqa_blanket"] += 1
        if _RE_ESLINT_DISABLE.search(ln):
            counts.c["c2_eslint_disable"] += 1
        if _RE_SWALLOW.search(ln):
            counts.c["c2_swallowed_errors"] += 1
        if lang == "rust" and _RE_PANIC_UNWRAP.search(ln):
            counts.c["c2_rust_unwrap_expect"] += 1
        if _RE_RISKY_CALL.search(ln):
            counts.c["c2_risky_call_sites"] += 1

        # ---- C3 security -- COUNTS ONLY, value never captured ----
        if _RE_SECRET.search(ln):
            counts.c["c3_secret_hits"] += 1          # count ONLY; matched text discarded
        if _RE_EVAL.search(ln):
            counts.c["c3_eval"] += 1
        if _RE_EXEC.search(ln):
            counts.c["c3_exec"] += 1
        if _RE_SHELL_TRUE.search(ln):
            counts.c["c3_shell_true"] += 1
        if _RE_DANGEROUS_HTML.search(ln):
            counts.c["c3_dangerous_html"] += 1
        if _RE_CHILD_PROCESS.search(ln):
            counts.c["c3_child_process"] += 1

    counts.c["c5_nested_loops"] += nested_loops
    counts.c["c6_await_in_loop"] += await_in_loop
    counts.c["c6_query_in_loop"] += query_in_loop
    counts.c["c5_deep_nesting_lines"] += deep_nesting
    counts.c["c5_todo_fixme"] += todo
    counts.c["c8_todo_fixme"] += todo
    counts.c["c7_comment_lines"] += comment_lines
    counts.c["c7_blank_lines"] += blank
    counts.c["c7_single_char_ids"] += single_char_ids

    # ---- per-file complexity (functions, large functions, duplication) ----
    if is_code and not is_test:
        source = "\n".join(lines)
        if lang == "python":
            funcs, large_fn, max_fn, imports = _python_ast_metrics(source)
            mod = _py_module_name(relpath)
            if mod:
                counts.py_modules.add(mod)
                for imp in imports:
                    counts.py_imports[imp] += 1
                    counts.import_edges.append((mod, imp))
        else:
            funcs, large_fn, max_fn = _generic_func_count(lines, lang)
        counts.c["c5_functions"] += funcs
        counts.c["c5_large_functions"] += large_fn
        counts.c["c5_max_function_lines"] = max(
            counts.c["c5_max_function_lines"], max_fn)
        ratio, dup_windows = _dup_ratio(lines)
        counts.c["c5_dup_windows"] += dup_windows


def _quick_linecount(path):
    """Cheap line count for files we don't full-stream. Tolerant of binary."""
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _py_module_name(relpath):
    """A python file's rel path -> a dotted top-level module hint (for circ. graph)."""
    p = relpath[:-3] if relpath.endswith(".py") else relpath
    p = p.replace("/", ".")
    if p.endswith(".__init__"):
        p = p[:-len(".__init__")]
    return p.split(".")[0] if p else ""


def _finalize_layering_and_circular(counts, repo_path):
    """Compute the C1 layering hints + a cheap circular-import hint (python)."""
    # Layering hint: presence of conventional architecture directories.
    layering = []
    hint_dirs = ("src", "lib", "core", "app", "domain", "services", "controllers",
                 "models", "views", "components", "api", "utils", "internal",
                 "pkg", "cmd", "packages", "modules")
    present = set()
    for root, dirs, _files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        base = os.path.basename(root)
        if base in hint_dirs:
            present.add(base)
    layering = sorted(present)
    counts.c["c1_layering_dirs"] = len(layering)
    counts._layering = layering  # stash for output

    # Circular-import hint (python only, aggregate): count import edges whose
    # target is ALSO a local module -> a potential cycle surface. This is a COUNT
    # hint (not a proof); the agent inspects if it matters.
    local = counts.py_modules
    intra = 0
    reciprocal = 0
    edge_set = set(counts.import_edges)
    for src_mod, tgt in counts.import_edges:
        if tgt in local:
            intra += 1
            if (tgt, src_mod) in edge_set and src_mod != tgt:
                reciprocal += 1
    counts.c["c1_intra_repo_import_edges"] = intra
    counts.c["c1_reciprocal_import_pairs"] = reciprocal // 2  # each pair counted twice


# --------------------------------------------------------------------------- #
# Repo-root inventory (manifests, lockfiles, CI, LICENSE, README, .env) -- C3/   #
# C4/C7/C8. Presence + rough sizes only; never the file BODY (esp. never .env).  #
# --------------------------------------------------------------------------- #

def scan_root_inventory(repo_path):
    """Inventory root-level discipline artifacts. Returns a dict of presence flags
    + rough counts. 100% local; reads names + sizes + a manifest's dep COUNT only
    (never a secret body -- a committed .env is a COUNT + a flag, never its text)."""
    repo_path = os.path.abspath(repo_path)
    inv = {
        "manifests": [], "lockfiles": [], "ci_present": False,
        "license_present": False, "readme_present": False,
        "readme_bytes": 0, "readme_stub": False,
        "env_committed": False, "test_config_present": False,
        "dependency_count": 0, "pinned_dep_hint": None,
    }

    def exists(rel):
        return os.path.exists(os.path.join(repo_path, rel))

    for m in MANIFESTS:
        if exists(m):
            inv["manifests"].append(m)
    for lf in LOCKFILES:
        if exists(lf):
            inv["lockfiles"].append(lf)
    for c in CI_GLOBS:
        if exists(c):
            inv["ci_present"] = True
            break
    for tc in TEST_CONFIG_NAMES:
        if exists(tc):
            inv["test_config_present"] = True
            break

    # LICENSE (any casing / extension)
    for lic in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "license"):
        if exists(lic):
            inv["license_present"] = True
            break

    # README present + size + stub flag
    for rd in ("README.md", "README.rst", "README.txt", "README", "readme.md"):
        p = os.path.join(repo_path, rd)
        if os.path.isfile(p):
            inv["readme_present"] = True
            try:
                inv["readme_bytes"] = os.path.getsize(p)
            except OSError:
                inv["readme_bytes"] = 0
            inv["readme_stub"] = 0 < inv["readme_bytes"] < README_SMALL_BYTES
            break

    # .env committed? (a real .env in the tree -- a security COUNT, never its body)
    for env_name in (".env", ".env.local", ".env.production", ".env.development"):
        if os.path.isfile(os.path.join(repo_path, env_name)):
            inv["env_committed"] = True
            break

    inv["dependency_count"], inv["pinned_dep_hint"] = _estimate_deps(repo_path, inv)
    return inv


def _estimate_deps(repo_path, inv):
    """Rough dependency COUNT + a pinned-vs-floating HINT, from manifests only.
    Never executes anything; parses names/counts, tolerant of malformed files."""
    dep_count = 0
    pinned = None

    def read(rel):
        try:
            with open(os.path.join(repo_path, rel), encoding="utf-8",
                      errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""

    if "package.json" in inv["manifests"]:
        try:
            pkg = json.loads(read("package.json") or "{}")
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                deps = pkg.get(key) or {}
                if isinstance(deps, dict):
                    dep_count += len(deps)
                    # floating if any version starts with ^ or ~ or *
                    if any(str(v).lstrip().startswith(("^", "~", "*"))
                           for v in deps.values()):
                        pinned = False
        except (ValueError, TypeError):
            pass
    if "requirements.txt" in inv["manifests"]:
        floating = False
        for raw in read("requirements.txt").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                dep_count += 1
                if "==" not in line and ">" not in line and "<" not in line:
                    floating = True
        if floating and pinned is None:
            pinned = False
    if "pyproject.toml" in inv["manifests"]:
        # cheap: count dependency-looking lines inside a [dependencies] / deps array
        body = read("pyproject.toml")
        dep_count += len(re.findall(r'^\s*["\']?[A-Za-z0-9_.-]+["\']?\s*[=><~]',
                                    body, re.MULTILINE))
    if pinned is None and inv["lockfiles"]:
        pinned = True   # a lockfile present => effectively pinned
    return dep_count, pinned


# --------------------------------------------------------------------------- #
# Assemble the 8-axis COUNTS output the agent consumes.                         #
# --------------------------------------------------------------------------- #

def build_output(counts, inv, repo_path, scanned_at=None):
    """Roll the raw Counts + root inventory into the documented 8-axis JSON.
    SCORES NOTHING. Every value is a mechanical count / ratio / presence flag."""
    c = counts.c
    code_files = c["code_files"]
    source_files = c["source_files"]
    test_files = c["test_files"]
    source_loc = c["source_loc"]
    test_loc = c["test_loc"]
    n_dirs = len(counts.dir_files) or 1

    axes = {
        # C1 architecture & structure -----------------------------------------
        "C1_architecture_structure": {
            "module_dirs": len(counts.dir_files),
            "total_files": counts.total_files,
            "avg_files_per_dir": round(counts.total_files / n_dirs, 2),
            "max_dir_depth": counts.max_dir_depth,
            "layering_dirs_present": getattr(counts, "_layering", []),
            "layering_dir_count": c["c1_layering_dirs"],
            "intra_repo_import_edges": c["c1_intra_repo_import_edges"],
            "circular_import_pairs_hint": c["c1_reciprocal_import_pairs"],
            "largest_files": [{"loc": loc, "path": p}
                              for loc, p in counts.largest_files],
        },
        # C2 reliability & error handling -------------------------------------
        "C2_reliability_errorhandling": {
            "bare_except": c["c2_bare_except"],
            "broad_except": c["c2_broad_except"],
            "empty_catch": c["c2_empty_catch"],
            "swallowed_errors": c["c2_swallowed_errors"],
            "catch_sites": c["c2_catch_sites"],
            "try_sites": c["c2_try_sites"],
            "ts_ignore": c["c2_ts_ignore"],
            "noqa_blanket": c["c2_noqa_blanket"],
            "eslint_disable": c["c2_eslint_disable"],
            "rust_unwrap_expect": c["c2_rust_unwrap_expect"],
            "risky_call_sites": c["c2_risky_call_sites"],
        },
        # C3 security & secrets (COUNTS ONLY -- never a value) -----------------
        "C3_security_secrets": {
            "secret_pattern_hits": c["c3_secret_hits"],
            "_note": "COUNTS ONLY -- secret VALUES are never captured or emitted.",
            "env_committed": inv["env_committed"],
            "eval_calls": c["c3_eval"],
            "exec_calls": c["c3_exec"],
            "shell_true": c["c3_shell_true"],
            "dangerously_set_inner_html": c["c3_dangerous_html"],
            "child_process_calls": c["c3_child_process"],
        },
        # C4 tests & coverage --------------------------------------------------
        "C4_tests_coverage": {
            "test_files": test_files,
            "source_files": source_files,
            "test_to_source_file_ratio": (round(test_files / source_files, 3)
                                          if source_files else None),
            "test_loc": test_loc,
            "source_loc": source_loc,
            "test_to_source_loc_ratio": (round(test_loc / source_loc, 3)
                                         if source_loc else None),
            "test_config_present": inv["test_config_present"],
            "ci_present": inv["ci_present"],
        },
        # C5 maintainability & complexity -------------------------------------
        "C5_maintainability_complexity": {
            "large_files": c["large_files"],
            "large_file_threshold_lines": LARGE_FILE_LINES,
            "functions": c["c5_functions"],
            "large_functions": c["c5_large_functions"],
            "large_function_threshold_lines": LARGE_FUNC_LINES,
            "max_function_lines": c["c5_max_function_lines"],
            "deep_nesting_lines": c["c5_deep_nesting_lines"],
            "nested_loops": c["c5_nested_loops"],
            "duplicate_block_windows": c["c5_dup_windows"],
            "duplicate_block_window_lines": DUP_BLOCK_LINES,
            "todo_fixme": c["c5_todo_fixme"],
        },
        # C6 performance efficiency (best-effort) ------------------------------
        "C6_performance_efficiency": {
            "nested_loops": c["c5_nested_loops"],
            "await_in_loop": c["c6_await_in_loop"],
            "query_or_fetch_in_loop_hint": c["c6_query_in_loop"],
        },
        # C7 documentation & readability --------------------------------------
        "C7_documentation_readability": {
            "readme_present": inv["readme_present"],
            "readme_bytes": inv["readme_bytes"],
            "readme_stub": inv["readme_stub"],
            "comment_lines": c["c7_comment_lines"],
            "blank_lines": c["c7_blank_lines"],
            "code_loc": c["code_loc"],
            "comment_to_code_ratio": (round(c["c7_comment_lines"] / c["code_loc"], 3)
                                      if c["code_loc"] else None),
            "single_char_identifier_lines": c["c7_single_char_ids"],
        },
        # C8 dependencies & tech debt -----------------------------------------
        "C8_dependencies_techdebt": {
            "manifests_present": inv["manifests"],
            "lockfiles_present": inv["lockfiles"],
            "dependency_count": inv["dependency_count"],
            "pinned_dependencies_hint": inv["pinned_dep_hint"],
            "license_present": inv["license_present"],
            "todo_fixme_total": c["c8_todo_fixme"],
        },
    }

    return {
        "agentcraft_repo_scan_version": "1",
        "brand": "AGENTCRAFT",
        "lens": "B",
        "note": ("counts only -- NOT a score. Feed to the AGENTCRAFT Lens B assessment "
                 "agent (skill/agentcraft-assess/SKILL.md) which SCORES the 8 axes "
                 "0-100 from these counts + a local code SAMPLE, per its runbook."),
        "scanned_at": scanned_at,            # deterministic: null unless caller fills it
        "repo": {
            "path": _short_repo(repo_path),
            "total_files": counts.total_files,
            "total_loc": counts.total_loc,
        },
        "languages": dict(counts.languages.most_common()),
        "total_files": counts.total_files,
        "total_loc": counts.total_loc,
        "axes": axes,
    }


def _short_repo(repo_path):
    """Repo path -> basename only (never leak a full home path in the output)."""
    return os.path.basename(os.path.normpath(repo_path)) or repo_path


# --------------------------------------------------------------------------- #
# Self-test on a SYNTHETIC fixture repo (no real data) -- proves counting math + #
# the C3 no-echo invariant, offline, deterministic.                             #
# --------------------------------------------------------------------------- #

_FIXTURE = {
    # a python source file with: 1 bare except, 1 broad except, a fake secret
    # (COUNTED, never echoed), an eval, a nested loop, a large function, a TODO.
    "src/core/engine.py": (
        "import os\n"
        "import json\n"
        "from src.core import util\n"          # intra-repo import (C1 edge)
        "\n"
        "API_KEY = \"sk-abcdefghijklmnop1234567890\"  # fake secret, COUNTED not echoed\n"
        "\n"
        "def parse(data):\n"
        "    try:\n"
        "        return json.loads(data)\n"
        "    except:\n"                          # bare except (C2)
        "        return None\n"
        "\n"
        "def risky(x):\n"
        "    try:\n"
        "        return eval(x)\n"               # eval (C3)
        "    except Exception:\n"                # broad except (C2)
        "        return 0\n"
        "\n"
        "def big():\n"                           # a large function (>50 lines)
        + "".join("    a = %d\n" % i for i in range(60))
        + "    for i in range(10):\n"
          "        for j in range(10):\n"        # nested loop (C5/C6)
          "            print(i * j)  # TODO: optimize\n"   # TODO (C5/C8)
    ),
    # a python module the engine imports (closes an intra-repo import edge)
    "src/core/util.py": (
        "from src.core import engine\n"          # reciprocal import (circular hint)
        "def helper():\n"
        "    return 42\n"
    ),
    # a test file (C4 test_files == 1)
    "tests/test_engine.py": (
        "from src.core.engine import parse\n"
        "def test_parse():\n"
        "    assert parse('{}') == {}\n"
    ),
    # a JS file with an empty catch + a dangerous html usage (C2/C3)
    "web/app.js": (
        "async function load(urls) {\n"
        "  for (const u of urls) {\n"
        "    await fetch(u);\n"                  # await in loop (C6)
        "  }\n"
        "  try { risky(); } catch (e) {}\n"      # empty catch (C2)
        "  el.dangerouslySetInnerHTML = { __html: x };\n"  # (C3)
        "}\n"
    ),
    # root inventory artifacts
    "README.md": "# Example Repo\n\nA fictional example repository for the self-test.\n",
    "package.json": ("{\n  \"name\": \"example\",\n  \"dependencies\": "
                     "{\n    \"left-pad\": \"^1.0.0\"\n  }\n}\n"),
    "requirements.txt": "flask==2.0.0\nrequests\n",
    "LICENSE": "MIT License\n",
    ".github/workflows/ci.yml": "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
}


def _build_fixture_repo(root):
    """Materialize the synthetic fixture repo under `root`. Returns nothing."""
    for rel, body in _FIXTURE.items():
        p = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)


def run_selftest():
    tmpdir = tempfile.mkdtemp(prefix="agentcraft_repo_selftest_")
    _build_fixture_repo(tmpdir)

    counts = scan_repo(tmpdir)
    inv = scan_root_inventory(tmpdir)
    out = build_output(counts, inv, tmpdir)

    axes = out["axes"]
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append("%s: got %r want %r" % (label, got, want))

    def at_least(label, got, want):
        if got < want:
            fails.append("%s: got %r want >= %r" % (label, got, want))

    # ---- totals ----
    at_least("total_files", out["total_files"], 9)
    at_least("total_loc", out["total_loc"], 80)
    if "python" not in out["languages"]:
        fails.append("languages: python missing")
    if "javascript" not in out["languages"]:
        fails.append("languages: javascript missing")

    # ---- C2 error handling (known-answer) ----
    c2 = axes["C2_reliability_errorhandling"]
    check("c2_bare_except", c2["bare_except"], 1)
    check("c2_broad_except", c2["broad_except"], 1)
    check("c2_empty_catch", c2["empty_catch"], 1)

    # ---- C3 security: SECRET IS COUNTED but VALUE NEVER ECHOED ----
    c3 = axes["C3_security_secrets"]
    check("c3_secret_hits", c3["secret_pattern_hits"], 1)
    check("c3_eval", c3["eval_calls"], 1)
    check("c3_dangerous_html", c3["dangerously_set_inner_html"], 1)
    # THE no-echo invariant: the fake secret VALUE must not appear ANYWHERE in the
    # serialized output. This is the C3 privacy guarantee, proven mechanically.
    blob = json.dumps(out, ensure_ascii=False)
    for leak in ("sk-abcdefghijklmnop1234567890", "left-pad"):
        pass  # left-pad IS allowed (a dep name), listed only to show intent
    if "sk-abcdefghijklmnop1234567890" in blob:
        fails.append("C3 LEAK: secret VALUE echoed into output (must be count-only)")

    # ---- C4 tests ----
    c4 = axes["C4_tests_coverage"]
    check("c4_test_files", c4["test_files"], 1)
    at_least("c4_source_files", c4["source_files"], 3)  # engine, util, app.js
    if not c4["ci_present"]:
        fails.append("c4: ci_present should be True (.github/workflows present)")

    # ---- C5 complexity ----
    c5 = axes["C5_maintainability_complexity"]
    at_least("c5_large_functions", c5["large_functions"], 1)   # big()
    at_least("c5_nested_loops", c5["nested_loops"], 1)
    at_least("c5_todo_fixme", c5["todo_fixme"], 1)

    # ---- C6 performance ----
    c6 = axes["C6_performance_efficiency"]
    at_least("c6_await_in_loop", c6["await_in_loop"], 1)

    # ---- C7 docs ----
    c7 = axes["C7_documentation_readability"]
    if not c7["readme_present"]:
        fails.append("c7: readme_present should be True")

    # ---- C8 deps ----
    c8 = axes["C8_dependencies_techdebt"]
    if "package.json" not in c8["manifests_present"]:
        fails.append("c8: package.json manifest not detected")
    if not c8["license_present"]:
        fails.append("c8: LICENSE not detected")
    at_least("c8_dependency_count", c8["dependency_count"], 2)

    # ---- C1 structure ----
    c1 = axes["C1_architecture_structure"]
    at_least("c1_module_dirs", c1["module_dirs"], 3)
    at_least("c1_intra_import_edges", c1["intra_repo_import_edges"], 1)
    if "src" not in c1["layering_dirs_present"]:
        fails.append("c1: 'src' layering dir not detected")

    # ---- determinism: two runs agree bit-for-bit ----
    out2 = build_output(scan_repo(tmpdir), scan_root_inventory(tmpdir), tmpdir)
    if json.dumps(out, sort_keys=True) != json.dumps(out2, sort_keys=True):
        fails.append("determinism: two scans of the same tree differ")

    # ---- scanned_at is deterministic (null unless caller fills it) ----
    if out["scanned_at"] is not None:
        fails.append("scanned_at: must default to null (no wall-clock in counts)")

    if fails:
        sys.stderr.write("SELFTEST FAILED:\n  " + "\n  ".join(fails) + "\n")
        return 1
    print("OK agentcraft_repo_scan self-test: fixture repo counts hold across all 8 "
          "axes (C1 structure + intra-import, C2 error-handling known-answer, C3 "
          "secret COUNTED-not-echoed + eval/html, C4 tests/CI, C5 large-func/nested/"
          "TODO, C6 await-in-loop, C7 README, C8 manifests/license/deps), determinism "
          "holds, no secret value leaked")
    return 0


# --------------------------------------------------------------------------- #
# CLI.                                                                          #
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="agentcraft_repo_scan.py",
        description="AGENTCRAFT Lens B code scanner (Step 1). Walks ANY repo and emits "
                    "mechanical COUNTS across 8 code-quality axes. 100%% local, zero "
                    "network, scores nothing.")
    ap.add_argument("--repo", default=None,
                    help="path to the repo to scan (default: current directory).")
    ap.add_argument("--scanned-at", default=None,
                    help="(optional) an ISO-8601 timestamp string to stamp into "
                         "`scanned_at`. Omitted => null, so runs stay deterministic.")
    ap.add_argument("--out", default="-",
                    help="output JSON path, or '-' for stdout (default).")
    ap.add_argument("--selftest", "--self-test", dest="selftest",
                    action="store_true",
                    help="run the offline synthetic-fixture self-test and exit.")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    repo_path = os.path.abspath(args.repo) if args.repo else os.getcwd()
    if not os.path.isdir(repo_path):
        sys.stderr.write("Not a directory: %s\n" % repo_path)
        return 2

    counts = scan_repo(repo_path)
    inv = scan_root_inventory(repo_path)
    out = build_output(counts, inv, repo_path, scanned_at=args.scanned_at)

    payload = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(payload)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        sys.stderr.write("wrote %s (%d files, %d loc)\n"
                         % (args.out, out["total_files"], out["total_loc"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
