#!/usr/bin/env python3
"""AGENTCRAFT brand-rename sweep (100% local, no network).

The brand string is single-sourced in SPEC.md §0 (`BRAND = "AGENTCRAFT"`, provisional —
`agentcraft.com`/`agentcraft.io` are taken). It is mirrored, by design, in ~6 downstream
"mirror sites": the README title, the renderer default, the report `brand` field,
the skill folder name, the .gitignore report globs, and the example filenames.

This script makes the rename a **single command**, not an aspirational grep-sweep:
it replaces every literal (case-preserving: AGENTCRAFT→UPPER, agentcraft→lower, Agentcraft→Title),
renames the skill folder + any files whose names carry the brand, and prints a
diff-style summary. It performs NO network I/O — it only rewrites local files.

Usage:
    python rename.py NEWBRAND                # apply
    python rename.py NEWBRAND --dry-run      # show what would change, touch nothing

Candidates weighed (not yet applied): AGENTCRAFT, PAIRSCORE, FORGEIQ.

After running, re-verify:
    python render/agentcraft_card.py --report examples/*-report-dogfood.json --summary-only
    grep -rid skip "<oldbrand>" .    # should be empty (only LOOP_*.md history may keep it)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

OLD = "AGENTCRAFT"  # canonical current brand (mirror of SPEC.md §0)

# Files we never rewrite (binaries, caches, VCS, and the loop-audit history that
# intentionally records the old name as a point-in-time artifact).
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
             ".ruff_cache", ".pytest_cache"}
SKIP_SUFFIXES = {".png", ".svg", ".pyc", ".pyo", ".jpg", ".jpeg", ".gif", ".ico",
                 ".woff", ".woff2", ".ttf", ".zip"}
# History/audit docs keep the old name (they are a record, not a live surface).
SKIP_NAMES = {"LOOP_BASELINE.md", "LOOP_FINAL_REPORT.md"}


def _cases(old: str, new: str) -> list[tuple[str, str]]:
    """Case-preserving replacement pairs: UPPER, lower, Title. Longest-first."""
    return [
        (old.upper(), new.upper()),
        (old.lower(), new.lower()),
        (old.capitalize(), new.capitalize()),
    ]


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        if p.name in SKIP_NAMES:
            continue
        yield p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rename",
                                 description="Rename the AGENTCRAFT brand across all mirror sites (local only).")
    ap.add_argument("new", help="the new brand name (e.g. AGENTCRAFT)")
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parent
    new = args.new.strip()
    if not new or not new.replace("-", "").replace("_", "").isalnum():
        print(f"error: '{new}' is not a clean brand token (alnum + -/_ only)", file=sys.stderr)
        return 2
    if new.upper() == OLD.upper():
        print("nothing to do: new brand equals current brand.")
        return 0

    pairs = _cases(OLD, new)
    edited_files = 0
    total_hits = 0
    renamed: list[tuple[str, str]] = []

    # 1) rewrite text content
    for f in _iter_files(root):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = text
        hits = 0
        for a, b in pairs:
            if a in new_text:
                hits += new_text.count(a)
                new_text = new_text.replace(a, b)
        if hits:
            total_hits += hits
            edited_files += 1
            rel = f.relative_to(root)
            print(f"  edit  {rel}  ({hits} literal{'s' if hits != 1 else ''})")
            if not args.dry_run:
                f.write_text(new_text, encoding="utf-8")

    # 2) rename files whose NAME carries the brand (e.g. agentcraft_card.py, *.agentcraft.json)
    for f in sorted(_iter_files(root), key=lambda p: len(p.parts), reverse=True):
        name = f.name
        new_name = name
        for a, b in pairs:
            new_name = new_name.replace(a, b)
        if new_name != name:
            dst = f.with_name(new_name)
            renamed.append((str(f.relative_to(root)), str(dst.relative_to(root))))
            print(f"  move  {f.relative_to(root)}  ->  {dst.relative_to(root)}")
            if not args.dry_run:
                f.rename(dst)

    # 3) rename the skill folder (skill/agentcraft-assess -> skill/<new>-assess)
    for d in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not d.is_dir():
            continue
        if any(part in SKIP_DIRS for part in d.parts):
            continue
        new_dir = d.name
        for a, b in pairs:
            new_dir = new_dir.replace(a, b)
        if new_dir != d.name:
            dst = d.with_name(new_dir)
            renamed.append((str(d.relative_to(root)) + "/", str(dst.relative_to(root)) + "/"))
            print(f"  move  {d.relative_to(root)}/  ->  {dst.relative_to(root)}/")
            if not args.dry_run:
                d.rename(dst)

    verb = "would change" if args.dry_run else "changed"
    print(f"\n{OLD} -> {new}: {verb} {total_hits} literal(s) in {edited_files} file(s), "
          f"{len(renamed)} path rename(s).")
    if args.dry_run:
        print("(dry-run — nothing written. Re-run without --dry-run to apply.)")
    else:
        print(f"Done. Remember to update BRAND in SPEC.md §0 if the sweep didn't already "
              f"(it should have). Re-verify: python render/{new.lower()}_card.py "
              f"--report examples/{new.lower()}-report-dogfood.json --summary-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
