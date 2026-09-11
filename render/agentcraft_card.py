#!/usr/bin/env python3
"""AGENTCRAFT offline card renderer (v2-aware, v1 backward-tolerant).

Consumes a local AGENTCRAFT report file (JSON, schema in ../SPEC.md section 7) and
renders TWO pages (SPEC section 7.1 · two-page split):

  PAGE 1 -- the SHAREABLE RESULT card (redacted, screenshot-able, viral):
    OVERALL + tier + 7-axis radar + 7 pillar scores + % VERIFIED + a short
    self-opinion sentence. Everything private is STRIPPED: no repo path, no
    filenames, no code, no evidence excerpts, no coaching prose, no sub-signal
    count hints. A machine-enforced redaction guard (fail-loud) refuses to write
    this page if any path/uuid/basename leak survives. This is the public artifact.

  PAGE 2 -- the PRIVATE depth dashboard (local, git-ignored, NEVER shared):
    the full GROWTH PLAN skill-development coaching (each weak pillar => a
    transferable HABIT you build in yourself: weak/why-it-grows-you/personal-
    practice/example) + curated FROM-YOUR-WORK excerpts + trend + per-sub-signal
    micro-bars + strengths +
    profile/style + practices/anti-patterns, rendered in a dark HUD
    aesthetic (Cinzel display headings + JetBrains Mono data + gold accents + a
    cosmic starfield + glass cards + gold/cyan glows). Stays on the user's disk.

Outputs self-contained HTML files and (when Chrome is available) PNGs. The PNG
capture measures the REAL document height and screenshots the WHOLE page, so the
card renders top-to-bottom with nothing clipped (the dynamic-height fix).

v2 (schema `agentcraft_version:"2"`) unlocks, additively:
  - fail-loud partition + containment validation (SPEC sec 2d / invariants 7-11);
  - partition-derived sub-signal micro-bars with an honest applied/eligible + verified
    hint, and an honest "unmeasured" badge (with the limitation code) instead of a
    fabricated number for below-threshold / gated-out signals;
  - a "% VERIFIED" meta cell (of what you applied, how much was independently
    confirmed — prove-don't-declare, per behaviour);
  - a per-week TREND sparkline that shows the two MOAT pillars (P6 Memory,
    P7 Discipline) compounding over weeks — the whole thesis, made visible;
  - a PROFILE & STYLE chip strip and a PRACTICES & ANTI-PATTERNS panel.
A v1 report (bare-number sub_signals, no v2 blocks) still validates and renders
exactly as before — the backward-tolerance bridge (SPEC invariant 12).

PRIVACY (the core feature): 100% OFFLINE. This script reads a LOCAL report file
and writes LOCAL files (HTML/PNG) only. It performs NO network I/O of any kind:
no telemetry, no HTTP POST, no external API, no CDN, no remote fonts. All fonts
are system-font fallbacks; all styling and the radar SVG are inlined. Do not add
`requests`, `urllib`, `socket`, or any external call to this file. You cannot leak
what you never transmit.

Usage:
    # both pages into a directory (page1 share + page2 depth):
    python agentcraft_card.py --report agentcraft-report.agentcraft.json --out cards
    # both pages as file siblings (<name>-share.png + <name>-depth.png):
    python agentcraft_card.py --report r.json --out card.png
    # only the shareable page 1 (redacted):
    python agentcraft_card.py --report r.json --out card.png --page share
    # only the private depth page 2 (HUD):
    python agentcraft_card.py --report r.json --out card.png --page depth
    python agentcraft_card.py --report r.json --out cards --html-only
    python agentcraft_card.py --report r.json --summary-only

Chrome (headless) is used only to rasterize the LOCAL HTML into a PNG. If Chrome
is not found, the renderer writes the HTML and exits 0 (HTML-only fallback).
"""

from __future__ import annotations

import argparse
import html as _html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --- BRAND (provisional) -------------------------------------------------------
# Canonical brand lives in ../SPEC.md. Mirror it here (ONE obvious place) so the
# renderer's title text is trivially renamable. To rebrand: change BRAND in
# SPEC.md, then update this constant. See SPEC.md top block.
BRAND: str = "AGENTCRAFT"
TAGLINE: str = "Not a verdict — a coach."

# --- Fixed contract from SPEC.md ----------------------------------------------
PILLAR_ORDER = ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
PILLAR_LABELS = {
    "P1": "Intent & Framing",
    "P2": "Context & Grounding",
    "P3": "Execution & Diagnosis",
    "P4": "Orchestration",
    "P5": "Verification",
    "P6": "Memory & Continuity",   # MEGA-blind moat
    "P7": "System-Discipline",     # MEGA-blind moat
}
# Short radar axis labels (kept tight so nothing gets cut off on the polygon).
PILLAR_SHORT = {
    "P1": "INTENT",
    "P2": "CONTEXT",
    "P3": "EXECUTION",
    "P4": "ORCHESTR.",
    "P5": "VERIFY",
    "P6": "MEMORY",
    "P7": "DISCIPLINE",
}
MOAT_PILLARS = {"P6", "P7"}

# Tier bands (SPEC.md section 3). Report may override via config.tier_bands.
DEFAULT_TIER_BANDS = {"diamond": 85, "gold": 75, "silver": 65}

# --- Aesthetic: OUR palette (premium dark, distinct from MEGA's bronze/gold) ---
# Deep indigo/obsidian base, cyan->violet accent, per-tier accent color. Tasteful,
# not a MEGA clone. All colors inlined; nothing external.
PALETTE = {
    "bg0": "#0a0a12",
    "bg1": "#12121f",
    "card_top": "#1a1a2e",
    "card_bot": "#0d0d18",
    "ink": "#f4f5fb",
    "ink_dim": "#9aa0bd",
    "ink_faint": "#5a6088",
    "line": "#262a44",
    "accent": "#5eead4",     # cyan/teal
    "accent2": "#a78bfa",    # violet
    "good": "#4ade80",
    "warn": "#fbbf24",
    "weak": "#f87171",
    "radar_fill": "rgba(94,234,212,0.16)",
    "radar_stroke": "#5eead4",
    "moat": "#a78bfa",
}
TIER_STYLE = {
    "diamond": {"accent": "#7dd3fc", "accent2": "#c4b5fd", "label": "DIAMOND"},
    "gold":    {"accent": "#fcd34d", "accent2": "#fbbf24", "label": "GOLD"},
    "silver":  {"accent": "#d1d5db", "accent2": "#9ca3af", "label": "SILVER"},
    "bronze":  {"accent": "#e0a878", "accent2": "#c08552", "label": "BRONZE"},
}


# =============================================================================
# Report loading + validation (SPEC.md section 7 invariants)
# =============================================================================
def load_report(path: Path) -> dict:
    """Load and validate a AGENTCRAFT report file (SPEC.md section 7)."""
    with path.open("r", encoding="utf-8") as fh:
        report = json.load(fh)
    _validate_report(report)
    return report


def _is_code_audit(report: dict) -> bool:
    """True if this is a LENS B code-audit report (axes C1..C8), not a Lens A
    collaboration report (pillars P1..P7).

    Detected by an explicit `report_kind == "code-audit"` OR (backward-tolerant)
    by an `axes` block present with no `pillars` block. Deterministic; never
    guesses a lens the file didn't declare.
    """
    if not isinstance(report, dict):
        return False
    if str(report.get("report_kind", "")).lower() == "code-audit":
        return True
    if str(report.get("lens", "")).upper() == "B" and "axes" in report:
        return True
    return "axes" in report and "pillars" not in report


def _validate_code_audit(report: dict) -> None:
    """Fail-loud structural validation for a LENS B code-audit report.

    Lighter than the pillar invariants — a code audit is descriptive per-axis.
    We validate only what build_repo_html dereferences so a malformed file fails
    loud, not silent:
      * `axes` is a dict and carries at least one C1..C8 axis;
      * each PRESENT axis that is eligible + measured has an int/float score 0-100
        (an unmeasured/ineligible axis may carry score:null — honest-empty);
      * `overall.score` is 0-100 and `overall.tier` is one of the four tiers.
    Absent axes are tolerated (the renderer shows an honest N/A row), so a partial
    scan still renders — we never fabricate a missing axis.
    """
    axes = report.get("axes")
    if not isinstance(axes, dict) or not axes:
        raise ValueError("code-audit report missing required non-empty 'axes' block")
    present = [s for s in CODE_AXIS_ORDER if _code_axis_lookup(axes, s)]
    if not present:
        raise ValueError("code-audit report.axes carries no recognized C1..C8 axis")
    for short in present:
        ax = _code_axis_lookup(axes, short)
        eligible = ax.get("eligible", True)
        measured = (ax.get("measurement_status", "measured") != "unmeasured")
        score = ax.get("score")
        if eligible and measured:
            if not isinstance(score, (int, float)) or not (0 <= score <= 100):
                raise ValueError(
                    f"{short}: measured axis needs score 0-100, got {score!r}")
        else:
            if score is not None and not (isinstance(score, (int, float)) and 0 <= score <= 100):
                raise ValueError(
                    f"{short}: unmeasured/ineligible axis score must be null or 0-100, "
                    f"got {score!r}")

    overall = report.get("overall")
    if not isinstance(overall, dict):
        raise ValueError("code-audit report missing required 'overall' block")
    oscore = overall.get("score")
    if not isinstance(oscore, (int, float)) or not (0 <= oscore <= 100):
        raise ValueError(f"overall.score must be 0-100, got {oscore!r}")
    tier = overall.get("tier")
    if tier not in {"diamond", "gold", "silver", "bronze"}:
        raise ValueError(f"overall.tier invalid: {tier!r}")


def _validate_report(report: dict) -> None:
    """Enforce the schema invariants the renderer relies on (SPEC.md section 7).

    Invariants checked here (carried from v1 — a v1 report satisfies all of these):
      1. pillars contains P1..P7; ineligible => eligible:false + score:null.
      2. overall.score is int 0-100; overall.tier in the four-tier set.
      3/4/5/6 are producer concerns; we validate the structural ones the
         renderer dereferences so a malformed file fails loud, not silent.

    When `agentcraft_version == "2"` AND a pillar's sub_signals are OBJECTS (not bare
    numbers), the v2 containment/partition invariants (SPEC.md sec 2d + sec 7,
    invariants 7-11) are ALSO enforced fail-loud. This mirrors the standalone
    examples/_v2_containment_check.py acceptance harness, so a v2 report cannot
    render a fabricated-consistent card. See _validate_v2().
    """
    if not isinstance(report, dict):
        raise ValueError("report is not a JSON object")

    # LENS B: a code-audit report is AXES-based (C1..C8), not pillar-based, so it
    # has its own (lighter) structural validation. Detected by report_kind OR by
    # the presence of an `axes` block with no `pillars`. Returns early — the
    # pillar invariants below do not apply to Lens B.
    if _is_code_audit(report):
        _validate_code_audit(report)
        return

    if "pillars" not in report or "overall" not in report:
        raise ValueError("report missing required 'pillars'/'overall' blocks")

    pillars = report["pillars"]
    for key in PILLAR_ORDER:
        if key not in pillars:
            raise ValueError(f"report.pillars missing required key {key!r}")
        p = pillars[key]
        eligible = p.get("eligible", True)
        score = p.get("score")
        if eligible:
            if not isinstance(score, (int, float)) or not (0 <= score <= 100):
                raise ValueError(f"{key}: eligible pillar needs score 0-100, got {score!r}")
        else:
            if score is not None:
                raise ValueError(f"{key}: ineligible pillar must have score:null")

    overall = report["overall"]
    oscore = overall.get("score")
    if not isinstance(oscore, (int, float)) or not (0 <= oscore <= 100):
        raise ValueError(f"overall.score must be 0-100, got {oscore!r}")
    tier = overall.get("tier")
    if tier not in {"diamond", "gold", "silver", "bronze"}:
        raise ValueError(f"overall.tier invalid: {tier!r}")

    # v2 additions: only when the file declares v2. A v1 file (or a v2 file whose
    # sub_signals are bare numbers) skips this entirely — the backward-tolerance
    # bridge (SPEC.md invariant 12). Never break it.
    if str(report.get("agentcraft_version", "1")) == "2":
        _validate_v2(report)


_V2_PARTS = ("eligible", "applied", "declined", "missed", "verified_outcome")
_LIMITATION_CODES = {
    "no-opportunity", "below-threshold", "extraction-gap",
    "narrow-window", "retention-window-bounded", "harness-capability-missing",
}


def _has_partition(obj: dict) -> bool:
    """True if a sub_signal/pillar dict carries the v2 partition counts."""
    return isinstance(obj, dict) and any(k in obj for k in _V2_PARTS)


def _validate_v2(report: dict) -> None:
    """Fail-loud validation of the v2 partition + containment invariants.

    Enforces SPEC.md sec 2d + sec 7 invariants 7-11, mirroring the standalone
    examples/_v2_containment_check.py harness so the renderer and the harness
    agree bit-for-bit:

      7.  Partition holds: eligible == applied + declined + missed
          (every v2 sub_signal OBJECT AND every pillar `partition` roll-up).
      8.  Verification bound: verified_outcome <= applied (everywhere).
      9.  Component-wise containment: each of the 5 counts for a sub_signal is
          <= its pillar's corresponding roll-up.
      10. Measurement containment: measured <=> eligible >= threshold; a measured
          sub_signal requires a measured pillar; unmeasured carries a valid code.
      11. Episode ceiling: no pillar partition.eligible exceeds task_episodes.

    Backward-tolerance (invariant 12): a pillar whose sub_signals are BARE NUMBERS
    (v1 shape inside a v2 file) is skipped — we only validate OBJECT sub_signals.
    """
    cfg = report.get("config", {}) or {}
    threshold = cfg.get("measurement_threshold", 3)
    cov = report.get("coverage", {}) or {}
    # Episode ceiling denominator (SPEC sec 1c). Prefer explicit task_episodes.
    episodes = cov.get("task_episodes", cov.get("episodes"))

    for pk, p in report["pillars"].items():
        if not isinstance(p, dict):
            continue
        p_meas = p.get("measurement_status")
        part = p.get("partition") or {}

        # (7) pillar partition holds — only assert when the pillar is measured and
        # actually carries a roll-up (an unmeasured/v1 pillar may omit it).
        if part:
            if p_meas == "measured":
                s = part.get("applied", 0) + part.get("declined", 0) + part.get("missed", 0)
                if part.get("eligible", 0) != s:
                    raise ValueError(
                        f"{pk}: pillar partition broken — eligible "
                        f"{part.get('eligible', 0)} != applied+declined+missed {s}")
            # (8) verification bound at pillar level
            if part.get("verified_outcome", 0) > part.get("applied", 0):
                raise ValueError(
                    f"{pk}: pillar verified_outcome {part.get('verified_outcome', 0)} "
                    f"> applied {part.get('applied', 0)}")
            # (11) episode ceiling
            if episodes is not None and part.get("eligible", 0) > episodes:
                raise ValueError(
                    f"{pk}: pillar eligible {part.get('eligible', 0)} exceeds "
                    f"coverage.task_episodes {episodes}")

        for sk, sub in (p.get("sub_signals") or {}).items():
            # Bare-number sub_signal = v1 shape inside a v2 file: skip (bridge).
            if not _has_partition(sub):
                continue
            sub_meas = sub.get("measurement_status")
            # (7) sub-signal partition holds
            s = sub.get("applied", 0) + sub.get("declined", 0) + sub.get("missed", 0)
            if sub.get("eligible", 0) != s:
                raise ValueError(
                    f"{pk}.{sk}: partition broken — eligible "
                    f"{sub.get('eligible', 0)} != applied+declined+missed {s}")
            # (8) verification bound
            if sub.get("verified_outcome", 0) > sub.get("applied", 0):
                raise ValueError(
                    f"{pk}.{sk}: verified_outcome {sub.get('verified_outcome', 0)} "
                    f"> applied {sub.get('applied', 0)}")
            # (9) component-wise containment against the pillar roll-up
            if part:
                for c in _V2_PARTS:
                    if sub.get(c, 0) > part.get(c, 0):
                        raise ValueError(
                            f"{pk}.{sk}: containment broken — {c} {sub.get(c, 0)} "
                            f"exceeds pillar {c} {part.get(c, 0)}")
            # (10) measurement containment
            is_measured = sub.get("eligible", 0) >= threshold
            if (sub_meas == "measured") != is_measured:
                raise ValueError(
                    f"{pk}.{sk}: measurement_status {sub_meas!r} disagrees with "
                    f"eligible {sub.get('eligible', 0)} (threshold {threshold})")
            if sub_meas == "measured" and p_meas is not None and p_meas != "measured":
                raise ValueError(
                    f"{pk}.{sk}: measured sub-signal under unmeasured pillar {pk}")
            if sub_meas == "unmeasured":
                lim = sub.get("limitations")
                if lim not in _LIMITATION_CODES:
                    raise ValueError(
                        f"{pk}.{sk}: unmeasured sub-signal needs a valid limitations "
                        f"code, got {lim!r}")


def tier_for(score: float, bands: dict | None = None) -> str:
    """Map an OVERALL score to a tier label (SPEC.md section 3)."""
    b = bands or DEFAULT_TIER_BANDS
    if score >= b.get("diamond", 85):
        return "diamond"
    if score >= b.get("gold", 75):
        return "gold"
    if score >= b.get("silver", 65):
        return "silver"
    return "bronze"


# =============================================================================
# Small helpers
# =============================================================================
def _esc(s) -> str:
    """HTML-escape any value for safe inline embedding."""
    return _html.escape("" if s is None else str(s))


def _score_color(score) -> str:
    """Traffic-ish color for a pillar score (our palette, not MEGA's)."""
    if score is None:
        return PALETTE["ink_faint"]
    if score >= 75:
        return PALETTE["good"]
    if score >= 65:
        return PALETTE["warn"]
    return PALETTE["weak"]


def _fmt_score(score) -> str:
    return "N/A" if score is None else str(int(round(score)))


def _humanize_sub(key: str) -> str:
    """Turn a sub_signal snake_case key into a compact human label.

    e.g. "root_cause_depth" -> "Root cause depth". Purely presentational; the
    renderer never invents sub-signals, it only labels whatever the report carries.
    """
    if not key:
        return ""
    words = str(key).replace("-", " ").replace("_", " ").split()
    if not words:
        return ""
    return " ".join(words[:1]).capitalize() + (" " + " ".join(words[1:]) if len(words) > 1 else "")


_LIMITATION_SHORT = {
    "no-opportunity": "no opp.",
    "below-threshold": "thin",
    "extraction-gap": "gated",
    "narrow-window": "narrow",
    "retention-window-bounded": "aged out",
    "harness-capability-missing": "no field",
}


def _sub_signal_bars(sub_signals) -> str:
    """Render per-pillar sub-signal micro-bars (D3 depth surface).

    `sub_signals` is an optional map on each pillar (SPEC.md sec 7). Two shapes,
    both tolerated (the v1->v2 backward-tolerance bridge, SPEC invariant 12):

      v1 : { name: 0-100 }            -> plain micro-bar (unchanged behaviour).
      v2 : { name: {score, measurement_status, applied, eligible, verified_outcome,
                    limitations, ...} }  -> micro-bar read via .get("score"), PLUS
             an honest "measured N/eligible + verified" hint, OR — for an unmeasured
             sub-signal (score:null) — a dimmed badge naming the limitation code
             (honest-empty; never a fabricated number).

    We render nothing when absent/empty (backward-compatible). A v2 OBJECT whose
    score is null is NOT skipped (it's shown as an honest unmeasured badge); a
    non-numeric v1 value that is neither a number nor a v2 object IS skipped.
    """
    if not isinstance(sub_signals, dict) or not sub_signals:
        return ""
    rows = []
    for name, val in sub_signals.items():
        if isinstance(val, (int, float)):
            # --- v1 bare-number shape (unchanged) ---
            v = max(0, min(100, int(round(val))))
            color = _score_color(v)
            rows.append(f'''
          <div class="sub">
            <span class="sub-name" title="{_esc(name)}">{_esc(_humanize_sub(name))}</span>
            <span class="sub-bar"><span class="sub-fill" style="width:{v}%;
                  background:{color}"></span></span>
            <span class="sub-val" style="color:{color}">{v}</span>
          </div>''')
        elif isinstance(val, dict) and ("score" in val or _has_partition(val)):
            # --- v2 object shape ---
            score = val.get("score")
            if isinstance(score, (int, float)):
                v = max(0, min(100, int(round(score))))
                color = _score_color(v)
                # Honest count hint: applied/eligible + how many verified.
                elig = val.get("eligible")
                app = val.get("applied")
                ver = val.get("verified_outcome")
                hint_bits = []
                if isinstance(app, int) and isinstance(elig, int) and elig:
                    hint_bits.append(f"{app}/{elig}")
                if isinstance(ver, int) and ver:
                    hint_bits.append(f"✓{ver}")  # check-mark + verified count
                hint = (f'<span class="sub-hint">{_esc(" ".join(hint_bits))}</span>'
                        if hint_bits else "")
                rows.append(f'''
          <div class="sub">
            <span class="sub-name" title="{_esc(name)}">{_esc(_humanize_sub(name))}</span>
            <span class="sub-bar"><span class="sub-fill" style="width:{v}%;
                  background:{color}"></span></span>
            <span class="sub-val" style="color:{color}">{v}{hint}</span>
          </div>''')
            else:
                # Unmeasured sub-signal: honest badge, no fabricated bar.
                lim = val.get("limitations")
                lim_txt = _LIMITATION_SHORT.get(lim, "unmeasured")
                rows.append(f'''
          <div class="sub sub-unmeasured">
            <span class="sub-name" title="{_esc(name)}">{_esc(_humanize_sub(name))}</span>
            <span class="sub-bar sub-bar-empty"></span>
            <span class="sub-na" title="{_esc(lim or 'unmeasured')}">{_esc(lim_txt)}</span>
          </div>''')
        # else: neither number nor v2 object -> skip (no fabrication).
    if not rows:
        return ""
    return f'<div class="subs">{"".join(rows)}</div>'


# =============================================================================
# Radar SVG (pure inline SVG, no JS, no external anything)
# =============================================================================
def build_radar_svg(report: dict, size: int = 460) -> str:
    """Build a 7-axis radar polygon (0-100) as inline SVG.

    Ineligible pillars (score:null) are plotted at the center (0) and their axis
    label is dimmed, so the shape stays honest without crashing.
    """
    # Horizontal breathing room so the longest EDGE labels (DISCIPLINE / EXECUTION /
    # ORCHESTR.) never clip against the SVG bounds. The wider canvas scales down to
    # fit any card via max-width:100% -- labels live inside the viewBox, so no clip.
    pad_x = 108
    w = size + 2 * pad_x
    cx = w / 2.0
    cy = size / 2.0
    n = len(PILLAR_ORDER)
    max_r = size * 0.36
    label_r = size * 0.455
    rings = [0.25, 0.5, 0.75, 1.0]

    def pt(angle_idx: int, radius_frac: float):
        # start at top (-90deg), go clockwise
        ang = -math.pi / 2 + (2 * math.pi * angle_idx / n)
        return (cx + max_r * radius_frac * math.cos(ang),
                cy + max_r * radius_frac * math.sin(ang))

    parts: list[str] = []
    parts.append(f'<svg width="{w}" height="{size}" viewBox="0 0 {w} {size}" '
                 f'style="max-width:100%;height:auto" '
                 f'xmlns="http://www.w3.org/2000/svg" role="img" '
                 f'aria-label="AGENTCRAFT 7-pillar radar">')

    # concentric grid rings
    for rf in rings:
        ring_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, rf) for i in range(n)))
        parts.append(f'<polygon points="{ring_pts}" fill="none" '
                     f'stroke="{PALETTE["line"]}" stroke-width="1" opacity="0.7"/>')

    # spokes
    for i in range(n):
        x, y = pt(i, 1.0)
        parts.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                     f'stroke="{PALETTE["line"]}" stroke-width="1" opacity="0.6"/>')

    # data polygon
    data_pts = []
    for i, key in enumerate(PILLAR_ORDER):
        raw = report["pillars"][key].get("score")
        frac = 0.0 if raw is None else max(0.0, min(1.0, raw / 100.0))
        data_pts.append(pt(i, frac))
    data_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)
    parts.append(f'<polygon points="{data_str}" fill="{PALETTE["radar_fill"]}" '
                 f'stroke="{PALETTE["radar_stroke"]}" stroke-width="2.5" '
                 f'stroke-linejoin="round"/>')

    # vertices (moat pillars get a violet dot)
    for i, key in enumerate(PILLAR_ORDER):
        x, y = data_pts[i]
        dot = PALETTE["moat"] if key in MOAT_PILLARS else PALETTE["radar_stroke"]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{dot}"/>')

    # axis labels + per-axis score
    for i, key in enumerate(PILLAR_ORDER):
        ang = -math.pi / 2 + (2 * math.pi * i / n)
        lx = cx + label_r * math.cos(ang)
        ly = cy + label_r * math.sin(ang)
        raw = report["pillars"][key].get("score")
        moat = key in MOAT_PILLARS
        lbl_color = PALETTE["moat"] if moat else PALETTE["ink_dim"]
        if raw is None:
            lbl_color = PALETTE["ink_faint"]
        anchor = "middle"
        if lx < cx - 6:
            anchor = "end"
        elif lx > cx + 6:
            anchor = "start"
        dy = 0
        if ly < cy - 6:
            dy = -4
        elif ly > cy + 6:
            dy = 12
        star = " ◆" if moat else ""  # diamond glyph flags moat axis
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + dy:.1f}" fill="{lbl_color}" '
            f'font-size="12.5" font-weight="700" text-anchor="{anchor}" '
            f'font-family="Segoe UI, Roboto, Helvetica, Arial, sans-serif">'
            f'{_esc(PILLAR_SHORT[key])}{star}</text>')
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + dy + 14:.1f}" '
            f'fill="{_score_color(raw)}" font-size="12" font-weight="800" '
            f'text-anchor="{anchor}" '
            f'font-family="Segoe UI, Roboto, Helvetica, Arial, sans-serif">'
            f'{_fmt_score(raw)}</text>')

    parts.append("</svg>")
    return "".join(parts)


# =============================================================================
# HTML assembly (fully self-contained; system fonts; no network)
# =============================================================================
_FONT_STACK = ('"Segoe UI", Roboto, "Helvetica Neue", Helvetica, Arial, '
               '"Noto Sans", sans-serif')
_MONO_STACK = ('"Cascadia Code", "Consolas", "SFMono-Regular", "Menlo", '
               'monospace')


def _pillar_stat_rows(report: dict) -> str:
    rows = []
    for key in PILLAR_ORDER:
        p = report["pillars"][key]
        score = p.get("score")
        eligible = p.get("eligible", True)
        moat = key in MOAT_PILLARS
        color = _score_color(score)
        bar_pct = 0 if score is None else max(0, min(100, int(round(score))))
        name = PILLAR_LABELS[key]
        moat_tag = (f'<span class="moat-tag" title="MEGA-blind axis — our moat">'
                    f'◆ moat</span>') if moat else ""
        elig_tag = "" if eligible else '<span class="na-tag">insufficient signal</span>'
        # Sub-signals: only rendered for eligible pillars that actually carry them.
        sub_bars = _sub_signal_bars(p.get("sub_signals")) if eligible else ""
        rows.append(f'''
        <div class="stat">
          <div class="stat-head">
            <span class="stat-key">{_esc(key)}</span>
            <span class="stat-name">{_esc(name)}{moat_tag}{elig_tag}</span>
            <span class="stat-score" style="color:{color}">{_fmt_score(score)}</span>
          </div>
          <div class="bar"><div class="bar-fill" style="width:{bar_pct}%;
               background:linear-gradient(90deg,{color},{color}cc)"></div></div>
          {sub_bars}
        </div>''')
    return "".join(rows)


def _meta_strip(report: dict) -> str:
    mm = report.get("meta_metrics", {}) or {}
    cov = report.get("coverage", {}) or {}
    outcome = mm.get("outcome_rate", {}) or {}
    eff = mm.get("efficiency", {}) or {}
    verified = mm.get("verified_rate", {}) or {}   # v2: prove-don't-declare stat
    win = cov.get("window", {}) or {}

    out_pct = outcome.get("pct")
    out_sub = ""
    if outcome.get("completed") is not None and outcome.get("attempted") is not None:
        out_sub = f"{outcome['completed']}/{outcome['attempted']} tasks"

    eff_idx = eff.get("index")
    eff_sub_bits = []
    if eff.get("turns_per_outcome") is not None:
        eff_sub_bits.append(f"{eff['turns_per_outcome']} turns/outcome")
    if eff.get("rework_ratio") is not None:
        eff_sub_bits.append(f"rework {eff['rework_ratio']}")
    eff_sub = " · ".join(eff_sub_bits)

    # v2 "% VERIFIED": of the behaviours the developer applied, how many were
    # independently confirmed (verified_outcome / applied). This is the
    # prove-don't-declare number, surfaced at card level (SPEC sec 1c + 7.1).
    ver_pct = verified.get("pct")
    ver_sub = ""
    if verified.get("verified") is not None and verified.get("applied") is not None:
        ver_sub = f"{verified['verified']}/{verified['applied']} applied confirmed"
    ver_tone = _score_color(ver_pct) if ver_pct is not None else PALETTE["ink_dim"]

    conf = cov.get("confidence", "?")
    cov_sub_bits = []
    if cov.get("sessions") is not None:
        cov_sub_bits.append(f"{cov['sessions']} sessions")
    if cov.get("episodes") is not None:
        cov_sub_bits.append(f"{cov['episodes']} episodes")
    cov_sub = " · ".join(cov_sub_bits)
    if win.get("from") and win.get("to"):
        cov_sub += f"<br>{_esc(win['from'])} → {_esc(win['to'])}"

    def cell(label, big, sub, tone=PALETTE["accent"]):
        big_s = "—" if big is None else _esc(big)
        return f'''
        <div class="meta-cell">
          <div class="meta-label">{_esc(label)}</div>
          <div class="meta-big" style="color:{tone}">{big_s}</div>
          <div class="meta-sub">{sub}</div>
        </div>'''

    conf_tone = {"high": PALETTE["good"], "medium": PALETTE["warn"],
                 "low": PALETTE["weak"]}.get(conf, PALETTE["ink_dim"])

    # The VERIFIED cell only appears when the report carries verified_rate (v2).
    # v1 reports show the original 3-cell strip unchanged (graceful degrade).
    cells = [
        cell("OUTCOME", (f"{out_pct}%" if out_pct is not None else None), _esc(out_sub)),
        cell("EFFICIENCY", eff_idx, eff_sub, PALETTE["accent2"]),
    ]
    if ver_pct is not None or ver_sub:
        cells.append(cell("% VERIFIED",
                          (f"{ver_pct}%" if ver_pct is not None else None),
                          _esc(ver_sub), ver_tone))
    cells.append(cell("COVERAGE", _esc(str(conf)).upper(), cov_sub, conf_tone))

    n = len(cells)
    return f'''
    <div class="meta-strip" style="grid-template-columns:repeat({n},1fr);">
      {"".join(cells)}
    </div>
    <div class="meta-note">Meta-metrics are descriptive context — NOT part of the OVERALL score.</div>'''


def _coaching_cards(report: dict) -> str:
    """Render the GROWTH-PLAN coaching cards — the depth surface (SPEC §5).

    AGENTCRAFT is a SKILL-DEVELOPMENT coach: each card frames a weak pillar as a
    transferable HABIT the user builds in THEMSELVES (not an infra/agent tweak).
    Each entry renders the full coach contract richly, in a growth/self-development
    voice:
      WEAK (what you did, from your own work) · WHY (why building this habit makes
      YOU stronger) · HOW (a personal PRACTICE you adopt) · the PRACTICE line (how
      YOU phrase/sequence it next time) · the RETEST tip (a behavior to track in
      yourself next scan). Captions read "BUILD THIS HABIT" / "PRACTICE — try this
      yourself" / "track in yourself next scan" so the card is unmistakably a
      personal growth plan, never a verdict or a to-do list for the user's tooling.

    Two optional depth fields are surfaced when the producer supplies them
    (backward-safe — absent => nothing extra renders, a v1 entry is unchanged):
      - `evidence_excerpt` : a short, REDACTED paraphrase the agent lifted from the
        curated evidence (SPEC §5b / extractor curation) — rendered as a "from your
        work" quote-block so the coaching is pinned to the user's OWN history, not a
        generic tip. This is the North-Star made visible: the coach saw the work.
      - `sub_signal` : the weakest sub-signal that dragged the pillar — rendered as a
        small chip in the head so the card names WHICH behaviour to fix.
    """
    coaching = report.get("coaching", []) or []
    if not coaching:
        return ('<div class="empty">No pillars below target — nothing to coach. '
                'Keep compounding.</div>')
    cards = []
    for c in coaching:
        if not isinstance(c, dict):
            continue  # never fabricate; skip a malformed entry rather than crash
        pillar = c.get("pillar", "")
        # Optional: name the weakest sub-signal that dragged the pillar (chip in head).
        sub = c.get("sub_signal", "")
        sub_chip = (f'<span class="coach-sub" title="weakest sub-signal">'
                    f'{_esc(_humanize_sub(sub))}</span>') if sub else ""
        # Optional WEAK row only when present (a v1 entry may omit it).
        weak = c.get("weak", "")
        weak_row = (f'''
          <div class="coach-row"><span class="lbl weak-lbl">WEAK</span>
               <span class="txt txt-weak">{_esc(weak)}</span></div>''' if weak else "")
        why = c.get("why", "")
        why_row = (f'''
          <div class="coach-row"><span class="lbl why-lbl">WHY</span>
               <span class="txt">{_esc(why)}</span></div>''' if why else "")
        how = c.get("how", "")
        how_row = (f'''
          <div class="coach-row"><span class="lbl how-lbl">HOW</span>
               <span class="txt">{_esc(how)}</span></div>''' if how else "")
        # PRACTICE — a personal move the USER tries themselves (a habit they build),
        # captioned so the card reads as self-development, not an infra to-do list.
        example = c.get("example", "")
        example_block = (f'''
          <div class="coach-example-wrap">
            <span class="coach-example-cap">PRACTICE — try this yourself</span>
            <div class="coach-example">{_esc(example)}</div>
          </div>''' if example else "")
        # FROM YOUR WORK — the curated, redacted excerpt (own-work anchor). Optional.
        excerpt = c.get("evidence_excerpt", "")
        excerpt_block = (f'''
          <div class="coach-excerpt-wrap">
            <span class="coach-excerpt-cap">FROM YOUR WORK</span>
            <div class="coach-excerpt">{_esc(excerpt)}</div>
          </div>''' if excerpt else "")
        retest = c.get("retest_tip", "")
        retest_row = (f'<div class="coach-retest">↻ track in yourself next scan: '
                      f'{_esc(retest)}</div>' if retest else "")
        cards.append(f'''
        <div class="coach">
          <div class="coach-head">
            <span class="coach-pill">{_esc(pillar)}</span>
            <span class="coach-title">{_esc(c.get("title", ""))}</span>
            {sub_chip}
            <span class="coach-habit-cap">BUILD THIS HABIT</span>
          </div>
          {weak_row}
          {why_row}
          {how_row}
          {example_block}
          {excerpt_block}
          {retest_row}
        </div>''')
    return "".join(cards)


def _strengths_list(report: dict) -> str:
    strengths = report.get("strengths", []) or []
    if not strengths:
        return ""
    items = []
    for s in strengths:
        # Tolerate both shapes: a {pillar, note} dict OR a plain string affirmation
        # (the SKILL prose says "one-line strengths[] affirmation"; be robust to both).
        if isinstance(s, str):
            pill, txt = "", s
        elif isinstance(s, dict):
            pill, txt = s.get("pillar", ""), s.get("note", s.get("text", ""))
        else:
            continue
        items.append(f'''
        <div class="strength">
          <span class="strength-pill">{_esc(pill)}</span>
          <span class="strength-txt">{_esc(txt)}</span>
        </div>''')
    return f'''
    <div class="panel-title">STRENGTHS</div>
    <div class="strengths">{"".join(items)}</div>'''


# =============================================================================
# v2 DESCRIPTIVE + SYNTHESIS surfaces (SPEC.md sec 5b / 7.7 — all descriptive,
# never folded into OVERALL). Each renders "" when its block is absent (v1-safe).
# =============================================================================
def _profile_style_strip(report: dict) -> str:
    """Compact PROFILE + STYLE strip (SPEC 7.7). Descriptive, evidence-inferred.

    Renders nothing if neither block exists (v1 report). Each field is a small
    key/value chip; an omitted field simply isn't shown (prove-don't-declare —
    we never invent a value the producer chose to omit).
    """
    profile = report.get("profile", {}) or {}
    style = report.get("style", {}) or {}
    if not profile and not style:
        return ""

    # Ordered, human labels for the known fields; unknown extra keys are appended.
    prof_labels = [("role", "role"), ("experience", "exp"),
                   ("team", "team"), ("goal", "goal")]
    style_labels = [("paradigm", "paradigm"), ("typing", "typing"),
                    ("testing", "testing"), ("architecture", "arch"),
                    ("error_handling", "errors"), ("abstraction", "abstraction")]

    def chips(block, labels):
        out = []
        seen = set()
        for key, lbl in labels:
            if block.get(key):
                seen.add(key)
                out.append(f'<span class="chip"><span class="chip-k">{_esc(lbl)}</span>'
                           f'<span class="chip-v">{_esc(block[key])}</span></span>')
        for key, val in block.items():  # any producer-added extras, honestly shown
            if key not in seen and val:
                out.append(f'<span class="chip"><span class="chip-k">{_esc(key)}</span>'
                           f'<span class="chip-v">{_esc(val)}</span></span>')
        return "".join(out)

    prof_html = chips(profile, prof_labels)
    style_html = chips(style, style_labels)
    groups = []
    if prof_html:
        groups.append(f'<div class="chip-group"><div class="chip-cap">PROFILE</div>'
                      f'<div class="chips">{prof_html}</div></div>')
    if style_html:
        groups.append(f'<div class="chip-group"><div class="chip-cap">STYLE</div>'
                      f'<div class="chips">{style_html}</div></div>')
    if not groups:
        return ""
    return f'''
      <div class="panel">
        <div class="panel-title">PROFILE &amp; STYLE</div>
        {"".join(groups)}
        <div class="desc-note">Inferred from history — descriptive, never scored.</div>
      </div>'''


def _trend_sparkline(report: dict, w: int = 560, h: int = 150) -> str:
    """Per-week trend sparkline (SPEC 5b/7.7) — inline SVG, no JS, no network.

    Plots OVERALL + the two MOAT pillars (P6 Memory, P7 Discipline) across the
    weeks the window covers. THIS IS THE THESIS MADE VISIBLE: P6/P7 compounding
    over weeks is the whole reason AGENTCRAFT beats a single-session score. Renders
    nothing for a v1 report (no `trend` block) or a trend with < 2 points (a line
    needs two points; one point would be a dishonest "trend").
    """
    trend = report.get("trend", []) or []
    pts = [t for t in trend if isinstance(t, dict) and t.get("week")]
    if len(pts) < 2:
        return ""

    # y-axis fixed 0-100 (scores are 0-100); x evenly spaced by week index.
    pad_l, pad_r, pad_t, pad_b = 8, 8, 14, 26
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    n = len(pts)

    def xy(i, val):
        x = pad_l + (plot_w * i / (n - 1))
        v = 0 if val is None else max(0, min(100, float(val)))
        y = pad_t + plot_h * (1 - v / 100.0)
        return x, y

    # Series: (report-key, label, color). OVERALL + the two moat pillars.
    series = [
        ("overall", "OVERALL", PALETTE["accent"]),
        ("P6", "MEMORY (moat)", PALETTE["moat"]),
        ("P7", "DISCIPLINE (moat)", PALETTE["accent2"]),
    ]

    parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
             f'xmlns="http://www.w3.org/2000/svg" role="img" '
             f'aria-label="AGENTCRAFT per-week trend">']

    # gridlines at 0/25/50/75/100
    for gy in (0, 25, 50, 75, 100):
        _, y = xy(0, gy)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" '
                     f'stroke="{PALETTE["line"]}" stroke-width="1" opacity="0.5"/>')

    # week labels along the bottom
    for i, t in enumerate(pts):
        x, _ = xy(i, 0)
        wk = str(t.get("week", ""))
        wk_short = wk.split("-")[-1] if "-" in wk else wk  # e.g. "2026-W36" -> "W36"
        anchor = "middle"
        if i == 0:
            anchor = "start"
        elif i == n - 1:
            anchor = "end"
        parts.append(
            f'<text x="{x:.1f}" y="{h - 8}" fill="{PALETTE["ink_faint"]}" '
            f'font-size="10" text-anchor="{anchor}" '
            f'font-family="Segoe UI, Roboto, Helvetica, Arial, sans-serif">'
            f'{_esc(wk_short)}</text>')

    # each series: polyline + end-dot; skip a series entirely if it has no data
    for key, _lbl, color in series:
        vals = [t.get(key) for t in pts]
        if all(v is None for v in vals):
            continue
        line_pts = " ".join(f"{x:.1f},{y:.1f}"
                            for x, y in (xy(i, v) for i, v in enumerate(vals)))
        parts.append(f'<polyline points="{line_pts}" fill="none" '
                     f'stroke="{color}" stroke-width="2.5" stroke-linejoin="round" '
                     f'stroke-linecap="round"/>')
        # end dot + value at the last real point
        last_i = max(i for i, v in enumerate(vals) if v is not None)
        ex, ey = xy(last_i, vals[last_i])
        parts.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" fill="{color}"/>')
        parts.append(
            f'<text x="{ex - 6:.1f}" y="{ey - 6:.1f}" fill="{color}" '
            f'font-size="11" font-weight="800" text-anchor="end" '
            f'font-family="Segoe UI, Roboto, Helvetica, Arial, sans-serif">'
            f'{int(round(vals[last_i]))}</text>')

    parts.append("</svg>")
    svg = "".join(parts)

    # legend (built from the same series list, only series that were plotted)
    legend = []
    for key, lbl, color in series:
        if any(t.get(key) is not None for t in pts):
            legend.append(f'<span class="leg"><span class="leg-dot" '
                          f'style="background:{color}"></span>{_esc(lbl)}</span>')

    return f'''
      <div class="panel">
        <div class="panel-title">TREND · P6/P7 COMPOUNDING</div>
        <div class="trend-legend">{"".join(legend)}</div>
        <div class="trend-svg">{svg}</div>
        <div class="desc-note">The moat lines rising over weeks is the whole thesis — continuity + discipline compound.</div>
      </div>'''


_COST_TONE = {
    "rework": PALETTE["weak"],
    "wasted-context": PALETTE["warn"],
    "undetected-defect": PALETTE["weak"],
    "manual-toil": PALETTE["warn"],
    "stalled-thread": PALETTE["ink_dim"],
}


def _practices_panel(report: dict) -> str:
    """PRACTICES (durable good habits) + ANTI-PATTERNS (recurring costs).

    SPEC 5b/7.7 — the positive/negative meta-pattern layer, brave-honest in both
    directions. Each item is evidence-anchored by the producer; the renderer just
    surfaces area + (cost) + text. Renders nothing if both arrays are empty (v1).
    """
    practices = report.get("practices", []) or []
    anti = report.get("anti_patterns", []) or []
    if not practices and not anti:
        return ""

    def prac_rows():
        rows = []
        for p in practices:
            if not isinstance(p, dict):
                continue
            area = p.get("area", "")
            habit = p.get("habit", p.get("observation", ""))
            rows.append(f'''
          <div class="pa-row pa-good">
            <span class="pa-pill pa-pill-good">{_esc(area)}</span>
            <span class="pa-txt">{_esc(habit)}</span>
          </div>''')
        return "".join(rows)

    def anti_rows():
        rows = []
        for a in anti:
            if not isinstance(a, dict):
                continue
            area = a.get("area", "")
            cost = a.get("cost", "")
            obs = a.get("observation", a.get("habit", ""))
            cost_tone = _COST_TONE.get(cost, PALETTE["ink_dim"])
            cost_tag = (f'<span class="pa-cost" style="color:{cost_tone};'
                        f'border-color:{cost_tone}66">{_esc(cost)}</span>'
                        if cost else "")
            rows.append(f'''
          <div class="pa-row pa-bad">
            <span class="pa-pill pa-pill-bad">{_esc(area)}</span>
            <span class="pa-txt">{_esc(obs)}{cost_tag}</span>
          </div>''')
        return "".join(rows)

    blocks = []
    if practices:
        blocks.append(f'<div class="pa-sub-title">DURABLE PRACTICES</div>{prac_rows()}')
    if anti:
        blocks.append(f'<div class="pa-sub-title pa-sub-bad">ANTI-PATTERNS &amp; COSTS</div>{anti_rows()}')

    return f'''
      <div class="panel">
        <div class="panel-title">PRACTICES &amp; ANTI-PATTERNS</div>
        {"".join(blocks)}
        <div class="desc-note">Brave-honest in both directions — descriptive, never scored.</div>
      </div>'''


# =============================================================================
# PAGE 1 -- SHAREABLE RESULT CARD (redacted). The public, viral,
# screenshot-able artifact. OVERALL + tier + 7-axis radar + 7 pillar scores +
# % VERIFIED + a short self-opinion. STRIPPED of everything private: no repo path,
# no filenames, no code, no evidence, no excerpts, no sub-signal count hints, no
# coaching prose. A machine-enforced redaction guard refuses to write it if any
# path/uuid/basename leak survives -- "no leak in the shareable artifact" is an
# invariant, not a promise. Still 100% local + zero-egress (system fonts only).
# =============================================================================

# Leak detector for the shareable page: paths, drive letters, /Users/, source
# file extensions, and session-UUID prefixes. Mirrors SKILL.md sec 7b's redaction
# grep so the renderer and the runbook agree bit-for-bit.
_LEAK_RE = re.compile(
    # Drive-letter branch: a SINGLE letter + ':\' or ':/', NOT preceded by another
    # letter. The negative lookbehind is load-bearing -- without it, the 'p:/' inside
    # a URL scheme (e.g. the SVG namespace "http://www.w3.org/2000/svg", or "https://")
    # matches as a fake "P:\ drive path" and the guard false-positives, blocking the
    # (perfectly clean) shareable card. A real leak (C:\Users, D:/data) is preceded by
    # whitespace/quote/paren, never a letter -- so it still fires. Verified against both.
    r"((?<![A-Za-z])[A-Za-z]:[\\/]"   # C:\ or C:/  (a Windows path; not a URL scheme)
    r"|/[Uu]sers/"                     # /Users/ or /users/  (a POSIX home path)
    r"|/home/"                         # /home/  (a Linux home path)
    r"|\.py\b|\.ts\b|\.tsx\b|\.js\b|\.jsx\b|\.json\b|\.md\b"   # a source filename
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"                    # a session UUID
    r")")


def _redaction_guard(share_html: str) -> None:
    """Fail-loud: refuse to emit a shareable page carrying any private substrate.

    Scans the ALREADY-ASSEMBLED share HTML for path/filename/UUID leaks. If one
    survives, we raise -- the caller must NOT write the shareable file. This makes
    "the shareable artifact contains no filenames/paths/evidence" a machine-checked
    invariant. Purely local text hygiene; no network, ever.
    """
    hits = []
    for m in _LEAK_RE.finditer(share_html):
        s = max(0, m.start() - 24)
        e = min(len(share_html), m.end() + 24)
        hits.append(share_html[s:e].replace("\n", " ").strip())
    if hits:
        raise ValueError(
            "REDACTION LEAK in shareable card (page 1) -- refusing to write it. "
            "The shareable artifact must carry NO path/filename/UUID/evidence. "
            "Offending fragments: " + " | ".join(hits[:6]))


def _self_opinion(report: dict, tier: str) -> str:
    """A short, redacted self-opinion sentence for the share card (no evidence).

    Synthesized from the tier + the strongest/weakest pillar LABELS only -- pillar
    names are public (they print on the radar), and no counts/paths/excerpts are
    used. Prove-don't-declare: an honest read of the shape, warm + second-person.
    """
    pillars = report.get("pillars", {}) or {}
    scored = [(k, pillars[k].get("score")) for k in PILLAR_ORDER
              if isinstance(pillars.get(k, {}).get("score"), (int, float))]
    tier_line = {
        "diamond": "Elite collaboration -- you work with agents like a systems architect.",
        "gold":    "Strong, disciplined collaboration with real room to compound.",
        "silver":  "Solid fundamentals -- a few habits away from the next tier.",
        "bronze":  "Early days -- the growth plan turns this into momentum fast.",
    }.get(tier, "An honest read of how you work with AI agents.")
    if not scored:
        return tier_line
    scored.sort(key=lambda kv: kv[1])
    weakest = PILLAR_LABELS[scored[0][0]]
    strongest = PILLAR_LABELS[scored[-1][0]]
    if scored[0][0] == scored[-1][0]:
        return tier_line
    return (f"{tier_line} Your edge is <b>{_esc(strongest)}</b>; "
            f"your biggest lever right now is <b>{_esc(weakest)}</b>.")


def build_share_html(report: dict, nav_href: str | None = None) -> str:
    """PAGE 1 -- the REDACTED shareable result card.

    Reuses the public dark-indigo/cyan/violet FUT card palette (already the brand
    look). Renders OVERALL + tier + the 7-axis radar + 7 pillar SCORES (numbers
    reveal nothing private, per SKILL sec 7b) + % VERIFIED + a short self-opinion.
    Deliberately OMITS: repo_path, generated_at, evidence, excerpts, sub-signal
    count hints, coaching, practices, profile/style. The caller runs
    `_redaction_guard` before writing it (fail-loud on any leak).

    `nav_href` (optional): a BARE .html basename (no path, no drive letter) of the
    private command-center page. When given, a tasteful call-to-action pill is
    rendered near the footer so a reader can WALK into the full audit. It MUST be a
    bare basename -- a directory/drive path would trip `_redaction_guard` (and leak
    a filesystem hint). Default None keeps the original single-arg behavior (no nav).
    """
    overall = report["overall"]
    oscore = int(round(overall.get("score", 0)))
    tier = overall.get("tier", tier_for(oscore,
                        (report.get("config", {}) or {}).get("tier_bands")))
    ts = TIER_STYLE.get(tier, TIER_STYLE["silver"])

    radar = build_radar_svg(report)
    opinion = _self_opinion(report, tier)

    verified = (report.get("meta_metrics", {}) or {}).get("verified_rate", {}) or {}
    ver_pct = verified.get("pct")
    ver_cell = ""
    if ver_pct is not None:
        vt = _score_color(ver_pct)
        ver_cell = (f'<div class="share-verified">'
                    f'<span class="sv-num" style="color:{vt}">{int(ver_pct)}%</span>'
                    f'<span class="sv-cap">VERIFIED</span></div>')

    chips = []
    for key in PILLAR_ORDER:
        p = report["pillars"][key]
        score = p.get("score")
        color = _score_color(score)
        moat = key in MOAT_PILLARS
        moat_dot = '<span class="sp-moat">&#9670;</span>' if moat else ""
        chips.append(
            f'<div class="share-pill">'
            f'<span class="sp-key">{_esc(key)}</span>'
            f'<span class="sp-name">{_esc(PILLAR_SHORT[key])}{moat_dot}</span>'
            f'<span class="sp-score" style="color:{color}">{_fmt_score(score)}</span>'
            f'</div>')
    pill_chips = "".join(chips)

    # Optional walk-into-the-audit CTA. `nav_href` is a bare .html basename, so it
    # is redaction-safe (no path/drive/UUID). Escaped defensively even though it is
    # a controlled basename. Renders nothing when nav_href is None (default).
    nav_cell = ""
    if nav_href:
        nav_cell = (f'<div class="share-nav">'
                    f'<a class="share-cta" href="{_esc(nav_href)}">'
                    f'&#128269;&nbsp;&nbsp;View the full command-center audit '
                    f'<span class="cta-arrow">&rarr;</span></a></div>')

    # FAZA 1 — LENS A framing (this share card is about how YOU work with agents:
    # your habits, your memory/continuity, your coaching plan — NOT your codebase).
    # Copy/emphasis only; the score + radar + pillar data are untouched.
    lens_cap = ('<div class="share-lens">LENS&nbsp;A &middot; '
                '<b>YOU</b> &mdash; how you work with agents</div>')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(BRAND)} card</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: radial-gradient(1200px 800px at 20% -10%, {PALETTE["bg1"]} 0%, {PALETTE["bg0"]} 60%);
    color: {PALETTE["ink"]};
    font-family: {_FONT_STACK};
    -webkit-font-smoothing: antialiased;
  }}
  .share-stage {{ width: 720px; padding: 34px; margin: 0 auto; }}
  .card {{
    position: relative; border-radius: 24px; padding: 30px 30px 26px;
    background:
      linear-gradient(160deg, {ts["accent"]}22 0%, transparent 42%),
      linear-gradient(180deg, {PALETTE["card_top"]} 0%, {PALETTE["card_bot"]} 100%);
    border: 1px solid {PALETTE["line"]};
    box-shadow: 0 24px 60px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04);
    overflow: hidden;
  }}
  .card::before {{
    content: ""; position: absolute; inset: 0; border-radius: 24px; padding: 1px;
    background: linear-gradient(140deg, {ts["accent"]}, transparent 40%, {ts["accent2"]}88);
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude; pointer-events: none;
  }}
  .brand-row {{ display:flex; align-items:baseline; justify-content:space-between; }}
  .brand {{
    font-size: 28px; font-weight: 900; letter-spacing: 3px;
    background: linear-gradient(90deg, {ts["accent"]}, {ts["accent2"]});
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }}
  .brand-tag {{ font-size: 12px; color: {PALETTE["ink_faint"]}; letter-spacing:.5px; }}

  .hero {{ display:flex; align-items:center; gap: 24px; margin: 22px 0 6px; }}
  .overall {{
    font-size: 108px; font-weight: 900; line-height: 0.9; color: {ts["accent"]};
    text-shadow: 0 0 30px {ts["accent"]}44; font-variant-numeric: tabular-nums;
  }}
  .overall-side {{ display:flex; flex-direction:column; gap:10px; }}
  .overall-cap {{ font-size:13px; letter-spacing:2px; color:{PALETTE["ink_dim"]}; font-weight:700; }}
  .tier-badge {{
    display:inline-block; padding: 7px 16px; border-radius: 999px;
    font-size: 15px; font-weight: 900; letter-spacing: 2px; color: {PALETTE["bg0"]};
    background: linear-gradient(90deg, {ts["accent"]}, {ts["accent2"]});
    box-shadow: 0 6px 18px {ts["accent"]}44; width: fit-content;
  }}
  .share-verified {{ display:flex; align-items:baseline; gap:8px; margin-top:4px; }}
  .sv-num {{ font-size:22px; font-weight:900; font-variant-numeric:tabular-nums; }}
  .sv-cap {{ font-size:10px; letter-spacing:2px; color:{PALETTE["ink_faint"]}; font-weight:700; }}

  .radar-wrap {{ display:flex; justify-content:center; margin: 6px 0 2px; }}

  .opinion {{
    margin: 10px 4px 18px; font-size: 15px; line-height: 1.55;
    color: {PALETTE["ink_dim"]}; text-align:center;
  }}
  .opinion b {{ color: {ts["accent"]}; font-weight: 800; }}

  .share-pills {{ display:grid; grid-template-columns: repeat(7,1fr); gap: 8px; margin-top: 4px; }}
  .share-pill {{
    display:flex; flex-direction:column; align-items:center; gap:2px;
    background:{PALETTE["bg0"]}88; border:1px solid {PALETTE["line"]};
    border-radius:12px; padding:10px 4px;
  }}
  .sp-key {{ font-family:{_MONO_STACK}; font-size:9px; color:{PALETTE["ink_faint"]}; font-weight:700; }}
  .sp-name {{ font-size:9px; color:{PALETTE["ink_dim"]}; font-weight:700; letter-spacing:.3px; text-align:center; }}
  .sp-moat {{ color:{PALETTE["moat"]}; font-size:8px; margin-left:2px; }}
  .sp-score {{ font-size:20px; font-weight:900; font-variant-numeric:tabular-nums; margin-top:2px; }}

  /* FAZA 1 — LENS A caption strip (frames the card as "YOU · how you work") */
  .share-lens {{ text-align:center; margin: 4px 0 14px; font-size: 11px;
    letter-spacing: 1.5px; font-weight: 700; text-transform: uppercase;
    color: {PALETTE["ink_faint"]}; }}
  .share-lens b {{ color: {ts["accent"]}; }}

  .share-nav {{ display:flex; justify-content:center; margin-top: 22px; }}
  .share-cta {{
    display:inline-flex; align-items:center; gap:2px; text-decoration:none;
    padding: 12px 24px; border-radius: 999px;
    font-size: 14px; font-weight: 800; letter-spacing:.4px;
    color: {PALETTE["bg0"]};
    background: linear-gradient(90deg, {ts["accent"]}, {ts["accent2"]});
    box-shadow: 0 8px 24px {ts["accent"]}44, inset 0 1px 0 rgba(255,255,255,.25);
    border: 1px solid {ts["accent"]}66;
    transition: transform .15s ease, box-shadow .15s ease;
  }}
  .share-cta:hover {{ transform: translateY(-1px); box-shadow: 0 12px 30px {ts["accent"]}66; }}
  .cta-arrow {{ margin-left:8px; font-weight:900; }}

  .share-foot {{ text-align:center; margin-top: 20px; font-size: 11px; color:{PALETTE["ink_faint"]}; }}
  .share-foot b {{ color:{PALETTE["ink_dim"]}; }}
</style>
</head>
<body>
  <div class="share-stage" id="agentcraft-share">
    <div class="card">
      <div class="brand-row">
        <div class="brand">{_esc(BRAND)}</div>
        <div class="brand-tag">{_esc(TAGLINE)}</div>
      </div>

      {lens_cap}

      <div class="hero">
        <div class="overall">{oscore}</div>
        <div class="overall-side">
          <div class="overall-cap">OVERALL</div>
          <div class="tier-badge">{_esc(ts["label"])}</div>
          {ver_cell}
        </div>
      </div>

      <div class="radar-wrap">{radar}</div>

      <div class="opinion">{opinion}</div>

      <div class="share-pills">{pill_chips}</div>
    </div>

    {nav_cell}

    <div class="share-foot">
      <b>{_esc(BRAND)}</b> &middot; Lens A &mdash; how you WORK with AI agents:
      habits, memory &amp; continuity, your coaching plan &middot;
      scored 100% locally, nothing sent anywhere &middot; open-source (MIT)
    </div>
  </div>
</body>
</html>'''


# =============================================================================
# PAGE 2 -- PRIVATE DEPTH DASHBOARD in a dark HUD aesthetic.
# The full growth-plan deep coaching + FROM-YOUR-WORK excerpts +
# trend + per-sub-signal + strengths + profile/style + practices, restyled in
# a cosmic command-center look: starfield background, Cinzel display headings,
# JetBrains Mono data, gold gradient section titles, glass cards, gold/cyan
# glows. Stays LOCAL + git-ignored, NEVER shared.
#
# ZERO-EGRESS FONT CAVEAT (load-bearing): the HUD references
# Cinzel/Inter/JetBrains Mono, which normally load from the Google Fonts CDN.
# AGENTCRAFT is zero-network, so we DO NOT add a <link href="fonts.googleapis.com">.
# Instead we declare the same families as a FONT STACK WITH SYSTEM FALLBACKS -- if
# the user has them installed they render; otherwise a graceful serif/mono/sans
# fallback. This preserves zero third-party egress. No remote font fetch, ever.
# =============================================================================

# HUD design tokens (a self-contained dark theme; no external stylesheet).
HUD = {
    "void": "#03020a",
    "deep": "#0a0716",
    "gold": "#d4af37",
    "gold_bright": "#ffd966",
    "cyan": "#41e0d0",
    "violet": "#a78bfa",
    "ink": "#eae6f5",
    "ink_dim": "#9a92b8",
    "ink_faint": "#5f5880",
    "line": "#241c40",
    "good": "#4ade80",
    "warn": "#fbbf24",
    "weak": "#f87171",
    "glass_a": "rgba(20,12,50,.85)",
    "glass_b": "rgba(35,20,70,.72)",
}
# Display / mono / body stacks -- HUD family FIRST, then system fallbacks
# (installed-or-graceful; NO remote fetch -> zero-egress preserved).
_HUD_DISPLAY = "'Cinzel', 'Trajan Pro', 'Playfair Display', Georgia, 'Times New Roman', serif"
_HUD_MONO = "'JetBrains Mono', 'Cascadia Code', 'SFMono-Regular', 'Consolas', monospace"
_HUD_BODY = "'Inter', 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"


# =============================================================================
# LENS B (your CODE) — CODE-AUDIT contract (SPEC.md / agentcraft_repo_scan.py).
# A code-audit report is AXES-based (C1..C8), not pillar-based. These constants
# are the renderer's fixed contract for build_repo_html — parallel to
# PILLAR_ORDER/PILLAR_LABELS for Lens A, so the two lenses stay symmetric.
# =============================================================================
CODE_AXIS_ORDER = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"]
# The scanner keys axes as "C1_architecture_structure" etc. Map the SHORT code
# (C1) both to the long report key and to a compact human label.
CODE_AXIS_KEYS = {
    "C1": "C1_architecture_structure",
    "C2": "C2_reliability_errorhandling",
    "C3": "C3_security_secrets",
    "C4": "C4_tests_coverage",
    "C5": "C5_maintainability_complexity",
    "C6": "C6_performance_efficiency",
    "C7": "C7_documentation_readability",
    "C8": "C8_dependencies_techdebt",
}
CODE_AXIS_LABELS = {
    "C1": "Architecture & Structure",
    "C2": "Reliability & Error-handling",
    "C3": "Security & Secrets",
    "C4": "Tests & Coverage",
    "C5": "Maintainability & Complexity",
    "C6": "Performance Efficiency",
    "C7": "Documentation & Readability",
    "C8": "Dependencies & Tech Debt",
}

# Severity tone for a finding/risk chip (dark-HUD palette; descriptive only).
_SEVERITY_TONE = {
    "critical": HUD["weak"],
    "high": HUD["weak"],
    "medium": HUD["warn"],
    "low": HUD["cyan"],
    "info": HUD["ink_dim"],
}


def _code_axis_lookup(axes: dict, short: str) -> dict:
    """Fetch an axis object by short code (C1..C8), tolerating either the long
    report key (`C1_architecture_structure`) or the bare short key (`C1`).

    Never fabricates: returns {} if the axis is absent, so the caller renders an
    honest "unmeasured/absent" state rather than a made-up score.
    """
    if not isinstance(axes, dict):
        return {}
    long_key = CODE_AXIS_KEYS.get(short, short)
    val = axes.get(long_key)
    if isinstance(val, dict):
        return val
    val = axes.get(short)
    return val if isinstance(val, dict) else {}


def _code_axis_bars(report: dict) -> str:
    """Per-axis score bars for all 8 code-audit axes (C1..C8) — HUD micro-bars.

    Reuses the same `.stat` / `.bar` / `.bar-fill` classes as _pillar_stat_rows
    so the code-audit dashboard shares the depth page's aesthetic exactly. An
    axis that is absent or measurement_status:"unmeasured" (score null) renders
    an honest N/A row with a dimmed limitation tag — never a fabricated bar.
    """
    axes = report.get("axes", {}) or {}
    rows = []
    for short in CODE_AXIS_ORDER:
        ax = _code_axis_lookup(axes, short)
        score = ax.get("score")
        name = ax.get("name") or CODE_AXIS_LABELS.get(short, short)
        eligible = ax.get("eligible", True)
        measured = (ax.get("measurement_status", "measured") != "unmeasured")
        color = _score_color(score)
        bar_pct = 0 if not isinstance(score, (int, float)) else max(0, min(100, int(round(score))))
        na_tag = ""
        if not eligible or not measured or not isinstance(score, (int, float)):
            lim = ax.get("limitations")
            lim_txt = _LIMITATION_SHORT.get(lim, "unmeasured")
            na_tag = f'<span class="na-tag">{_esc(lim_txt)}</span>'
        rows.append(f'''
        <div class="stat">
          <div class="stat-head">
            <span class="stat-key">{_esc(short)}</span>
            <span class="stat-name">{_esc(name)}{na_tag}</span>
            <span class="stat-score" style="color:{color}">{_fmt_score(score)}</span>
          </div>
          <div class="bar"><div class="bar-fill" style="width:{bar_pct}%;
               background:linear-gradient(90deg,{color},{color}cc)"></div></div>
        </div>''')
    return "".join(rows)


def _code_findings(report: dict, key: str = "findings",
                   empty_msg: str = "No findings recorded.") -> str:
    """Render an audit findings/risks list (the coaching surface for Lens B).

    Each finding is a producer-supplied dict: {axis, severity, title, what, why,
    how, evidence[]}. We surface axis + severity chip + title + the what/why/how
    rows, reusing the depth page's `.coach*` classes so the CODE audit reads like
    the same command-center. Evidence PATHS are shown here (this is the PRIVATE
    page 2 — never redacted; the shareable card is Lens A only). Counts only,
    never a secret VALUE (the report carries counts, not secret contents).

    `key` selects which list ("findings" or "risks"); renders an honest empty
    note if the list is absent/empty. Never fabricates an entry.
    """
    items = report.get(key, []) or []
    if not items:
        return f'<div class="empty">{_esc(empty_msg)}</div>'
    cards = []
    for f in items:
        if not isinstance(f, dict):
            continue
        axis = f.get("axis", "")
        sev = str(f.get("severity", "")).lower()
        sev_tone = _SEVERITY_TONE.get(sev, HUD["ink_dim"])
        sev_chip = (f'<span class="rf-sev" style="color:{sev_tone};'
                    f'border-color:{sev_tone}66">{_esc(sev.upper())}</span>'
                    if sev else "")
        what = f.get("what", "")
        what_row = (f'''
          <div class="coach-row"><span class="lbl weak-lbl">WHAT</span>
               <span class="txt txt-weak">{_esc(what)}</span></div>''' if what else "")
        why = f.get("why", "")
        why_row = (f'''
          <div class="coach-row"><span class="lbl why-lbl">WHY</span>
               <span class="txt">{_esc(why)}</span></div>''' if why else "")
        how = f.get("how", "")
        how_row = (f'''
          <div class="coach-row"><span class="lbl how-lbl">FIX</span>
               <span class="txt">{_esc(how)}</span></div>''' if how else "")
        # Evidence: producer-supplied path + note (PRIVATE page — paths shown).
        ev_block = ""
        ev = f.get("evidence", []) or []
        ev_rows = []
        for e in ev:
            if not isinstance(e, dict):
                continue
            path = e.get("path", "")
            note = e.get("note", "")
            if not path and not note:
                continue
            ev_rows.append(f'<div class="rf-ev"><code class="rf-ev-path">'
                           f'{_esc(path)}</code>'
                           f'<span class="rf-ev-note">{_esc(note)}</span></div>')
        if ev_rows:
            ev_block = (f'<div class="rf-ev-wrap"><span class="rf-ev-cap">'
                        f'EVIDENCE</span>{"".join(ev_rows)}</div>')
        cards.append(f'''
        <div class="coach">
          <div class="coach-head">
            <span class="coach-pill">{_esc(axis)}</span>
            <span class="coach-title">{_esc(f.get("title", ""))}</span>
            {sev_chip}
          </div>
          {what_row}
          {why_row}
          {how_row}
          {ev_block}
        </div>''')
    if not cards:
        return f'<div class="empty">{_esc(empty_msg)}</div>'
    return "".join(cards)


def _code_strengths(report: dict) -> str:
    """Code-audit strengths list — reuses the depth `.strength` classes.

    Tolerates {axis, note} dicts OR plain strings (prove-don't-declare — only
    what the producer supplied). Renders nothing if empty.
    """
    strengths = report.get("strengths", []) or []
    if not strengths:
        return ""
    items = []
    for s in strengths:
        if isinstance(s, str):
            pill, txt = "", s
        elif isinstance(s, dict):
            pill = s.get("axis", s.get("pillar", ""))
            txt = s.get("note", s.get("text", ""))
        else:
            continue
        items.append(f'''
        <div class="strength">
          <span class="strength-pill">{_esc(pill)}</span>
          <span class="strength-txt">{_esc(txt)}</span>
        </div>''')
    if not items:
        return ""
    return f'''
    <div class="panel-title">STRENGTHS</div>
    <div class="strengths">{"".join(items)}</div>'''


def _code_refactor_priorities(report: dict) -> str:
    """REFACTOR PRIORITIES — an ordered, highest-leverage-first punch list.

    Derived deterministically from the report (no fabrication): if the producer
    supplies an explicit `refactor_priorities` list we render it verbatim;
    otherwise we synthesize it from `findings` ordered by severity (critical >
    high > medium > low), showing axis + title + the FIX line. This is the "do
    these next" surface a builder acts on. Renders an honest empty note if there
    is nothing to prioritize.
    """
    explicit = report.get("refactor_priorities", []) or []
    rows = []
    if explicit:
        for i, p in enumerate(explicit, 1):
            if isinstance(p, str):
                axis, title, fix = "", p, ""
            elif isinstance(p, dict):
                axis = p.get("axis", "")
                title = p.get("title", p.get("what", ""))
                fix = p.get("how", p.get("fix", ""))
            else:
                continue
            rows.append((i, axis, title, fix))
    else:
        sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        findings = [f for f in (report.get("findings", []) or [])
                    if isinstance(f, dict)]
        findings.sort(key=lambda f: sev_rank.get(str(f.get("severity", "")).lower(), 5))
        for i, f in enumerate(findings, 1):
            rows.append((i, f.get("axis", ""), f.get("title", ""), f.get("how", "")))
    if not rows:
        return '<div class="empty">Nothing flagged for refactor — healthy shape.</div>'
    out = []
    for i, axis, title, fix in rows:
        axis_chip = (f'<span class="rp-axis">{_esc(axis)}</span>' if axis else "")
        fix_row = (f'<div class="rp-fix">{_esc(fix)}</div>' if fix else "")
        out.append(f'''
        <div class="rp-row">
          <span class="rp-num">{i}</span>
          <div class="rp-body">
            <div class="rp-head">{axis_chip}<span class="rp-title">{_esc(title)}</span></div>
            {fix_row}
          </div>
        </div>''')
    return f'<div class="rp-list">{"".join(out)}</div>'


def _code_scan_meta(report: dict) -> str:
    """A compact SCAN META strip for the code-audit page (files/LOC/languages).

    Reads `scan_ref` (files, LOC, per-language counts) — descriptive context,
    never scored. Renders nothing extra when absent (honest-empty).
    """
    sr = report.get("scan_ref", {}) or {}
    cells = []

    def cell(label, big, sub, tone=HUD["cyan"]):
        big_s = "—" if big is None else _esc(big)
        return (f'<div class="meta-cell"><div class="meta-label">{_esc(label)}</div>'
                f'<div class="meta-big" style="color:{tone}">{big_s}</div>'
                f'<div class="meta-sub">{sub}</div></div>')

    files = sr.get("total_files")
    loc = sr.get("total_loc")
    langs = sr.get("languages", {}) or {}
    # Top 3 languages by count, for the sub-line.
    lang_sub = ""
    if isinstance(langs, dict) and langs:
        top = sorted(((k, v) for k, v in langs.items()
                      if isinstance(v, (int, float))),
                     key=lambda kv: kv[1], reverse=True)[:3]
        lang_sub = " · ".join(f"{_esc(k)} {int(v)}" for k, v in top)

    cells.append(cell("FILES", (str(int(files)) if isinstance(files, (int, float)) else None),
                      "in scan scope"))
    cells.append(cell("LINES", (f"{int(loc):,}" if isinstance(loc, (int, float)) else None),
                      "total LOC", HUD["violet"]))
    cells.append(cell("LANGUAGES",
                      (str(len(langs)) if isinstance(langs, dict) and langs else None),
                      lang_sub, HUD["gold_bright"]))
    n = len(cells)
    return (f'<div class="meta-strip" style="grid-template-columns:repeat({n},1fr);">'
            f'{"".join(cells)}</div>'
            f'<div class="meta-note">Scan context — descriptive, NOT part of the code grade.</div>')


def build_depth_html(report: dict, nav_href: str | None = None) -> str:
    """PAGE 2 -- the PRIVATE depth dashboard (dark HUD aesthetic).

    Full coaching + FROM-YOUR-WORK excerpts + trend + per-sub-signal + strengths
    + profile/style + practices/anti-patterns. Reuses the existing depth builders
    (_coaching_cards, _trend_sparkline, _profile_style_strip, _practices_panel,
    _pillar_stat_rows, _meta_strip) -- the HUD styling is applied via this page's
    own <style> (glass cards, starfield, gold section titles). Rendered with the
    full-height PNG capture so nothing clips.

    `nav_href` (optional): a bare .html basename of the shareable card. When given,
    an unobtrusive top-left "back to the shareable card" link is rendered so the
    reader can walk BACK out of the audit. Default None keeps the single-arg
    behavior (no nav). This page is private (never redaction-guarded), but we still
    keep nav_href a bare basename for symmetry + safety.
    """
    overall = report["overall"]
    oscore = int(round(overall.get("score", 0)))
    tier = overall.get("tier", tier_for(oscore,
                        (report.get("config", {}) or {}).get("tier_bands")))
    ts = TIER_STYLE.get(tier, TIER_STYLE["silver"])
    subject = report.get("subject", {}) or {}
    label = subject.get("label", "local-user")
    repo_path = subject.get("repo_path", "")
    generated = report.get("generated_at", "")
    target = (report.get("config", {}) or {}).get("target", 75)

    radar = build_radar_svg(report)
    stats = _pillar_stat_rows(report)
    meta = _meta_strip(report)
    coaching = _coaching_cards(report)
    strengths = _strengths_list(report)
    profile_style = _profile_style_strip(report)
    trend = _trend_sparkline(report)
    practices = _practices_panel(report)

    repo_line = (f'<div class="hud-repo">{_esc(repo_path)}</div>'
                 if repo_path else "")

    # Optional back-to-the-card link (unobtrusive, top-left). Rendered nothing when
    # nav_href is None (default single-arg behavior). `back_row` is the full wrapped
    # markup (precomputed here so the f-string body carries no backslash -- Py3.11
    # disallows a backslash inside an f-string expression).
    back_row = ""
    if nav_href:
        back_row = (f'<div class="hud-backrow">'
                    f'<a class="hud-back" href="{_esc(nav_href)}">'
                    f'<span class="back-arrow">&larr;</span>&nbsp;&nbsp;'
                    f'Back to the shareable card</a></div>')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(BRAND)} depth dashboard (private) — {_esc(label)}</title>
<style>
  /* ==== Depth HUD — cosmic dark, gold + neon accents ====
     Fonts: HUD family first, SYSTEM FALLBACKS after. NO remote font fetch (zero-egress). */
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: {HUD["void"]};
    color: {HUD["ink"]};
    font-family: {_HUD_BODY};
    -webkit-font-smoothing: antialiased;
    position: relative;
    overflow-x: hidden;
  }}
  body::before {{
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
      radial-gradient(900px 640px at 12% -8%, rgba(167,139,250,.16) 0%, transparent 58%),
      radial-gradient(820px 620px at 92% 4%, rgba(65,224,208,.12) 0%, transparent 60%),
      radial-gradient(1100px 900px at 50% 120%, rgba(212,175,55,.10) 0%, transparent 62%);
  }}
  .starfield, .stars-near {{ position: fixed; inset: 0; z-index: 0; pointer-events: none; }}
  .starfield::before, .starfield::after, .stars-near::before {{
    content: ""; position: absolute; inset: -50%; width: 200%; height: 200%;
  }}
  .starfield::before {{
    background-image:
      radial-gradient(1.4px 1.4px at 20% 30%, rgba(255,255,255,.85) 50%, transparent),
      radial-gradient(1.2px 1.2px at 70% 60%, rgba(255,240,200,.7) 50%, transparent),
      radial-gradient(1px 1px at 40% 80%, rgba(200,220,255,.6) 50%, transparent),
      radial-gradient(1.3px 1.3px at 85% 25%, rgba(255,255,255,.7) 50%, transparent),
      radial-gradient(1px 1px at 15% 65%, rgba(255,255,255,.5) 50%, transparent);
    background-size: 620px 620px, 520px 520px, 440px 440px, 700px 700px, 380px 380px;
    animation: drift 180s linear infinite;
  }}
  .starfield::after {{
    background-image:
      radial-gradient(1px 1px at 55% 15%, rgba(255,255,255,.55) 50%, transparent),
      radial-gradient(1.6px 1.6px at 30% 50%, rgba(255,225,180,.8) 50%, transparent),
      radial-gradient(1px 1px at 78% 85%, rgba(210,225,255,.55) 50%, transparent);
    background-size: 800px 800px, 560px 560px, 660px 660px;
    animation: drift 260s linear infinite reverse, twinkle 6s ease-in-out infinite;
    opacity: .8;
  }}
  .stars-near::before {{
    background-image:
      radial-gradient(2px 2px at 60% 40%, rgba(255,240,210,.9) 50%, transparent),
      radial-gradient(2.2px 2.2px at 25% 70%, rgba(255,255,255,.85) 50%, transparent);
    background-size: 900px 900px, 1000px 1000px;
    animation: drift 120s linear infinite, twinkle 4.5s ease-in-out infinite;
  }}
  @keyframes drift {{ from {{ transform: translate(0,0); }} to {{ transform: translate(-140px,-90px); }} }}
  @keyframes twinkle {{ 0%,100% {{ opacity:.6; }} 50% {{ opacity:1; }} }}

  .hud-stage {{
    position: relative; z-index: 2;
    width: 1200px; padding: 40px 40px 30px; margin: 0 auto;
    display: grid; grid-template-columns: 430px 1fr; gap: 30px; align-items: start;
  }}

  .glass-card {{
    position: relative; border-radius: 22px; padding: 26px 26px 22px;
    background: linear-gradient(135deg, {HUD["glass_a"]}, {HUD["glass_b"]});
    border: 1px solid rgba(212,175,55,.24);
    box-shadow: 0 24px 70px rgba(0,0,0,.6), 0 0 40px rgba(212,175,55,.10),
                inset 0 1px 0 rgba(255,255,255,.05);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    overflow: hidden;
  }}
  .hud-brandrow {{ display:flex; align-items:baseline; justify-content:space-between; }}
  .hud-brand {{
    font-family: {_HUD_DISPLAY}; font-size: 30px; font-weight: 800; letter-spacing: 4px;
    background: linear-gradient(90deg, {HUD["gold"]}, {HUD["gold_bright"]});
    -webkit-background-clip: text; background-clip: text; color: transparent;
    text-shadow: 0 0 24px rgba(212,175,55,.4);
  }}
  .hud-private {{
    font-family:{_HUD_MONO}; font-size: 9px; letter-spacing:2px; font-weight:700;
    color: {HUD["cyan"]}; border:1px solid {HUD["cyan"]}55; border-radius:999px;
    padding:3px 9px; background:{HUD["cyan"]}12;
  }}
  .hud-hero {{ display:flex; align-items:center; gap:20px; margin:20px 0 6px; }}
  .hud-overall {{
    font-family:{_HUD_DISPLAY}; font-size: 94px; font-weight: 800; line-height:.9;
    color:{ts["accent"]}; text-shadow: 0 0 34px {ts["accent"]}55;
    font-variant-numeric: tabular-nums;
  }}
  .hud-oside {{ display:flex; flex-direction:column; gap:9px; }}
  .hud-ocap {{ font-family:{_HUD_MONO}; font-size:11px; letter-spacing:2px; color:{HUD["ink_dim"]}; font-weight:700; }}
  .hud-tier {{
    display:inline-block; padding:6px 15px; border-radius:999px; width:fit-content;
    font-family:{_HUD_MONO}; font-size:13px; font-weight:800; letter-spacing:2px;
    color:{HUD["void"]}; background: linear-gradient(90deg,{ts["accent"]},{ts["accent2"]});
    box-shadow: 0 6px 20px {ts["accent"]}55;
  }}
  .hud-subj {{ margin-top:12px; }}
  .hud-label {{ font-size:16px; font-weight:700; color:{HUD["ink"]}; }}
  .hud-repo {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["ink_faint"]}; margin-top:3px; word-break:break-all; }}
  .hud-gen {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["ink_faint"]}; margin-top:4px; }}
  .radar-wrap {{ display:flex; justify-content:center; margin:12px 0 4px; }}

  .stats {{ margin-top: 8px; display:flex; flex-direction:column; gap:9px; }}
  .stat-head {{ display:flex; align-items:baseline; gap:8px; }}
  .stat-key {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["gold"]}; font-weight:700; width:22px; }}
  .stat-name {{ flex:1; font-size:13px; color:{HUD["ink_dim"]}; font-weight:600; }}
  .stat-score {{ font-family:{_HUD_MONO}; font-size:16px; font-weight:800; font-variant-numeric:tabular-nums; }}
  .moat-tag {{ margin-left:6px; font-size:10px; color:{HUD["violet"]}; font-weight:800; letter-spacing:.5px; }}
  .na-tag {{ margin-left:6px; font-size:10px; color:{HUD["ink_faint"]}; font-style:italic; }}
  .bar {{ height:6px; border-radius:6px; background:{HUD["line"]}; overflow:hidden; margin-top:3px; }}
  .bar-fill {{ height:100%; border-radius:6px; }}
  .subs {{ margin:6px 0 2px 22px; display:flex; flex-direction:column; gap:4px; }}
  .sub {{ display:grid; grid-template-columns: 96px 1fr 20px; align-items:center; gap:8px; }}
  .sub-name {{ font-size:10.5px; color:{HUD["ink_faint"]}; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .sub-bar {{ height:4px; border-radius:4px; background:{HUD["line"]}; overflow:hidden; display:block; }}
  .sub-fill {{ display:block; height:100%; border-radius:4px; opacity:0.9; }}
  .sub-val {{ font-family:{_HUD_MONO}; font-size:10px; font-weight:800; text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .sub-hint {{ font-family:{_HUD_MONO}; font-size:8.5px; font-weight:700; color:{HUD["ink_faint"]}; margin-left:4px; letter-spacing:.2px; }}
  .sub-unmeasured .sub-name {{ opacity:0.7; font-style:italic; }}
  .sub-bar-empty {{ background:repeating-linear-gradient(90deg,{HUD["line"]} 0 4px, transparent 4px 8px); opacity:0.5; }}
  .sub-na {{ font-family:{_HUD_MONO}; font-size:8.5px; font-weight:800; text-align:right; letter-spacing:.3px; color:{HUD["ink_faint"]}; font-style:italic; white-space:nowrap; }}

  .right {{ display:flex; flex-direction:column; gap:22px; }}
  .panel {{
    position: relative; border-radius: 20px; padding: 22px 24px;
    background: linear-gradient(135deg, {HUD["glass_a"]}, {HUD["glass_b"]});
    border: 1px solid rgba(212,175,55,.18);
    box-shadow: 0 18px 50px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.04);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  }}
  .panel-title {{
    font-family:{_HUD_DISPLAY}; font-size: 15px; letter-spacing: 3px; font-weight: 700;
    background: linear-gradient(90deg,{HUD["gold"]},{HUD["gold_bright"]});
    -webkit-background-clip: text; background-clip: text; color: transparent;
    text-shadow: 0 0 20px rgba(212,175,55,.35);
    margin-bottom: 15px; display:flex; align-items:center; gap:12px;
  }}
  .panel-title::after {{ content:""; flex:1; height:1px; background: linear-gradient(90deg, {HUD["gold"]}55, transparent); }}

  .meta-strip {{ display:grid; grid-template-columns: repeat(3,1fr); gap: 16px; }}
  .meta-cell {{ background:{HUD["void"]}aa; border:1px solid {HUD["line"]}; border-radius:14px; padding:14px 16px; }}
  .meta-label {{ font-family:{_HUD_MONO}; font-size:11px; letter-spacing:2px; color:{HUD["ink_faint"]}; font-weight:700; }}
  .meta-big {{ font-family:{_HUD_DISPLAY}; font-size:34px; font-weight:800; margin:4px 0 2px; font-variant-numeric:tabular-nums; }}
  .meta-sub {{ font-size:11px; color:{HUD["ink_dim"]}; line-height:1.4; }}
  .meta-note {{ margin-top:10px; font-size:11px; color:{HUD["ink_faint"]}; font-style:italic; }}

  .growth-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }}
  .growth-title {{ font-family:{_HUD_DISPLAY}; font-size:15px; letter-spacing:3px; font-weight:700;
    background: linear-gradient(90deg,{HUD["gold"]},{HUD["gold_bright"]});
    -webkit-background-clip:text; background-clip:text; color:transparent; }}
  .growth-target {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["ink_faint"]}; }}
  .growth-target b {{ color:{ts["accent"]}; }}

  .coach {{
    border:1px solid {HUD["line"]}; border-radius:14px; padding:16px 18px; margin-bottom:12px;
    background:{HUD["void"]}88; border-left:3px solid {HUD["weak"]};
    box-shadow: inset 0 0 30px rgba(167,139,250,.05);
  }}
  .coach-head {{ display:flex; align-items:center; flex-wrap:wrap; gap:8px 10px; margin-bottom:10px; }}
  .coach-pill {{ font-family:{_HUD_MONO}; font-size:11px; font-weight:800; color:{HUD["void"]}; background:{HUD["cyan"]}; padding:2px 8px; border-radius:6px; }}
  .coach-title {{ font-size:15px; font-weight:800; color:{HUD["ink"]}; }}
  .coach-sub {{ font-family:{_HUD_MONO}; font-size:10px; font-weight:700; letter-spacing:.3px; color:{HUD["violet"]};
    background:{HUD["violet"]}1a; border:1px solid {HUD["violet"]}44; padding:2px 8px; border-radius:999px; }}
  .coach-row {{ display:flex; gap:12px; margin:7px 0; font-size:13px; line-height:1.6; }}
  .lbl {{ flex:0 0 42px; font-family:{_HUD_MONO}; font-size:10px; font-weight:800; letter-spacing:1px; color:{HUD["ink_faint"]}; padding-top:2px; }}
  .weak-lbl {{ color:{HUD["weak"]}; }}
  .why-lbl {{ color:{HUD["warn"]}; }}
  .how-lbl {{ color:{HUD["good"]}; }}
  .txt {{ flex:1; max-width:64ch; color:{HUD["ink_dim"]}; }}
  .txt-weak {{ color:{HUD["ink"]}; }}
  .coach-example-wrap {{ margin:10px 0 4px; }}
  .coach-example-cap {{ display:block; font-family:{_HUD_MONO}; font-size:9.5px; letter-spacing:1.5px; font-weight:800; color:{HUD["good"]}; margin-bottom:5px; }}
  .coach-example {{ padding:9px 12px; border-radius:8px; background:{HUD["void"]}; border:1px dashed {HUD["line"]};
    font-family:{_HUD_MONO}; font-size:12px; color:{HUD["cyan"]}; line-height:1.5; word-break:break-word; }}
  .coach-excerpt-wrap {{ margin:10px 0 4px; }}
  .coach-excerpt-cap {{ display:block; font-family:{_HUD_MONO}; font-size:9.5px; letter-spacing:1.5px; font-weight:800; color:{HUD["violet"]}; margin-bottom:5px; }}
  .coach-excerpt {{ padding:9px 12px 9px 14px; border-radius:8px; background:{HUD["violet"]}12; border-left:2px dashed {HUD["violet"]}88;
    font-size:12px; color:{HUD["ink_dim"]}; font-style:italic; line-height:1.55; word-break:break-word; }}
  .coach-retest {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["ink_faint"]}; margin-top:8px; font-style:italic; }}

  .strengths {{ display:flex; flex-direction:column; gap:8px; }}
  .strength {{ display:flex; gap:10px; align-items:baseline; }}
  .strength-pill {{ font-family:{_HUD_MONO}; font-size:11px; font-weight:800; color:{HUD["void"]}; background:{HUD["good"]}; padding:2px 8px; border-radius:6px; flex:0 0 auto; }}
  .strength-txt {{ font-size:13px; color:{HUD["ink_dim"]}; line-height:1.5; }}
  .empty {{ font-size:13px; color:{HUD["ink_dim"]}; font-style:italic; }}

  .desc-note {{ margin-top:12px; font-size:11px; color:{HUD["ink_faint"]}; font-style:italic; }}
  .chip-group {{ margin-bottom:12px; }}
  .chip-group:last-of-type {{ margin-bottom:0; }}
  .chip-cap {{ font-family:{_HUD_MONO}; font-size:10px; letter-spacing:2px; font-weight:800; color:{HUD["ink_faint"]}; margin-bottom:8px; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
  .chip {{ display:inline-flex; align-items:baseline; gap:6px; background:{HUD["void"]}aa; border:1px solid {HUD["line"]}; border-radius:8px; padding:5px 10px; }}
  .chip-k {{ font-family:{_HUD_MONO}; font-size:10px; font-weight:800; letter-spacing:.5px; color:{HUD["violet"]}; text-transform:uppercase; }}
  .chip-v {{ font-size:12px; color:{HUD["ink_dim"]}; }}

  .trend-legend {{ display:flex; flex-wrap:wrap; gap:14px; margin-bottom:10px; }}
  .leg {{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:700; color:{HUD["ink_dim"]}; }}
  .leg-dot {{ width:10px; height:10px; border-radius:3px; display:inline-block; }}
  .trend-svg {{ width:100%; }}
  .trend-svg svg {{ width:100%; height:auto; display:block; }}

  .pa-sub-title {{ font-family:{_HUD_MONO}; font-size:10px; letter-spacing:2px; font-weight:800; color:{HUD["good"]}; margin:6px 0 10px; }}
  .pa-sub-bad {{ color:{HUD["weak"]}; margin-top:16px; }}
  .pa-row {{ display:flex; gap:10px; align-items:baseline; margin-bottom:9px; }}
  .pa-pill {{ font-family:{_HUD_MONO}; font-size:10px; font-weight:800; color:{HUD["void"]}; padding:2px 8px; border-radius:6px; flex:0 0 auto; }}
  .pa-pill-good {{ background:{HUD["good"]}; }}
  .pa-pill-bad {{ background:{HUD["weak"]}; }}
  .pa-txt {{ font-size:12.5px; color:{HUD["ink_dim"]}; line-height:1.5; }}
  .pa-cost {{ display:inline-block; margin-left:8px; font-family:{_HUD_MONO}; font-size:9.5px; font-weight:800; letter-spacing:.5px; text-transform:uppercase; padding:1px 7px; border-radius:999px; border:1px solid; vertical-align:middle; }}

  .footer {{ grid-column: 1 / -1; text-align:center; margin-top: 8px; padding-bottom: 6px;
    font-family:{_HUD_MONO}; font-size: 11px; color:{HUD["ink_faint"]}; }}
  .footer b {{ color:{HUD["ink_dim"]}; }}

  .hud-backrow {{ position: relative; z-index: 3; width: 1200px; margin: 0 auto; padding: 20px 40px 0; }}
  .hud-back {{
    display:inline-flex; align-items:center; text-decoration:none;
    font-family:{_HUD_MONO}; font-size: 12px; font-weight: 700; letter-spacing:.4px;
    color:{HUD["cyan"]};
    border:1px solid {HUD["cyan"]}44; border-radius:999px; padding:7px 15px;
    background:{HUD["cyan"]}10;
    transition: background .15s ease, border-color .15s ease;
  }}
  .hud-back:hover {{ background:{HUD["cyan"]}22; border-color:{HUD["cyan"]}88; }}
  .back-arrow {{ font-weight:900; }}
</style>
</head>
<body>
  <div class="starfield"></div>
  <div class="stars-near"></div>
  {back_row}
  <div class="hud-stage" id="agentcraft-depth">
    <!-- LEFT: identity + radar + pillar stats -->
    <div class="glass-card">
      <div class="hud-brandrow">
        <div class="hud-brand">{_esc(BRAND)}</div>
        <div class="hud-private">PRIVATE &middot; LOCAL</div>
      </div>

      <div class="hud-hero">
        <div class="hud-overall">{oscore}</div>
        <div class="hud-oside">
          <div class="hud-ocap">OVERALL</div>
          <div class="hud-tier">{_esc(ts["label"])}</div>
        </div>
      </div>

      <div class="hud-subj">
        <div class="hud-label">{_esc(label)}</div>
        {repo_line}
        <div class="hud-gen">{_esc(generated)}</div>
      </div>

      <div class="radar-wrap">{radar}</div>

      <div class="stats">{stats}</div>
    </div>

    <!-- RIGHT: META + TREND + GROWTH PLAN + PROFILE/STYLE + PRACTICES -->
    <div class="right">
      <div class="panel">
        <div class="panel-title">SIGNAL COVERAGE &amp; META</div>
        {meta}
      </div>

      {trend}

      <div class="panel">
        <div class="growth-head">
          <div class="growth-title">GROWTH PLAN</div>
          <div class="growth-target">level up how YOU work with AI &middot; threshold <b>{_esc(target)}</b> (gold line)</div>
        </div>
        {coaching}
        {strengths}
      </div>

      {profile_style}

      {practices}
    </div>

    <div class="footer">
      <b>{_esc(BRAND)}</b> &middot; PRIVATE depth dashboard &middot; stays on your machine, git-ignored, never shared &middot;
      100% local, no telemetry, no send &middot; open-source (MIT)
    </div>
  </div>
</body>
</html>'''


# =============================================================================
# LENS B (your CODE) -- CODE-AUDIT COMMAND-CENTER (page-2-style dark HUD).
# Renders from a code-audit report (report_kind == "code-audit"): the overall
# CODE grade + tier, per-axis bars for all 8 axes (C1..C8), the SCAN META
# (files/LOC/languages), top FINDINGS, top RISKS, REFACTOR PRIORITIES, and
# STRENGTHS. Same cosmic dark HUD aesthetic as build_depth_html (starfield +
# Cinzel headings + JetBrains Mono data + gold section titles + glass panels),
# reusing the same CSS variables/classes plus a few audit-specific ones.
#
# This is a PRIVATE, local page (like page 2): it may show evidence PATHS. It is
# NOT the shareable card and is NEVER redaction-guarded. It NEVER echoes a secret
# VALUE -- the code-audit report carries COUNTS (e.g. secret_pattern_hits: 2),
# not the secret contents, so there is nothing sensitive to leak here.
# 100% local + zero-egress (system-font fallbacks; inline SVG-free; no network).
# =============================================================================
def build_repo_html(report: dict, nav_href: str | None = None) -> str:
    """PAGE (Lens B) -- the CODE-AUDIT command-center dashboard (dark HUD).

    Renders a code-audit report (report_kind == "code-audit", axes C1..C8) into
    the same page-2 HUD look as build_depth_html: overall code grade + tier, an
    8-axis score-bar column, scan META, top findings, top risks, refactor
    priorities, and strengths.

    `nav_href` (optional): a bare .html basename of the landing index (or the
    Lens A card). When given, an unobtrusive top-left back link is rendered so a
    reader can walk BACK out of the audit. Default None keeps single-arg behavior.
    """
    overall = report.get("overall", {}) or {}
    oscore = int(round(overall.get("score", 0)))
    tier = overall.get("tier", tier_for(oscore,
                        (report.get("config", {}) or {}).get("tier_bands")))
    ts = TIER_STYLE.get(tier, TIER_STYLE["silver"])
    subject = report.get("subject", {}) or {}
    repo_name = subject.get("repo_name", subject.get("label", "repository"))
    repo_path = subject.get("repo_path", "")
    generated = report.get("generated_at", "")
    summary = report.get("summary", "")

    axis_bars = _code_axis_bars(report)
    scan_meta = _code_scan_meta(report)
    findings = _code_findings(report, "findings", "No findings recorded.")
    risks = _code_findings(report, "risks", "No standalone risks recorded.")
    refactor = _code_refactor_priorities(report)
    strengths = _code_strengths(report)

    repo_line = (f'<div class="hud-repo">{_esc(repo_path)}</div>'
                 if repo_path else "")
    summary_block = (f'<div class="repo-summary">{_esc(summary)}</div>'
                     if summary else "")
    # Only render the RISKS panel when the report actually carries a `risks` list
    # (many code-audit reports fold risk into findings). Honest-empty otherwise.
    risks_panel = ""
    if report.get("risks"):
        risks_panel = f'''
      <div class="panel">
        <div class="panel-title">TOP RISKS</div>
        {risks}
      </div>'''

    back_row = ""
    if nav_href:
        back_row = (f'<div class="hud-backrow">'
                    f'<a class="hud-back" href="{_esc(nav_href)}">'
                    f'<span class="back-arrow">&larr;</span>&nbsp;&nbsp;'
                    f'Back to start</a></div>')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(BRAND)} code audit (Lens B) — {_esc(repo_name)}</title>
<style>
  /* ==== Code-audit HUD — same cosmic dark aesthetic as the depth dashboard.
     Fonts: HUD family first, SYSTEM FALLBACKS after. NO remote font fetch (zero-egress). */
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: {HUD["void"]};
    color: {HUD["ink"]};
    font-family: {_HUD_BODY};
    -webkit-font-smoothing: antialiased;
    position: relative;
    overflow-x: hidden;
  }}
  body::before {{
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
      radial-gradient(900px 640px at 12% -8%, rgba(167,139,250,.16) 0%, transparent 58%),
      radial-gradient(820px 620px at 92% 4%, rgba(65,224,208,.12) 0%, transparent 60%),
      radial-gradient(1100px 900px at 50% 120%, rgba(212,175,55,.10) 0%, transparent 62%);
  }}
  .starfield, .stars-near {{ position: fixed; inset: 0; z-index: 0; pointer-events: none; }}
  .starfield::before, .starfield::after, .stars-near::before {{
    content: ""; position: absolute; inset: -50%; width: 200%; height: 200%;
  }}
  .starfield::before {{
    background-image:
      radial-gradient(1.4px 1.4px at 20% 30%, rgba(255,255,255,.85) 50%, transparent),
      radial-gradient(1.2px 1.2px at 70% 60%, rgba(255,240,200,.7) 50%, transparent),
      radial-gradient(1px 1px at 40% 80%, rgba(200,220,255,.6) 50%, transparent),
      radial-gradient(1.3px 1.3px at 85% 25%, rgba(255,255,255,.7) 50%, transparent),
      radial-gradient(1px 1px at 15% 65%, rgba(255,255,255,.5) 50%, transparent);
    background-size: 620px 620px, 520px 520px, 440px 440px, 700px 700px, 380px 380px;
    animation: drift 180s linear infinite;
  }}
  .starfield::after {{
    background-image:
      radial-gradient(1px 1px at 55% 15%, rgba(255,255,255,.55) 50%, transparent),
      radial-gradient(1.6px 1.6px at 30% 50%, rgba(255,225,180,.8) 50%, transparent),
      radial-gradient(1px 1px at 78% 85%, rgba(210,225,255,.55) 50%, transparent);
    background-size: 800px 800px, 560px 560px, 660px 660px;
    animation: drift 260s linear infinite reverse, twinkle 6s ease-in-out infinite;
    opacity: .8;
  }}
  .stars-near::before {{
    background-image:
      radial-gradient(2px 2px at 60% 40%, rgba(255,240,210,.9) 50%, transparent),
      radial-gradient(2.2px 2.2px at 25% 70%, rgba(255,255,255,.85) 50%, transparent);
    background-size: 900px 900px, 1000px 1000px;
    animation: drift 120s linear infinite, twinkle 4.5s ease-in-out infinite;
  }}
  @keyframes drift {{ from {{ transform: translate(0,0); }} to {{ transform: translate(-140px,-90px); }} }}
  @keyframes twinkle {{ 0%,100% {{ opacity:.6; }} 50% {{ opacity:1; }} }}

  .hud-stage {{
    position: relative; z-index: 2;
    width: 1200px; padding: 40px 40px 30px; margin: 0 auto;
    display: grid; grid-template-columns: 430px 1fr; gap: 30px; align-items: start;
  }}

  .glass-card {{
    position: relative; border-radius: 22px; padding: 26px 26px 22px;
    background: linear-gradient(135deg, {HUD["glass_a"]}, {HUD["glass_b"]});
    border: 1px solid rgba(212,175,55,.24);
    box-shadow: 0 24px 70px rgba(0,0,0,.6), 0 0 40px rgba(212,175,55,.10),
                inset 0 1px 0 rgba(255,255,255,.05);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    overflow: hidden;
  }}
  .hud-brandrow {{ display:flex; align-items:baseline; justify-content:space-between; }}
  .hud-brand {{
    font-family: {_HUD_DISPLAY}; font-size: 30px; font-weight: 800; letter-spacing: 4px;
    background: linear-gradient(90deg, {HUD["gold"]}, {HUD["gold_bright"]});
    -webkit-background-clip: text; background-clip: text; color: transparent;
    text-shadow: 0 0 24px rgba(212,175,55,.4);
  }}
  /* LENS B badge — the code-audit twin of the "PRIVATE·LOCAL" chip */
  .hud-lensb {{
    font-family:{_HUD_MONO}; font-size: 9px; letter-spacing:2px; font-weight:700;
    color: {HUD["violet"]}; border:1px solid {HUD["violet"]}55; border-radius:999px;
    padding:3px 9px; background:{HUD["violet"]}12;
  }}
  .hud-hero {{ display:flex; align-items:center; gap:20px; margin:20px 0 6px; }}
  .hud-overall {{
    font-family:{_HUD_DISPLAY}; font-size: 94px; font-weight: 800; line-height:.9;
    color:{ts["accent"]}; text-shadow: 0 0 34px {ts["accent"]}55;
    font-variant-numeric: tabular-nums;
  }}
  .hud-oside {{ display:flex; flex-direction:column; gap:9px; }}
  .hud-ocap {{ font-family:{_HUD_MONO}; font-size:11px; letter-spacing:2px; color:{HUD["ink_dim"]}; font-weight:700; }}
  .hud-tier {{
    display:inline-block; padding:6px 15px; border-radius:999px; width:fit-content;
    font-family:{_HUD_MONO}; font-size:13px; font-weight:800; letter-spacing:2px;
    color:{HUD["void"]}; background: linear-gradient(90deg,{ts["accent"]},{ts["accent2"]});
    box-shadow: 0 6px 20px {ts["accent"]}55;
  }}
  .hud-subj {{ margin-top:12px; }}
  .hud-label {{ font-size:16px; font-weight:700; color:{HUD["ink"]}; }}
  .hud-repo {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["ink_faint"]}; margin-top:3px; word-break:break-all; }}
  .hud-gen {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["ink_faint"]}; margin-top:4px; }}

  .axes-cap {{ font-family:{_HUD_MONO}; font-size:11px; letter-spacing:2px; font-weight:700;
    color:{HUD["ink_faint"]}; margin:18px 0 8px; }}
  .stats {{ margin-top: 4px; display:flex; flex-direction:column; gap:11px; }}
  .stat-head {{ display:flex; align-items:baseline; gap:8px; }}
  .stat-key {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["gold"]}; font-weight:700; width:26px; }}
  .stat-name {{ flex:1; font-size:13px; color:{HUD["ink_dim"]}; font-weight:600; }}
  .stat-score {{ font-family:{_HUD_MONO}; font-size:16px; font-weight:800; font-variant-numeric:tabular-nums; }}
  .na-tag {{ margin-left:6px; font-size:10px; color:{HUD["ink_faint"]}; font-style:italic; }}
  .bar {{ height:6px; border-radius:6px; background:{HUD["line"]}; overflow:hidden; margin-top:4px; }}
  .bar-fill {{ height:100%; border-radius:6px; }}

  .right {{ display:flex; flex-direction:column; gap:22px; }}
  .panel {{
    position: relative; border-radius: 20px; padding: 22px 24px;
    background: linear-gradient(135deg, {HUD["glass_a"]}, {HUD["glass_b"]});
    border: 1px solid rgba(212,175,55,.18);
    box-shadow: 0 18px 50px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.04);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  }}
  .panel-title {{
    font-family:{_HUD_DISPLAY}; font-size: 15px; letter-spacing: 3px; font-weight: 700;
    background: linear-gradient(90deg,{HUD["gold"]},{HUD["gold_bright"]});
    -webkit-background-clip: text; background-clip: text; color: transparent;
    text-shadow: 0 0 20px rgba(212,175,55,.35);
    margin-bottom: 15px; display:flex; align-items:center; gap:12px;
  }}
  .panel-title::after {{ content:""; flex:1; height:1px; background: linear-gradient(90deg, {HUD["gold"]}55, transparent); }}

  .repo-summary {{ font-size:13.5px; line-height:1.65; color:{HUD["ink_dim"]}; }}

  .meta-strip {{ display:grid; grid-template-columns: repeat(3,1fr); gap: 16px; }}
  .meta-cell {{ background:{HUD["void"]}aa; border:1px solid {HUD["line"]}; border-radius:14px; padding:14px 16px; }}
  .meta-label {{ font-family:{_HUD_MONO}; font-size:11px; letter-spacing:2px; color:{HUD["ink_faint"]}; font-weight:700; }}
  .meta-big {{ font-family:{_HUD_DISPLAY}; font-size:32px; font-weight:800; margin:4px 0 2px; font-variant-numeric:tabular-nums; }}
  .meta-sub {{ font-size:11px; color:{HUD["ink_dim"]}; line-height:1.4; }}
  .meta-note {{ margin-top:10px; font-size:11px; color:{HUD["ink_faint"]}; font-style:italic; }}

  /* findings / risks — reuse the coach card shell */
  .coach {{
    border:1px solid {HUD["line"]}; border-radius:14px; padding:16px 18px; margin-bottom:12px;
    background:{HUD["void"]}88; border-left:3px solid {HUD["weak"]};
    box-shadow: inset 0 0 30px rgba(167,139,250,.05);
  }}
  .coach-head {{ display:flex; align-items:center; flex-wrap:wrap; gap:8px 10px; margin-bottom:10px; }}
  .coach-pill {{ font-family:{_HUD_MONO}; font-size:11px; font-weight:800; color:{HUD["void"]}; background:{HUD["cyan"]}; padding:2px 8px; border-radius:6px; }}
  .coach-title {{ font-size:15px; font-weight:800; color:{HUD["ink"]}; }}
  .rf-sev {{ font-family:{_HUD_MONO}; font-size:10px; font-weight:800; letter-spacing:1px;
    padding:2px 8px; border-radius:999px; border:1px solid; margin-left:auto; }}
  .coach-row {{ display:flex; gap:12px; margin:7px 0; font-size:13px; line-height:1.6; }}
  .lbl {{ flex:0 0 42px; font-family:{_HUD_MONO}; font-size:10px; font-weight:800; letter-spacing:1px; color:{HUD["ink_faint"]}; padding-top:2px; }}
  .weak-lbl {{ color:{HUD["weak"]}; }}
  .why-lbl {{ color:{HUD["warn"]}; }}
  .how-lbl {{ color:{HUD["good"]}; }}
  .txt {{ flex:1; max-width:64ch; color:{HUD["ink_dim"]}; }}
  .txt-weak {{ color:{HUD["ink"]}; }}
  .rf-ev-wrap {{ margin:10px 0 2px; }}
  .rf-ev-cap {{ display:block; font-family:{_HUD_MONO}; font-size:9.5px; letter-spacing:1.5px; font-weight:800; color:{HUD["violet"]}; margin-bottom:6px; }}
  .rf-ev {{ display:flex; flex-wrap:wrap; gap:4px 10px; align-items:baseline; margin-bottom:5px; }}
  .rf-ev-path {{ font-family:{_HUD_MONO}; font-size:11px; color:{HUD["cyan"]}; background:{HUD["void"]}; border:1px solid {HUD["line"]}; border-radius:6px; padding:2px 7px; word-break:break-all; }}
  .rf-ev-note {{ font-size:12px; color:{HUD["ink_dim"]}; font-style:italic; }}

  /* refactor priorities — ordered punch list */
  .rp-list {{ display:flex; flex-direction:column; gap:12px; }}
  .rp-row {{ display:flex; gap:14px; align-items:flex-start; }}
  .rp-num {{ flex:0 0 auto; width:26px; height:26px; border-radius:8px; display:flex;
    align-items:center; justify-content:center; font-family:{_HUD_MONO}; font-size:13px;
    font-weight:800; color:{HUD["void"]}; background:linear-gradient(135deg,{HUD["gold"]},{HUD["gold_bright"]});
    box-shadow:0 4px 14px rgba(212,175,55,.35); }}
  .rp-body {{ flex:1; }}
  .rp-head {{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }}
  .rp-axis {{ font-family:{_HUD_MONO}; font-size:10px; font-weight:800; color:{HUD["void"]}; background:{HUD["cyan"]}; padding:1px 7px; border-radius:6px; }}
  .rp-title {{ font-size:14px; font-weight:700; color:{HUD["ink"]}; }}
  .rp-fix {{ font-size:12.5px; color:{HUD["ink_dim"]}; line-height:1.5; margin-top:4px; }}

  .strengths {{ display:flex; flex-direction:column; gap:8px; margin-top:4px; }}
  .strength {{ display:flex; gap:10px; align-items:baseline; }}
  .strength-pill {{ font-family:{_HUD_MONO}; font-size:11px; font-weight:800; color:{HUD["void"]}; background:{HUD["good"]}; padding:2px 8px; border-radius:6px; flex:0 0 auto; }}
  .strength-txt {{ font-size:13px; color:{HUD["ink_dim"]}; line-height:1.5; }}
  .empty {{ font-size:13px; color:{HUD["ink_dim"]}; font-style:italic; }}

  .footer {{ grid-column: 1 / -1; text-align:center; margin-top: 8px; padding-bottom: 6px;
    font-family:{_HUD_MONO}; font-size: 11px; color:{HUD["ink_faint"]}; }}
  .footer b {{ color:{HUD["ink_dim"]}; }}

  .hud-backrow {{ position: relative; z-index: 3; width: 1200px; margin: 0 auto; padding: 20px 40px 0; }}
  .hud-back {{
    display:inline-flex; align-items:center; text-decoration:none;
    font-family:{_HUD_MONO}; font-size: 12px; font-weight: 700; letter-spacing:.4px;
    color:{HUD["cyan"]};
    border:1px solid {HUD["cyan"]}44; border-radius:999px; padding:7px 15px;
    background:{HUD["cyan"]}10;
    transition: background .15s ease, border-color .15s ease;
  }}
  .hud-back:hover {{ background:{HUD["cyan"]}22; border-color:{HUD["cyan"]}88; }}
  .back-arrow {{ font-weight:900; }}
</style>
</head>
<body>
  <div class="starfield"></div>
  <div class="stars-near"></div>
  {back_row}
  <div class="hud-stage" id="agentcraft-repo">
    <!-- LEFT: identity + overall code grade + 8-axis bars -->
    <div class="glass-card">
      <div class="hud-brandrow">
        <div class="hud-brand">{_esc(BRAND)}</div>
        <div class="hud-lensb">LENS B &middot; YOUR CODE</div>
      </div>

      <div class="hud-hero">
        <div class="hud-overall">{oscore}</div>
        <div class="hud-oside">
          <div class="hud-ocap">CODE GRADE</div>
          <div class="hud-tier">{_esc(ts["label"])}</div>
        </div>
      </div>

      <div class="hud-subj">
        <div class="hud-label">{_esc(repo_name)}</div>
        {repo_line}
        <div class="hud-gen">{_esc(generated)}</div>
      </div>

      <div class="axes-cap">8 AXES &middot; C1&ndash;C8</div>
      <div class="stats">{axis_bars}</div>
    </div>

    <!-- RIGHT: scan meta + findings + risks + refactor priorities + strengths -->
    <div class="right">
      <div class="panel">
        <div class="panel-title">SCAN COVERAGE</div>
        {scan_meta}
        {summary_block}
      </div>

      <div class="panel">
        <div class="panel-title">TOP FINDINGS</div>
        {findings}
      </div>

      {risks_panel}

      <div class="panel">
        <div class="panel-title">REFACTOR PRIORITIES</div>
        {refactor}
      </div>

      <div class="panel">
        {strengths}
      </div>
    </div>

    <div class="footer">
      <b>{_esc(BRAND)}</b> &middot; Lens B code audit &middot; stays on your machine, git-ignored, never shared &middot;
      100% local, no telemetry, no send &middot; counts only (never a secret value) &middot; open-source (MIT)
    </div>
  </div>
</body>
</html>'''


def build_html(report: dict) -> str:
    overall = report["overall"]
    oscore = int(round(overall.get("score", 0)))
    tier = overall.get("tier", tier_for(oscore,
                        (report.get("config", {}) or {}).get("tier_bands")))
    ts = TIER_STYLE.get(tier, TIER_STYLE["silver"])
    subject = report.get("subject", {}) or {}
    label = subject.get("label", "local-user")
    repo_path = subject.get("repo_path", "")
    generated = report.get("generated_at", "")
    target = (report.get("config", {}) or {}).get("target", 75)

    radar = build_radar_svg(report)
    stats = _pillar_stat_rows(report)
    meta = _meta_strip(report)
    coaching = _coaching_cards(report)
    strengths = _strengths_list(report)
    # v2 descriptive/synthesis surfaces — each is "" for a v1 report (v1-safe).
    profile_style = _profile_style_strip(report)
    trend = _trend_sparkline(report)
    practices = _practices_panel(report)

    repo_line = (f'<div class="subj-repo">{_esc(repo_path)}</div>'
                 if repo_path else "")

    # Big card score color follows tier accent.
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(BRAND)} card — {_esc(label)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: radial-gradient(1200px 800px at 20% -10%, {PALETTE["bg1"]} 0%, {PALETTE["bg0"]} 60%);
    color: {PALETTE["ink"]};
    font-family: {_FONT_STACK};
    -webkit-font-smoothing: antialiased;
  }}
  .stage {{
    width: 1200px;
    padding: 32px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 420px 1fr;
    gap: 28px;
    align-items: start;
  }}

  /* ---------- FUT-STYLE CARD (left) ---------- */
  .card {{
    position: relative;
    border-radius: 24px;
    padding: 26px 24px 22px;
    background:
      linear-gradient(160deg, {ts["accent"]}22 0%, transparent 42%),
      linear-gradient(180deg, {PALETTE["card_top"]} 0%, {PALETTE["card_bot"]} 100%);
    border: 1px solid {PALETTE["line"]};
    box-shadow: 0 24px 60px rgba(0,0,0,0.55),
                inset 0 1px 0 rgba(255,255,255,0.04);
    overflow: hidden;
  }}
  .card::before {{
    content: "";
    position: absolute; inset: 0;
    border-radius: 24px;
    padding: 1px;
    background: linear-gradient(140deg, {ts["accent"]}, transparent 40%, {ts["accent2"]}88);
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude;
    pointer-events: none;
  }}
  .brand-row {{ display:flex; align-items:baseline; justify-content:space-between; }}
  .brand {{
    font-size: 26px; font-weight: 900; letter-spacing: 3px;
    background: linear-gradient(90deg, {ts["accent"]}, {ts["accent2"]});
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }}
  .brand-tag {{ font-size: 11px; color: {PALETTE["ink_faint"]}; letter-spacing:.5px; }}

  .hero {{ display:flex; align-items:center; gap: 20px; margin: 18px 0 8px; }}
  .overall {{
    font-size: 92px; font-weight: 900; line-height: 0.9;
    color: {ts["accent"]};
    text-shadow: 0 0 30px {ts["accent"]}44;
    font-variant-numeric: tabular-nums;
  }}
  .overall-side {{ display:flex; flex-direction:column; gap:8px; }}
  .overall-cap {{ font-size:12px; letter-spacing:2px; color:{PALETTE["ink_dim"]}; font-weight:700; }}
  .tier-badge {{
    display:inline-block; padding: 6px 14px; border-radius: 999px;
    font-size: 14px; font-weight: 900; letter-spacing: 2px;
    color: {PALETTE["bg0"]};
    background: linear-gradient(90deg, {ts["accent"]}, {ts["accent2"]});
    box-shadow: 0 6px 18px {ts["accent"]}44;
    width: fit-content;
  }}
  .subj {{ margin-top: 10px; }}
  .subj-label {{ font-size: 16px; font-weight: 700; color: {PALETTE["ink"]}; }}
  .subj-repo {{
    font-family: {_MONO_STACK}; font-size: 11px; color: {PALETTE["ink_faint"]};
    margin-top: 3px; word-break: break-all;
  }}
  .subj-gen {{ font-size: 11px; color: {PALETTE["ink_faint"]}; margin-top: 4px; }}

  .radar-wrap {{ display:flex; justify-content:center; margin: 8px 0 4px; }}

  .stats {{ margin-top: 6px; display:flex; flex-direction:column; gap: 9px; }}
  .stat-head {{ display:flex; align-items:baseline; gap:8px; }}
  .stat-key {{ font-family:{_MONO_STACK}; font-size:11px; color:{PALETTE["ink_faint"]}; font-weight:700; width:22px; }}
  .stat-name {{ flex:1; font-size:13px; color:{PALETTE["ink_dim"]}; font-weight:600; }}
  .stat-score {{ font-size:16px; font-weight:900; font-variant-numeric:tabular-nums; }}
  .moat-tag {{ margin-left:6px; font-size:10px; color:{PALETTE["moat"]}; font-weight:800; letter-spacing:.5px; }}
  .na-tag {{ margin-left:6px; font-size:10px; color:{PALETTE["ink_faint"]}; font-style:italic; }}
  .bar {{ height:6px; border-radius:6px; background:{PALETTE["line"]}; overflow:hidden; margin-top:3px; }}
  .bar-fill {{ height:100%; border-radius:6px; }}

  /* per-pillar SUB-SIGNAL micro-bars (D3 depth surface) */
  .subs {{ margin:6px 0 2px 22px; display:flex; flex-direction:column; gap:4px; }}
  .sub {{ display:grid; grid-template-columns: 96px 1fr 20px; align-items:center; gap:8px; }}
  .sub-name {{ font-size:10.5px; color:{PALETTE["ink_faint"]}; font-weight:600;
              white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .sub-bar {{ height:4px; border-radius:4px; background:{PALETTE["line"]};
             overflow:hidden; display:block; }}
  .sub-fill {{ display:block; height:100%; border-radius:4px; opacity:0.85; }}
  .sub-val {{ font-size:10px; font-weight:800; text-align:right;
             font-variant-numeric:tabular-nums; white-space:nowrap; }}
  /* v2: honest count hint (applied/eligible + verified) beside a sub-signal */
  .sub-hint {{ font-size:8.5px; font-weight:700; color:{PALETTE["ink_faint"]};
              margin-left:4px; letter-spacing:.2px; }}
  /* v2: unmeasured sub-signal (score:null) — honest badge, no fabricated bar */
  .sub-unmeasured .sub-name {{ opacity:0.7; font-style:italic; }}
  .sub-bar-empty {{ background:repeating-linear-gradient(90deg,
                    {PALETTE["line"]} 0 4px, transparent 4px 8px); opacity:0.5; }}
  .sub-na {{ font-size:8.5px; font-weight:800; text-align:right; letter-spacing:.3px;
            color:{PALETTE["ink_faint"]}; font-style:italic; white-space:nowrap; }}

  /* ---------- RIGHT COLUMN ---------- */
  .right {{ display:flex; flex-direction:column; gap: 22px; }}
  .panel {{
    background: linear-gradient(180deg, {PALETTE["card_top"]}cc, {PALETTE["bg1"]}cc);
    border: 1px solid {PALETTE["line"]};
    border-radius: 18px;
    padding: 20px 22px;
  }}
  .panel-title {{
    font-size: 12px; letter-spacing: 3px; font-weight: 800;
    color: {PALETTE["ink_dim"]}; margin-bottom: 14px;
    display:flex; align-items:center; gap:10px;
  }}
  .panel-title::after {{ content:""; flex:1; height:1px; background:{PALETTE["line"]}; }}

  .meta-strip {{ display:grid; grid-template-columns: repeat(3,1fr); gap: 16px; }}
  .meta-cell {{
    background: {PALETTE["bg0"]}88; border:1px solid {PALETTE["line"]};
    border-radius: 14px; padding: 14px 16px;
  }}
  .meta-label {{ font-size:11px; letter-spacing:2px; color:{PALETTE["ink_faint"]}; font-weight:700; }}
  .meta-big {{ font-size:34px; font-weight:900; margin:4px 0 2px; font-variant-numeric:tabular-nums; }}
  .meta-sub {{ font-size:11px; color:{PALETTE["ink_dim"]}; line-height:1.4; }}
  .meta-note {{ margin-top:10px; font-size:11px; color:{PALETTE["ink_faint"]}; font-style:italic; }}

  .growth-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:14px; margin-bottom:14px; }}
  .growth-title-wrap {{ display:flex; flex-direction:column; gap:3px; }}
  .growth-title {{ font-size: 12px; letter-spacing:3px; font-weight:800; color:{PALETTE["ink_dim"]}; }}
  /* self-development framing — this is a personal growth plan, not a verdict */
  .growth-subtitle {{ font-size:10.5px; letter-spacing:.2px; color:{PALETTE["ink_faint"]};
                     font-style:italic; max-width:46ch; line-height:1.4; }}
  .growth-target {{ font-size: 11px; color:{PALETTE["ink_faint"]}; white-space:nowrap; padding-top:2px; }}
  .growth-target b {{ color:{ts["accent"]}; }}

  .coach {{
    border:1px solid {PALETTE["line"]}; border-radius:14px;
    padding: 16px 18px; margin-bottom: 12px;
    background: {PALETTE["bg0"]}66;
    border-left: 3px solid {PALETTE["weak"]};
  }}
  .coach-head {{ display:flex; align-items:center; flex-wrap:wrap; gap:8px 10px; margin-bottom:10px; }}
  .coach-pill {{
    font-family:{_MONO_STACK}; font-size:11px; font-weight:800;
    color:{PALETTE["bg0"]}; background:{PALETTE["accent"]};
    padding:2px 8px; border-radius:6px;
  }}
  .coach-title {{ font-size:15px; font-weight:800; color:{PALETTE["ink"]}; }}
  /* the weakest sub-signal that dragged the pillar — names WHAT to fix */
  .coach-sub {{ font-family:{_MONO_STACK}; font-size:10px; font-weight:700;
               letter-spacing:.3px; color:{PALETTE["accent2"]};
               background:{PALETTE["accent2"]}1a; border:1px solid {PALETTE["accent2"]}44;
               padding:2px 8px; border-radius:999px; }}
  /* "BUILD THIS HABIT" micro-cap — frames each card as personal self-development,
     not a verdict. Growth-green tone, pushed to the right of the head row. */
  .coach-habit-cap {{ margin-left:auto; font-size:9px; font-weight:800;
               letter-spacing:1.3px; color:{PALETTE["good"]};
               background:{PALETTE["good"]}14; border:1px solid {PALETTE["good"]}3a;
               padding:2px 8px; border-radius:999px; white-space:nowrap; }}
  /* WEAK / WHY / HOW rows — roomier line-height + max width for longer, richer text */
  .coach-row {{ display:flex; gap:12px; margin: 7px 0; font-size:13px; line-height:1.6; }}
  .lbl {{ flex:0 0 42px; font-size:10px; font-weight:800; letter-spacing:1px;
          color:{PALETTE["ink_faint"]}; padding-top:2px; }}
  .weak-lbl {{ color:{PALETTE["weak"]}; }}
  .why-lbl {{ color:{PALETTE["warn"]}; }}
  .how-lbl {{ color:{PALETTE["good"]}; }}
  .txt {{ flex:1; max-width:64ch; color:{PALETTE["ink_dim"]}; }}
  /* WEAK carries the diagnosis — a touch brighter so it reads as the headline gap */
  .txt-weak {{ color:{PALETTE["ink"]}; }}
  /* EXAMPLE — a copy/adapt line, captioned */
  .coach-example-wrap {{ margin: 10px 0 4px; }}
  .coach-example-cap {{ display:block; font-size:9.5px; letter-spacing:1.5px;
                       font-weight:800; color:{PALETTE["good"]}; margin-bottom:5px; }}
  .coach-example {{
    padding: 9px 12px; border-radius:8px;
    background:{PALETTE["bg0"]}; border:1px dashed {PALETTE["line"]};
    font-family:{_MONO_STACK}; font-size:12px; color:{PALETTE["accent"]};
    line-height:1.5; word-break: break-word;
  }}
  /* FROM YOUR WORK — the curated, redacted own-work excerpt (the coach saw the work) */
  .coach-excerpt-wrap {{ margin: 10px 0 4px; }}
  .coach-excerpt-cap {{ display:block; font-size:9.5px; letter-spacing:1.5px;
                       font-weight:800; color:{PALETTE["accent2"]}; margin-bottom:5px; }}
  .coach-excerpt {{
    padding: 9px 12px 9px 14px; border-radius:8px;
    background:{PALETTE["accent2"]}0f; border-left:2px dashed {PALETTE["accent2"]}88;
    font-size:12px; color:{PALETTE["ink_dim"]}; font-style:italic;
    line-height:1.55; word-break: break-word;
  }}
  .coach-retest {{ font-size:11px; color:{PALETTE["ink_faint"]}; margin-top:8px; font-style:italic; }}

  .strengths {{ display:flex; flex-direction:column; gap:8px; }}
  .strength {{ display:flex; gap:10px; align-items:baseline; }}
  .strength-pill {{
    font-family:{_MONO_STACK}; font-size:11px; font-weight:800;
    color:{PALETTE["bg0"]}; background:{PALETTE["good"]};
    padding:2px 8px; border-radius:6px; flex:0 0 auto;
  }}
  .strength-txt {{ font-size:13px; color:{PALETTE["ink_dim"]}; line-height:1.5; }}

  .empty {{ font-size:13px; color:{PALETTE["ink_dim"]}; font-style:italic; }}

  /* ---------- v2: PROFILE & STYLE chips ---------- */
  .desc-note {{ margin-top:12px; font-size:11px; color:{PALETTE["ink_faint"]};
               font-style:italic; }}
  .chip-group {{ margin-bottom:12px; }}
  .chip-group:last-of-type {{ margin-bottom:0; }}
  .chip-cap {{ font-size:10px; letter-spacing:2px; font-weight:800;
              color:{PALETTE["ink_faint"]}; margin-bottom:8px; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
  .chip {{ display:inline-flex; align-items:baseline; gap:6px;
          background:{PALETTE["bg0"]}88; border:1px solid {PALETTE["line"]};
          border-radius:8px; padding:5px 10px; }}
  .chip-k {{ font-size:10px; font-weight:800; letter-spacing:.5px;
            color:{PALETTE["accent2"]}; text-transform:uppercase; }}
  .chip-v {{ font-size:12px; color:{PALETTE["ink_dim"]}; }}

  /* ---------- v2: TREND sparkline ---------- */
  .trend-legend {{ display:flex; flex-wrap:wrap; gap:14px; margin-bottom:10px; }}
  .leg {{ display:inline-flex; align-items:center; gap:6px; font-size:11px;
         font-weight:700; color:{PALETTE["ink_dim"]}; }}
  .leg-dot {{ width:10px; height:10px; border-radius:3px; display:inline-block; }}
  .trend-svg {{ width:100%; }}
  .trend-svg svg {{ width:100%; height:auto; display:block; }}

  /* ---------- v2: PRACTICES & ANTI-PATTERNS ---------- */
  .pa-sub-title {{ font-size:10px; letter-spacing:2px; font-weight:800;
                  color:{PALETTE["good"]}; margin:6px 0 10px; }}
  .pa-sub-bad {{ color:{PALETTE["weak"]}; margin-top:16px; }}
  .pa-row {{ display:flex; gap:10px; align-items:baseline; margin-bottom:9px; }}
  .pa-pill {{ font-family:{_MONO_STACK}; font-size:10px; font-weight:800;
             color:{PALETTE["bg0"]}; padding:2px 8px; border-radius:6px;
             flex:0 0 auto; }}
  .pa-pill-good {{ background:{PALETTE["good"]}; }}
  .pa-pill-bad {{ background:{PALETTE["weak"]}; }}
  .pa-txt {{ font-size:12.5px; color:{PALETTE["ink_dim"]}; line-height:1.5; }}
  .pa-cost {{ display:inline-block; margin-left:8px; font-size:9.5px; font-weight:800;
             letter-spacing:.5px; text-transform:uppercase; padding:1px 7px;
             border-radius:999px; border:1px solid; vertical-align:middle; }}

  .footer {{
    grid-column: 1 / -1; text-align:center; margin-top: 4px;
    font-size: 11px; color:{PALETTE["ink_faint"]};
  }}
  .footer b {{ color:{PALETTE["ink_dim"]}; }}
</style>
</head>
<body>
  <div class="stage" id="agentcraft-stage">
    <!-- LEFT: FUT-STYLE CARD -->
    <div class="card">
      <div class="brand-row">
        <div class="brand">{_esc(BRAND)}</div>
        <div class="brand-tag">{_esc(TAGLINE)}</div>
      </div>

      <div class="hero">
        <div class="overall">{oscore}</div>
        <div class="overall-side">
          <div class="overall-cap">OVERALL</div>
          <div class="tier-badge">{_esc(ts["label"])}</div>
        </div>
      </div>

      <div class="subj">
        <div class="subj-label">{_esc(label)}</div>
        {repo_line}
        <div class="subj-gen">{_esc(generated)}</div>
      </div>

      <div class="radar-wrap">{radar}</div>

      <div class="stats">{stats}</div>
    </div>

    <!-- RIGHT: META + TREND + GROWTH PLAN + PROFILE/STYLE + PRACTICES -->
    <div class="right">
      <div class="panel">
        <div class="panel-title">SIGNAL COVERAGE &amp; META</div>
        {meta}
      </div>

      {trend}

      <div class="panel">
        <div class="growth-head">
          <div class="growth-title-wrap">
            <div class="growth-title">GROWTH PLAN</div>
            <div class="growth-subtitle">level up how YOU work with AI &mdash; transferable habits you build in yourself</div>
          </div>
          <div class="growth-target">coaching threshold: <b>{_esc(target)}</b> (gold line)</div>
        </div>
        {coaching}
        {strengths}
      </div>

      {profile_style}

      {practices}
    </div>

    <div class="footer">
      <b>{_esc(BRAND)}</b> · 100% local, no telemetry, no send · open-source (MIT) ·
      inspired by MEGA.dev, built deeper + private + coaching.
    </div>
  </div>
</body>
</html>'''


# =============================================================================
# PNG via Chrome headless (rasterizes the LOCAL HTML; no network)
# =============================================================================
def _rmtree_best_effort(path: str, attempts: int = 12, delay: float = 0.35) -> None:
    """Delete a temp dir without EVER raising (WinError 267 race defense).

    On Windows, headless Chrome can still hold handles inside its --user-data-dir
    for a beat after `subprocess.run` returns, so an immediate rmtree raises
    WinError 267 ("The directory name is invalid") / PermissionError. We retry
    with backoff (up to ~4s here — Chrome usually releases within 1-3s on this
    class of box), and if the OS STILL won't let go we give up SILENTLY — a leaked
    temp dir is harmless housekeeping; a traceback is not. The final attempt uses
    `ignore_errors=True`, which guarantees no exception ever escapes this function.
    """
    for i in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if i == attempts - 1:
                shutil.rmtree(path, ignore_errors=True)  # never raises
                return
            time.sleep(delay)


def _find_chrome() -> str | None:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    for name in ("chrome", "chrome.exe", "chromium", "msedge", "msedge.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _png_dimensions(png_path: Path) -> tuple[int, int] | None:
    """Read a PNG's (width, height) from its IHDR — pure stdlib, no Pillow.

    A PNG is: 8-byte signature, then chunks. The FIRST chunk is always IHDR,
    whose 13-byte data starts with 4-byte big-endian width + 4-byte height.
    We read only the first ~26 bytes. Returns None if the file isn't a PNG.
    """
    try:
        with png_path.open("rb") as fh:
            head = fh.read(26)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    import struct
    width, height = struct.unpack(">II", head[16:24])
    return int(width), int(height)


# Marker the injected probe script writes the real scrollHeight into, so a
# --dump-dom pass can read the EXACT content height back. See _inject_height_probe
# + _measure_doc_height. Zero-network (inline JS only; no fetch, no CDP socket).
_HEIGHT_MARK = "AGENTCRAFT_DOCH:"


def _inject_height_probe(html: str) -> str:
    """Append a tiny inline script that writes the real document height into the
    <title>, so a headless `--dump-dom` pass can read the EXACT content height.

    This is the deterministic full-height fix: instead of GUESSING a tall viewport
    (which either clips when too short, or -- with a fixed-position starfield that
    paints the whole viewport -- defeats the tail-trim when too tall), we MEASURE
    the rendered `documentElement.scrollHeight` in Chrome and screenshot at exactly
    that height. Pure inline JS: no network, no fetch, no remote anything (zero-egress).
    """
    probe = (
        "<script>try{document.title="
        f"'{_HEIGHT_MARK}'+"
        "Math.max(document.documentElement.scrollHeight,document.body.scrollHeight,"
        "document.documentElement.offsetHeight);}catch(e){}</script>")
    # Insert right before </body> so layout is complete when it runs.
    if "</body>" in html:
        return html.replace("</body>", probe + "</body>", 1)
    return html + probe


def _measure_doc_height(chrome: str, file_url: str, width: int) -> int | None:
    """Measure the REAL rendered document height (CSS px) of a local HTML page.

    Runs headless Chrome with `--dump-dom` against the page (whose inline probe
    script, injected by _inject_height_probe, has stamped the real scrollHeight
    into `<title>`). We parse the height marker out of the dumped DOM. This gives
    the EXACT content height, so html_to_png can screenshot at precisely that
    height -- no clip (too-short) and no dead tail (too-tall + starfield defeats
    the trim). Version-portable (--dump-dom is stable across Chrome/Edge), and
    100% local: --dump-dom prints the DOM to stdout, no network of any kind.

    Returns the height in CSS px, or None if the measure failed (caller then
    falls back to the tall-estimate + trim path, so correctness degrades safely).
    """
    profile_dir = tempfile.mkdtemp(prefix="agentcraft_measure_")
    try:
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--user-data-dir={profile_dir}", "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={width},1200",     # any height; we only read the DOM
            "--virtual-time-budget=4000",      # let layout + the probe script run
            "--dump-dom", file_url,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError):
            return None
        dom = (proc.stdout or b"").decode("utf-8", "replace")
        m = re.search(re.escape(_HEIGHT_MARK) + r"(\d+)", dom)
        if not m:
            return None
        h = int(m.group(1))
        # Sanity clamp: a real card is between ~600 and ~24000 CSS px.
        if h < 400 or h > 40000:
            return None
        return h
    finally:
        _rmtree_best_effort(profile_dir)


def _trim_png_bottom(png_path: Path, bg_is_dark: bool = True,
                     keep_pad_px: int = 24) -> bool:
    """Crop the empty tail off a tall-viewport screenshot -- pure stdlib.

    A tall-viewport capture screenshots a fixed big height, so a shorter card
    leaves a large dead band at the bottom. We parse the PNG (stdlib zlib), find
    the LAST scanline that carries real content (differs from the page's own
    background / is not fully transparent), and rewrite the PNG cropped to that
    line + a small pad. This GUARANTEES the last section is present AND the file
    has no giant transparent/blank tail. No Pillow, no network -- zlib + struct.

    Returns True if the file was trimmed (or already tight); False on any parse
    issue (caller keeps the untrimmed PNG -- still full-height, just padded).
    """
    import struct
    import zlib
    try:
        raw = png_path.read_bytes()
    except OSError:
        return False
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return False

    # ---- parse chunks; collect IHDR + concatenated IDAT ----
    pos = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    other_before = []  # chunks between IHDR and IDAT (e.g. tRNS, PLTE) to preserve
    saw_idat = False
    try:
        while pos + 8 <= len(raw):
            (clen,) = struct.unpack(">I", raw[pos:pos + 4])
            ctype = raw[pos + 4:pos + 8]
            cdata = raw[pos + 8:pos + 8 + clen]
            if ctype == b"IHDR":
                width, height, bit_depth, color_type = struct.unpack(
                    ">IIBB", cdata[:10])
            elif ctype == b"IDAT":
                idat += cdata
                saw_idat = True
            elif ctype == b"IEND":
                break
            elif not saw_idat and ctype not in (b"IHDR",):
                other_before.append((ctype, cdata))
            pos += 12 + clen  # len + type + data + crc
    except struct.error:
        return False
    if width is None or not idat:
        return False
    # Only handle the common truecolor/truecolor-alpha 8-bit case Chrome emits.
    if bit_depth != 8 or color_type not in (2, 6):
        return False
    channels = 4 if color_type == 6 else 3
    stride = width * channels

    try:
        rows = zlib.decompress(bytes(idat))
    except zlib.error:
        return False
    rowlen = stride + 1  # each scanline is prefixed by 1 filter byte
    if len(rows) < rowlen * height:
        return False

    # ---- unfilter into raw pixel scanlines (PNG filters 0-4) ----
    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        return b if pb <= pc else c

    recon = bytearray(stride * height)
    prev = bytearray(stride)
    for y in range(height):
        base = y * rowlen
        ftype = rows[base]
        line = rows[base + 1:base + 1 + stride]
        cur = bytearray(stride)
        for x in range(stride):
            raw_x = line[x]
            a = cur[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if ftype == 0:
                val = raw_x
            elif ftype == 1:
                val = raw_x + a
            elif ftype == 2:
                val = raw_x + b
            elif ftype == 3:
                val = raw_x + ((a + b) >> 1)
            elif ftype == 4:
                val = raw_x + paeth(a, b, c)
            else:
                return False
            cur[x] = val & 0xFF
        recon[y * stride:(y + 1) * stride] = cur
        prev = cur

    # ---- find the last row that carries CONTENT ----
    # ROBUST content detection -- survives BOTH tail hazards:
    #   (a) the depth page's fixed-position starfield peppers the tail with sparse
    #       1-3px star dots -> require a RUN of >= RUN_MIN contiguous content px
    #       (real text/panels are wide; a lone star is not);
    #   (b) the share page's radial-gradient background makes the tail NON-uniform
    #       (each row a slightly different near-black shade) -> compare by
    #       MAGNITUDE against the background, not exact bytes. A gradient shade is
    #       within TOL of the reference (background); real content (cyan/gold/white
    #       text) differs by >> TOL. So neither the gradient nor a star triggers a
    #       false "content" -- only genuine card pixels do.
    RUN_MIN = 24   # px; a real content run is wide, a star/gradient speck is not
    TOL = 22       # per-channel delta; below = background (gradient), above = content

    last_off = (height - 1) * stride
    if channels == 4:
        bg = None  # alpha image: content = any sufficiently opaque RUN
    else:
        from collections import Counter
        cnt = Counter()
        for x in range(0, stride, channels):
            cnt[bytes(recon[last_off + x:last_off + x + channels])] += 1
        ref = cnt.most_common(1)[0][0] if cnt else bytes(recon[last_off:last_off + channels])
        bg = (ref[0], ref[1], ref[2])

    def row_has_content(y: int) -> bool:
        off = y * stride
        run = 0
        for x in range(0, stride, channels):
            if channels == 4:
                deviates = recon[off + x + 3] > 40  # meaningfully opaque
            else:
                deviates = (abs(recon[off + x] - bg[0]) > TOL
                            or abs(recon[off + x + 1] - bg[1]) > TOL
                            or abs(recon[off + x + 2] - bg[2]) > TOL)
            if deviates:
                run += 1
                if run >= RUN_MIN:
                    return True
            else:
                run = 0
        return False

    last_content = -1
    for y in range(height - 1, -1, -1):
        if row_has_content(y):
            last_content = y
            break
    if last_content < 0:
        return False  # fully empty -> keep original, don't crop to nothing
    new_h = min(height, last_content + 1 + keep_pad_px)
    if new_h >= height:
        return True  # already tight enough; nothing to crop

    # ---- re-encode cropped image (filter 0 = None on every row) ----
    out_rows = bytearray()
    for y in range(new_h):
        out_rows.append(0)  # filter type None
        out_rows += recon[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(out_rows), 9)

    def chunk(ctype: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + ctype + data
                + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, new_h, 8, color_type, 0, 0, 0)
    out = bytearray(b"\x89PNG\r\n\x1a\n")
    out += chunk(b"IHDR", ihdr)
    for ctype, cdata in other_before:
        out += chunk(ctype, bytes(cdata))
    out += chunk(b"IDAT", comp)
    out += chunk(b"IEND", b"")
    try:
        png_path.write_bytes(bytes(out))
    except OSError:
        return False
    return True


def _estimate_tall_height(html: str) -> int:
    """Estimate a SAFE tall viewport height (CSS px) from the HTML content.

    The card is dynamic-height (grows with N coaching cards + trend + practices +
    profile). Rather than a fixed 1000px viewport (which CLIPS), we pick a viewport
    tall enough that nothing is cut, then trim the transparent/blank tail with the
    stdlib PNG bottom-crop. Base + per-section budget, clamped to a safe ceiling.
    Deliberately over-estimates -- an over-tall viewport is harmless (it's trimmed);
    an under-tall one clips (the exact bug we're killing).
    """
    # Tuned to slightly OVER-estimate the real content height (so nothing clips)
    # without a huge wasteful tail -- the tail is trimmed, but a tighter viewport
    # also makes the (pure-Python) trim scan proportionally faster.
    base = 760                                   # header + radar + brand + footer
    n_coach = html.count('class="coach"')
    base += 360 * n_coach                        # a coaching card (weak/why/how/example)
    for marker, px in (('class="panel"', 300),   # a right-column HUD panel
                       ('class="coach-excerpt', 96),   # FROM-YOUR-WORK block
                       ('trend-svg', 240),       # the trend sparkline
                       ('class="pa-row', 42),    # a practice / anti-pattern row
                       ('class="strength"', 32), # a strength line
                       ('class="chip"', 28)):    # a profile/style chip
        base += px * html.count(marker)
    return max(1200, min(base, 24000))


def html_to_png(html_path: Path, png_path: Path,
                width: int = 1264, height: int | None = None,
                full_height: bool = True) -> bool:
    """Rasterize a LOCAL HTML file to PNG via headless Chrome. No network.

    FULL-HEIGHT CAPTURE (the truncation fix): the card is dynamic-height, so a
    fixed viewport clips the tail. We MEASURE the real content height in Chrome
    (`_measure_doc_height` reads a probe script's `documentElement.scrollHeight`
    via `--dump-dom`) and screenshot at exactly that height -- so the whole card
    is captured with no clip and no dead tail. If the measure fails, we fall back
    to a generous ESTIMATE (`_estimate_tall_height`) + a pure-stdlib bottom-trim
    (`_trim_png_bottom`). The measure-first path is what makes the depth page --
    whose fixed-position starfield paints the entire viewport and defeats the
    tail-trim -- render tight (no 1000px clip, no giant void band). Zero network:
    Chrome only rasterizes the local file; the probe is inline JS, no fetch.

    Returns True if a PNG file was produced, False otherwise (caller keeps HTML).
    """
    chrome = _find_chrome()
    if not chrome:
        print("[png] Chrome/Edge not found — HTML-only fallback.", file=sys.stderr)
        return False

    # Resolve to ABSOLUTE paths: Chrome resolves a relative --screenshot= target
    # against its own CWD (which differs under a fresh --user-data-dir), so a
    # relative out path would write the PNG somewhere we never look. Absolute
    # kills that ambiguity.
    html_path = html_path.resolve()
    png_path = png_path.resolve()
    file_url = html_path.as_uri()
    if png_path.exists():
        try:
            png_path.unlink()
        except OSError:
            pass

    # Size the viewport to contain the WHOLE card so the fixed-viewport clip can't
    # happen. Strategy (in order of preference):
    #   1. MEASURE the real content height in Chrome (a probe script stamps
    #      documentElement.scrollHeight into <title>; a --dump-dom pass reads it),
    #      then screenshot at exactly that height -> tight, no tail. Deterministic
    #      when Chrome's --dump-dom yields output.
    #   2. If the measure is unavailable/empty (some headless builds print nothing
    #      to --dump-dom), fall back to a generous ESTIMATE + a starfield-robust
    #      bottom-trim (_trim_png_bottom requires a RUN of content pixels, so a
    #      sparse fixed-position starfield in the tail can't defeat the crop).
    # A caller-pinned explicit height (legacy) is honored verbatim.
    measured = False
    if height is None:
        try:
            html = html_path.read_text(encoding="utf-8")
        except OSError:
            html = ""
        cap_height = None
        if full_height:
            # (1) Measure the true content height via a probe-injected temp copy.
            probe_path = html_path.with_name(html_path.stem + ".measure.html")
            try:
                probe_path.write_text(_inject_height_probe(html), encoding="utf-8")
                real_h = _measure_doc_height(chrome, probe_path.as_uri(), width)
            except OSError:
                real_h = None
            finally:
                try:
                    probe_path.unlink()
                except OSError:
                    pass
            if real_h is not None:
                # +36px pad so a sub-pixel/rounded last line is never shaved.
                cap_height = real_h + 36
                measured = True
        if cap_height is None:
            cap_height = _estimate_tall_height(html) if full_height else 1000
    else:
        cap_height = height
        full_height = False  # explicit height => no trim (caller owns it)
    # If we measured the exact height, the screenshot is already tight. If we
    # ESTIMATED (measure unavailable), always run the starfield-robust bottom-trim
    # to crop the dead band. Either way the WHOLE card is captured (never clipped).
    do_trim = full_height and not measured

    # A FRESH, DEDICATED --user-data-dir is the critical flag: without it, a
    # spawned Chrome attaches to any already-running Chrome (singleton/default
    # profile), forwards the URL to that instance, and exits rc=0 WITHOUT taking
    # the screenshot — the classic "rc=0, no file" symptom. An isolated temp
    # profile forces a standalone headless render.
    # --virtual-time-budget makes Chrome flush layout/paint before snapshotting.
    # --no-sandbox is required for headless Chrome on Windows in this environment.
    # Some environments (fresh sandboxes, a stale Chrome singleton) hit the
    # "rc=0, no screenshot" race on the first launch. Retry once with a fresh
    # isolated profile before falling back to HTML — cheap insurance, no cost
    # on the happy path (first attempt returns immediately on success).
    last_rc = None
    last_err = b""
    for _attempt in range(2):
        profile_dir = tempfile.mkdtemp(prefix="agentcraft_chrome_")
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--user-data-dir={profile_dir}",  # <-- isolate from running Chrome
            "--no-first-run",
            "--no-default-browser-check",
            "--force-device-scale-factor=2",   # crisp 2x render
            "--virtual-time-budget=5000",      # wait for layout/paint, then snapshot
            "--default-background-color=00000000",
            f"--window-size={width},{cap_height}",
            f"--screenshot={str(png_path)}",
            file_url,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
            last_rc, last_err = proc.returncode, (proc.stderr or b"")
        except subprocess.TimeoutExpired:
            print("[png] Chrome timed out — retry / HTML fallback.", file=sys.stderr)
            _rmtree_best_effort(profile_dir)
            continue
        except OSError as exc:
            print(f"[png] Chrome launch failed: {exc} — HTML-only fallback.", file=sys.stderr)
            _rmtree_best_effort(profile_dir)
            return False
        finally:
            # WinError 267 rmtree race: Chrome may still hold handles in the temp
            # profile dir when this finally runs. Retry-then-ignore; never raise.
            _rmtree_best_effort(profile_dir)

        # Wait for a stable, non-empty file (Chrome writes async on some builds).
        last = -1
        produced = False
        for _ in range(50):  # up to ~5s
            if png_path.exists():
                sz = png_path.stat().st_size
                if sz > 0 and sz == last:
                    produced = True
                    break
                last = sz
            time.sleep(0.1)
        if not produced and png_path.exists() and png_path.stat().st_size > 0:
            produced = True
        if produced:
            # When we MEASURED the exact height, the capture is already tight --
            # no trim needed (and trimming is skipped because a fixed-position
            # starfield would defeat the tail-detection anyway). When we ESTIMATED
            # a tall viewport, trim the blank tail so the PNG is exactly the card
            # height. Best-effort: a trim parse failure leaves the full-height
            # (padded) PNG -- the whole card is still present. Either way: no clip.
            if do_trim:
                try:
                    _trim_png_bottom(png_path)
                except Exception as exc:  # never let trim break a good capture
                    print(f"[png] bottom-trim skipped ({exc}); PNG is full-height "
                          f"with padding.", file=sys.stderr)
            return True
        # no file this attempt -> loop retries once with a fresh profile

    tail = (last_err or b"").decode("utf-8", "replace")[-300:]
    print(f"[png] no PNG produced (rc={last_rc}) after retry — HTML is ready "
          f"(open the .html). stderr tail:\n{tail}", file=sys.stderr)
    return False


# =============================================================================
# Text summary (works even without any drawing / Chrome)
# =============================================================================
def _summarize_code_audit(report: dict) -> str:
    """Text summary for a LENS B code-audit report (axes C1..C8)."""
    overall = report.get("overall", {}) or {}
    sr = report.get("scan_ref", {}) or {}
    lines = [
        f"{BRAND} - Lens B (your code) code audit",
        f"CODE GRADE {overall.get('score')} ({overall.get('tier')})",
    ]
    files = sr.get("total_files")
    loc = sr.get("total_loc")
    if files is not None or loc is not None:
        lines.append(f"Scan: {files} files, {loc} LOC")
    lines.append("Axes:")
    axes = report.get("axes", {}) or {}
    for short in CODE_AXIS_ORDER:
        ax = _code_axis_lookup(axes, short)
        if not ax:
            lines.append(f"  {short} {CODE_AXIS_LABELS.get(short, short)}: (absent)")
            continue
        score = ax.get("score")
        name = ax.get("name") or CODE_AXIS_LABELS.get(short, short)
        ms = ax.get("measurement_status")
        ms_tag = ""
        if ms == "unmeasured":
            lim = ax.get("limitations")
            ms_tag = f" [unmeasured: {lim}]" if lim else " [unmeasured]"
        lines.append(f"  {short} {name}: {_fmt_score(score)}{ms_tag}")
    lines.append(f"Findings: {len(report.get('findings', []) or [])}")
    lines.append(f"Strengths: {len(report.get('strengths', []) or [])}")
    return "\n".join(lines)


def _summarize(report: dict) -> str:
    if _is_code_audit(report):
        return _summarize_code_audit(report)
    ver = str(report.get("agentcraft_version", "1"))
    overall = report.get("overall", {})
    lines = [
        f"{BRAND} - {TAGLINE}  (schema v{ver})",
        f"OVERALL {overall.get('score')} ({overall.get('tier')})",
        "Pillars:",
    ]
    for key in PILLAR_ORDER:
        p = report["pillars"][key]
        score = p.get("score")
        flag = " [moat]" if p.get("moat") or key in MOAT_PILLARS else ""
        # v2: name the measurement status when a pillar is unmeasured (honest-empty).
        ms = p.get("measurement_status")
        ms_tag = ""
        if ms == "unmeasured":
            lim = p.get("limitations")
            ms_tag = f" [unmeasured: {lim}]" if lim else " [unmeasured]"
        lines.append(f"  {key} {PILLAR_LABELS[key]}: {_fmt_score(score)}{flag}{ms_tag}")
    # v2: surface the prove-don't-declare verified stat if present.
    vr = (report.get("meta_metrics", {}) or {}).get("verified_rate", {}) or {}
    if vr.get("pct") is not None:
        lines.append(f"% VERIFIED: {vr['pct']}%"
                     + (f" ({vr['verified']}/{vr['applied']} applied confirmed)"
                        if vr.get("verified") is not None and vr.get("applied") is not None
                        else ""))
    coaching = report.get("coaching", [])
    lines.append(f"Coaching entries: {len(coaching)}")
    if report.get("trend"):
        lines.append(f"Trend weeks: {len(report['trend'])} (P6/P7 compounding visible)")
    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================
def _one_page(html_builder, out_png: Path, html_only: bool,
              guard=None) -> dict:
    """Write one page's HTML (+ full-height PNG). `guard` is an optional callable
    that inspects the HTML and RAISES to block a leaking shareable page."""
    html = html_builder()
    if guard is not None:
        guard(html)  # fail-loud BEFORE writing (redaction invariant for page 1)
    html_path = out_png.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    out = {"html": html_path, "png": None}
    if html_only:
        return out
    if html_to_png(html_path, out_png):  # full-height capture (no clip)
        out["png"] = out_png
    return out


def _page_paths(out: Path) -> tuple[Path, Path]:
    """Resolve (share_png, depth_png) from the --out argument.

    Two shapes are accepted:
      * a DIRECTORY (e.g. --out cards)  -> writes cards/agentcraft-card-share.png +
        cards/agentcraft-card-depth.png (both auto-git-ignored by the agentcraft-card* /
        *-depth.* globs).
      * a FILE path (e.g. --out me.png) -> writes me-share.png + me-depth.png
        siblings (the depth twin carries the '-depth' marker so it's git-ignored).
    Both filenames match a .gitignore glob so a scan's output never gets committed.
    """
    s = str(out)
    is_dir = out.is_dir() or s.endswith(("/", "\\")) or (out.suffix == "")
    if is_dir:
        base = out
        base.mkdir(parents=True, exist_ok=True)
        return base / "agentcraft-card-share.png", base / "agentcraft-card-depth.png"
    stem = out.with_suffix("")          # strip extension
    suffix = out.suffix or ".png"
    # Ensure the target's parent dir exists too (mirrors the DIRECTORY branch's
    # mkdir). Without this, `--out sub/dir/card.png` where sub/dir/ is absent
    # crashes with FileNotFoundError on the first write_text -- a real bug: only
    # the directory branch created its target, so a nested FILE path failed.
    parent = stem.parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    return (parent / f"{stem.name}-share{suffix}",
            parent / f"{stem.name}-depth{suffix}")


def build_index_html(report: dict, share_href: str | None = None,
                     depth_href: str | None = None,
                     repo_href: str | None = None) -> str:
    """The landing ENTRY POINT that ties BOTH LENSES together (FAZA 4).

    A small, self-contained, zero-egress page (system fonts, no CDN, no network)
    that presents AGENTCRAFT as TWO LENSES, walkable from one obvious file:

      (1) YOU  -- how you WORK with agents (Lens A): the collaboration card
          (`share_href`) + private command-center depth dashboard (`depth_href`).
      (2) YOUR CODE -- the repo audit (Lens B): the code-audit dashboard
          (`repo_href`).

    Each href is a BARE .html basename (redaction-safe, no path). A lens whose
    target isn't provided in this run is still SHOWN (so the two-lens product is
    always legible) but rendered as a dimmed "run this lens to unlock" card with
    no link -- honest-empty, never a dangling href.
    """
    overall = report.get("overall", {}) or {}
    oscore = int(round(overall.get("score", 0)))
    tier = overall.get("tier", tier_for(oscore,
                        (report.get("config", {}) or {}).get("tier_bands")))
    ts = TIER_STYLE.get(tier, TIER_STYLE["silver"])

    # -- Lens A block (YOU): links to the collaboration card + depth dashboard.
    # NOTE: nested <a> is invalid HTML (browsers hoist the inner anchor OUT of the
    # outer, breaking the card layout). So the Lens A card is a <div> with explicit
    # link BUTTONS inside — never an <a> wrapping other <a>s.
    if share_href or depth_href:
        secondary_bits = []
        if share_href:
            secondary_bits.append(f'<a class="lens-sub" href="{_esc(share_href)}">'
                                  f'shareable card &rarr;</a>')
        if depth_href:
            secondary_bits.append(f'<a class="lens-sub" href="{_esc(depth_href)}">'
                                  f'command-center depth &rarr;</a>')
        lens_a = (f'<div class="idx-card idx-card-multi">'
                  f'<div class="idx-num">&#9312; &nbsp;YOU</div>'
                  f'<div class="idx-title">How you work with agents</div>'
                  f'<div class="idx-desc">Lens A &mdash; your habits, your memory '
                  f'&amp; continuity, your coaching plan. The redacted card is safe '
                  f'to share; the private command-center depth stays on your disk.</div>'
                  f'<div class="lens-subs">{"".join(secondary_bits)}</div>'
                  f'</div>')
    else:
        lens_a = ('<div class="idx-card idx-card-off">'
                  '<div class="idx-num">&#9312; &nbsp;YOU</div>'
                  '<div class="idx-title">How you work with agents</div>'
                  '<div class="idx-desc">Lens A &mdash; run the collaboration '
                  'assessment on your Claude Code history to unlock this lens.</div>'
                  '<div class="idx-go idx-go-off">run Lens A to unlock</div></div>')

    # -- Lens B block (YOUR CODE): links to the code-audit dashboard.
    if repo_href:
        lens_b = (f'<a class="idx-card" href="{_esc(repo_href)}">'
                  f'<div class="idx-num">&#9313; &nbsp;YOUR CODE</div>'
                  f'<div class="idx-title">Repo audit</div>'
                  f'<div class="idx-desc">Lens B &mdash; a code-audit command-center: '
                  f'the overall code grade + tier and all 8 axes (architecture, '
                  f'reliability, security, tests, maintainability, performance, docs, '
                  f'dependencies), top findings + refactor priorities.</div>'
                  f'<div class="idx-go">Enter the audit &rarr;</div></a>')
    else:
        lens_b = ('<div class="idx-card idx-card-off">'
                  '<div class="idx-num">&#9313; &nbsp;YOUR CODE</div>'
                  '<div class="idx-title">Repo audit</div>'
                  '<div class="idx-desc">Lens B &mdash; run the repo scan on a '
                  'codebase to unlock the 8-axis code-audit command-center.</div>'
                  '<div class="idx-go idx-go-off">run Lens B to unlock</div></div>')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(BRAND)} — start here (two lenses)</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    min-height: 100%;
    background: radial-gradient(1200px 800px at 20% -10%, {PALETTE["bg1"]} 0%, {PALETTE["bg0"]} 60%);
    color: {PALETTE["ink"]};
    font-family: {_FONT_STACK};
    -webkit-font-smoothing: antialiased;
  }}
  .idx-stage {{ max-width: 820px; margin: 0 auto; padding: 72px 32px 48px; }}
  .idx-brand {{
    font-size: 40px; font-weight: 900; letter-spacing: 4px; text-align:center;
    background: linear-gradient(90deg, {ts["accent"]}, {ts["accent2"]});
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }}
  .idx-tag {{ text-align:center; margin-top: 10px; font-size: 14px; color: {PALETTE["ink_dim"]}; letter-spacing:.4px; }}
  .idx-lede {{ text-align:center; margin: 22px auto 0; max-width: 600px; font-size: 14px; line-height:1.6; color: {PALETTE["ink_dim"]}; }}
  .idx-lede b {{ color: {ts["accent"]}; }}
  .idx-cards {{ display:grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 40px; }}
  @media (max-width: 680px) {{ .idx-cards {{ grid-template-columns: 1fr; }} }}
  .idx-card {{
    display:flex; flex-direction:column; gap:10px; text-decoration:none;
    border-radius: 20px; padding: 26px 24px 24px;
    background: linear-gradient(180deg, {PALETTE["card_top"]} 0%, {PALETTE["card_bot"]} 100%);
    border: 1px solid {PALETTE["line"]};
    box-shadow: 0 18px 44px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04);
    transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease;
  }}
  a.idx-card:hover {{ transform: translateY(-3px); border-color: {ts["accent"]}66; box-shadow: 0 24px 56px rgba(0,0,0,0.6); }}
  .idx-card-off {{ opacity: .58; }}
  .idx-num {{ font-size: 13px; font-weight: 900; letter-spacing: 2px; color: {ts["accent"]}; }}
  .idx-title {{ font-size: 19px; font-weight: 800; color: {PALETTE["ink"]}; }}
  .idx-desc {{ font-size: 13px; line-height: 1.55; color: {PALETTE["ink_dim"]}; }}
  .idx-go {{ margin-top: 6px; font-size: 13px; font-weight: 800; color: {ts["accent"]}; }}
  .idx-go-off {{ color: {PALETTE["ink_faint"]}; font-style: italic; }}
  /* Lens A multi-link card: two explicit link buttons inside a non-anchor card
     (nested <a> is invalid HTML — this keeps both links legal + inside the card). */
  .idx-card-multi {{ cursor: default; }}
  .lens-subs {{ margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }}
  .lens-sub {{
    display: inline-flex; align-self: flex-start; text-decoration: none;
    font-size: 12.5px; font-weight: 800; color: {ts["accent"]};
    padding: 6px 12px; border-radius: 999px;
    border: 1px solid {ts["accent"]}44; background: {ts["accent"]}12;
    transition: background .15s ease, border-color .15s ease, transform .15s ease;
  }}
  .lens-sub:hover {{ background: {ts["accent"]}22; border-color: {ts["accent"]}88; transform: translateY(-1px); }}
  .idx-foot {{ text-align:center; margin-top: 40px; font-size: 11px; color: {PALETTE["ink_faint"]}; }}
  .idx-foot b {{ color: {PALETTE["ink_dim"]}; }}
</style>
</head>
<body>
  <div class="idx-stage">
    <div class="idx-brand">{_esc(BRAND)}</div>
    <div class="idx-tag">{_esc(TAGLINE)}</div>
    <p class="idx-lede">
      Two lenses, one tool &mdash; <b>YOU</b> (how you work with AI agents) and
      <b>YOUR CODE</b> (a repo audit). Scored 100% locally, nothing sent anywhere.
    </p>
    <div class="idx-cards">
      {lens_a}
      {lens_b}
    </div>
    <div class="idx-foot">
      <b>{_esc(BRAND)}</b> &middot; two lenses: You + Your Code &middot; 100% local, no telemetry, no send &middot; open-source (MIT)
    </div>
  </div>
</body>
</html>'''


def _repo_page_path(out: Path) -> Path:
    """Resolve the SINGLE code-audit page output path from --out.

    Unlike the Lens A two-page split (`-share`/`-depth`), the Lens B code-audit is
    ONE page. We keep the caller's basename verbatim (so a caller can name it
    e.g. `sample-repo-card.png` — deliberately NOT matching the `*-depth.*`
    git-ignore glob). A DIRECTORY --out writes `agentcraft-code-audit.png` inside.
    """
    s = str(out)
    is_dir = out.is_dir() or s.endswith(("/", "\\")) or (out.suffix == "")
    if is_dir:
        out.mkdir(parents=True, exist_ok=True)
        return out / "agentcraft-code-audit.png"
    parent = out.parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    return out if out.suffix else out.with_suffix(".png")


def render_code_audit(report: dict, out: Path, html_only: bool = False,
                      index: bool = True) -> dict:
    """Render the LENS B code-audit COMMAND-CENTER (one page) + a two-lens index.

    Writes the code-audit dashboard HTML (always) + a full-height PNG (unless
    html_only / Chrome missing), and — when `index` — a unified `index.html`
    presenting BOTH lenses (Lens A card unlockable, Lens B pointing at THIS page).

    Returns {"repo": {...}, "index": <Path or None>}.
    """
    repo_png = _repo_page_path(out)
    written: dict = {"repo": None, "index": None}

    repo_href = repo_png.with_suffix(".html").name if index else None
    nav_href = "index.html" if index else None

    written["repo"] = _one_page(
        lambda: build_repo_html(report, nav_href=nav_href),
        repo_png, html_only)   # private page — NOT redaction-guarded (paths OK)

    if index:
        index_path = repo_png.with_name("index.html")
        index_path.write_text(
            build_index_html(report, share_href=None, depth_href=None,
                             repo_href=repo_href),
            encoding="utf-8")
        written["index"] = index_path
    return written


def render(report: dict, out: Path, html_only: bool = False,
           page: str = "both") -> dict:
    """Render AGENTCRAFT pages for whichever LENS the report belongs to.

    LENS B (code-audit report, report_kind == "code-audit"): delegates to
    render_code_audit — one command-center page + a two-lens index. `page` is
    ignored for Lens B (there is only one page).

    LENS A (collaboration report): renders the TWO pages (SPEC section 7.1) —
    a REDACTED shareable card (page 1) and a PRIVATE HUD depth dashboard (page 2).
    Each is HTML (always) + a full-height PNG (unless html_only / Chrome missing).

    `page` selects which to render: 'both' (default) | 'share' | 'depth'.
    The shareable page passes through `_redaction_guard` (fail-loud on any leak)
    before it is written -- the shareable artifact carries no path/filename/UUID.

    When `page == 'both'` the pages are made NAVIGABLE: each links to the OTHER's
    bare .html basename (`.name`, never a full path -- guard-safe), and a two-lens
    `index.html` landing entry point is written alongside them. A single-page
    render passes NO nav (so there is never a dangling link to a page we did not
    write).

    Returns a dict of paths actually written (keys vary by lens).
    """
    # LENS B route: a code-audit report has axes (C1..C8), not pillars.
    if _is_code_audit(report):
        return render_code_audit(report, out, html_only=html_only)

    share_png, depth_png = _page_paths(out)
    written: dict = {"share": None, "depth": None, "index": None}

    # Cross-link only when rendering BOTH pages. Basenames are bare .html (from
    # `.with_suffix('.html').name`) -- no path/drive, so page 1 survives the guard.
    both = page == "both"
    share_href = depth_png.with_suffix(".html").name if both else None
    depth_href = share_png.with_suffix(".html").name if both else None

    if page in ("both", "share"):
        written["share"] = _one_page(
            lambda: build_share_html(report, nav_href=share_href),
            share_png, html_only,
            guard=_redaction_guard)   # <-- redaction invariant enforced here
    if page in ("both", "depth"):
        written["depth"] = _one_page(
            lambda: build_depth_html(report, nav_href=depth_href),
            depth_png, html_only)

    if both:
        # Two-lens landing entry point. Lens A (this run) links to the two pages;
        # Lens B is shown as "run to unlock" (a code audit is a separate report).
        index_path = share_png.with_name("index.html")
        index_path.write_text(
            build_index_html(
                report,
                share_href=share_png.with_suffix(".html").name,
                depth_href=depth_png.with_suffix(".html").name,
                repo_href=None),
            encoding="utf-8")
        written["index"] = index_path
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentcraft_card",
        description=f"{BRAND} offline card renderer (100% local, no network). "
                    f"Emits TWO pages: a redacted shareable card + a private HUD "
                    f"depth dashboard.",
    )
    parser.add_argument("--report", required=True, help="path to AGENTCRAFT report JSON")
    parser.add_argument("--out", default="agentcraft-card.png",
                        help="output PNG path OR directory. A DIRECTORY writes "
                             "agentcraft-card-share.png + agentcraft-card-depth.png inside; "
                             "a FILE path writes <name>-share.png + <name>-depth.png "
                             "siblings. HTML twins written alongside each.")
    parser.add_argument("--page", choices=["both", "share", "depth"], default="both",
                        help="Lens A only: which page(s) to render: both (default) "
                             "| share (page 1, redacted, shareable) | depth (page 2, "
                             "private HUD dashboard). Ignored for a code-audit report.")
    parser.add_argument("--kind", choices=["auto", "collab", "repo"], default="auto",
                        help="which LENS to render: auto (default — detect from "
                             "report_kind) | collab (Lens A, how you work) | repo "
                             "(Lens B, the code-audit command-center). 'repo' forces "
                             "the code-audit page even if report_kind is absent.")
    parser.add_argument("--html-only", action="store_true",
                        help="write HTML only; skip the Chrome PNG step")
    parser.add_argument("--summary-only", action="store_true",
                        help="print a text summary and exit (no files written)")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"error: report not found: {report_path}", file=sys.stderr)
        return 2

    try:
        report = load_report(report_path)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: invalid report: {exc}", file=sys.stderr)
        return 2

    # --kind forces a lens: 'repo' requires a code-audit report; 'collab' requires
    # a pillar report. 'auto' trusts _is_code_audit (report_kind). Fail loud on a
    # mismatch rather than render the wrong builder.
    detected_repo = _is_code_audit(report)
    if args.kind == "repo" and not detected_repo:
        print("error: --kind repo given but the report is not a code-audit "
              "(no axes/report_kind). Refusing to render.", file=sys.stderr)
        return 2
    if args.kind == "collab" and detected_repo:
        print("error: --kind collab given but the report is a code-audit "
              "(axes C1..C8). Refusing to render.", file=sys.stderr)
        return 2

    if args.summary_only:
        print(_summarize(report))
        return 0

    try:
        written = render(report, Path(args.out), html_only=args.html_only,
                         page=args.page)
    except ValueError as exc:  # redaction guard fired on the shareable page
        print(f"error: {exc}", file=sys.stderr)
        return 2

    labels = {"share": "PAGE 1 (shareable, redacted)",
              "depth": "PAGE 2 (private HUD depth dashboard)",
              "repo": "CODE AUDIT (Lens B — command-center dashboard)"}
    any_png = False
    for key in ("share", "depth", "repo"):
        w = written.get(key)
        if not w:
            continue
        print(f"{labels[key]}")
        print(f"  wrote HTML: {w['html'].resolve()}")
        if w["png"]:
            print(f"  wrote PNG:  {w['png'].resolve()}")
            any_png = True
        else:
            print("  PNG: not produced (HTML-only). Open the HTML to view/print.")
    index_path = written.get("index")
    if index_path:
        print("INDEX (two-lens landing entry point — start here)")
        print(f"  wrote HTML: {index_path.resolve()}")
    if not any_png and not args.html_only:
        print("(PNG not produced — Chrome/Edge missing. HTML is ready.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
