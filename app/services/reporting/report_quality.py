"""
Report Quality Gate for the EASM client-facing PDF deliverable.

This module inspects a *rendered* report (its per-page extracted text) together
with the underlying database state and decides whether the document meets the
minimum bar for a premium, consultancy-grade deliverable. It is intentionally
strict: a report that "sucks" — empty findings when findings exist, a KPI-only
executive summary with no real prose, mostly-empty pages, or missing sections —
must FAIL so the generator can be corrected before anything reaches a client.

Public API:
    evaluate_report_quality(db, tenant_id, page_texts: list[str]) -> dict
        Returns {'overall': 'pass'|'fail',
                 'checks': [{'name', 'status', 'detail'}, ...],
                 'summary': str}

The page text is expected to come from pymupdf (``fitz``):
    doc = fitz.open(path); page_texts = [p.get_text() for p in doc]
No PDF parsing happens here — the caller supplies the extracted text so the gate
stays decoupled from any particular rendering library.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Minimum non-whitespace characters a content page must contain before it is
# considered "substantial" rather than nearly blank.
MIN_PAGE_CHARS = 220
# The cover is deliberately airy; it is held to a lower (but non-zero) bar.
MIN_COVER_CHARS = 90
# Minimum amount of genuine prose (long, sentence-like lines) the executive
# summary must contain to count as a real narrative rather than labels/numbers.
MIN_NARRATIVE_CHARS = 350
MIN_NARRATIVE_SENTENCES = 3

RISK_WORDS = ("critical", "high", "moderate", "medium", "low", "minimal")

# Phrases that indicate the findings section rendered an "empty" state.
_EMPTY_FINDING_PHRASES = (
    "no confirmed vulnerabilities",
    "no open findings",
    "no findings",
    "did not surface any confirmed findings",
    "no issues",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _pass(name: str, detail: str) -> Dict[str, str]:
    return {"name": name, "status": "pass", "detail": detail}


def _fail(name: str, detail: str) -> Dict[str, str]:
    return {"name": name, "status": "fail", "detail": detail}


def _db_finding_count(db, tenant_id: int) -> int:
    """Count findings for the tenant, defensively (0 on any error)."""
    try:
        from app.repositories.finding_repository import FindingRepository
        stats = FindingRepository(db).get_finding_stats(tenant_id, days=0) or {}
        return int(stats.get("total", 0) or 0)
    except Exception:
        try:
            from app.models.database import Finding, Asset
            return (
                db.query(Finding).join(Asset)
                .filter(Asset.tenant_id == tenant_id).count()
            )
        except Exception:
            return 0


def _db_finding_names(db, tenant_id: int, limit: int = 25) -> List[str]:
    try:
        from app.repositories.finding_repository import FindingRepository
        finds = FindingRepository(db).get_findings(tenant_id, limit=limit) or []
        return [n for n in ((getattr(f, "name", None) or "").strip() for f in finds) if n]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
def _check_sections_present(pages_lower: str) -> Dict[str, str]:
    required = {
        "cover": ("external attack surface", "security assessment report", "confidential"),
        "executive summary": ("executive summary",),
        "findings": ("findings",),
        "attack surface": ("attack surface",),
        "recommendations": ("recommendation",),
    }
    missing = []
    for label, needles in required.items():
        if not any(n in pages_lower for n in needles):
            missing.append(label)
    if missing:
        return _fail("sections_present",
                     f"Missing required section(s): {', '.join(missing)}.")
    return _pass("sections_present",
                 "All required sections present (cover, executive summary, "
                 "attack surface, findings, recommendations).")


def _check_exec_summary_narrative(page_texts: List[str]) -> Dict[str, str]:
    exec_page = ""
    for p in page_texts:
        if "executive summary" in (p or "").lower():
            exec_page = p
            break
    if not exec_page:
        return _fail("exec_summary_narrative",
                     "No page containing an 'Executive Summary' heading was found.")

    # Genuine prose = lines with several words (KPI tiles / labels are short).
    prose_lines = [ln.strip() for ln in exec_page.splitlines()
                   if len(ln.split()) >= 6]
    prose = _norm(" ".join(prose_lines))
    sentences = prose.count(".")
    if len(prose) < MIN_NARRATIVE_CHARS or sentences < MIN_NARRATIVE_SENTENCES:
        return _fail("exec_summary_narrative",
                     f"Executive summary prose too thin ({len(prose)} chars, "
                     f"{sentences} sentences; need >= {MIN_NARRATIVE_CHARS} chars "
                     f"and >= {MIN_NARRATIVE_SENTENCES} sentences). Looks like "
                     f"KPI tiles without a written narrative.")
    return _pass("exec_summary_narrative",
                 f"Executive summary contains a written narrative "
                 f"({len(prose)} chars across {sentences} sentences).")


def _check_findings_rendered(db, tenant_id: int, page_texts: List[str],
                             pages_lower: str) -> Dict[str, str]:
    db_count = _db_finding_count(db, tenant_id)
    if db_count == 0:
        # No findings in DB: the section may legitimately show a clean-state note.
        return _pass("findings_rendered",
                     "Tenant has no findings in the database; a clean-state "
                     "findings section is acceptable.")

    # Findings exist -> the report must actually list them.
    empty_hit = next((ph for ph in _EMPTY_FINDING_PHRASES if ph in pages_lower), None)
    names = _db_finding_names(db, tenant_id)
    listed = sum(1 for n in names if n.lower() in pages_lower)

    if listed == 0:
        return _fail("findings_rendered",
                     f"Database has {db_count} finding(s) but none of the actual "
                     f"finding names appear in the report"
                     + (f" (and it states '{empty_hit}')." if empty_hit else "."))
    if empty_hit:
        return _fail("findings_rendered",
                     f"Report lists findings yet also claims '{empty_hit}', "
                     f"which is contradictory.")
    return _pass("findings_rendered",
                 f"{db_count} finding(s) in DB; {listed} distinct finding name(s) "
                 f"rendered in the report.")


def _check_no_empty_pages(page_texts: List[str]) -> Dict[str, str]:
    thin = []
    for idx, p in enumerate(page_texts):
        chars = len(_norm(p))
        floor = MIN_COVER_CHARS if idx == 0 else MIN_PAGE_CHARS
        if chars < floor:
            thin.append(f"page {idx + 1} ({chars} chars)")
    if thin:
        return _fail("no_empty_pages",
                     "Nearly-blank page(s) detected: " + "; ".join(thin) + ".")
    return _pass("no_empty_pages",
                 f"All {len(page_texts)} page(s) carry substantial content "
                 f"(>= {MIN_PAGE_CHARS} chars each).")


def _check_risk_posture_present(pages_lower: str) -> Dict[str, str]:
    if "risk posture" not in pages_lower and "risk rating" not in pages_lower:
        return _fail("risk_posture_present",
                     "No overall 'risk posture' / 'risk rating' statement found.")
    if not any(w in pages_lower for w in RISK_WORDS):
        return _fail("risk_posture_present",
                     "Risk posture heading present but no rating word "
                     "(critical/high/medium/moderate/low/minimal) stated.")
    return _pass("risk_posture_present",
                 "An overall risk posture with an explicit rating is stated.")


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def evaluate_report_quality(db, tenant_id: int, page_texts: List[str]) -> Dict[str, Any]:
    """Evaluate whether the rendered report meets the premium quality bar.

    Args:
        db: SQLAlchemy session (used to cross-check DB state vs. rendered output).
        tenant_id: Tenant primary key.
        page_texts: Per-page extracted text, e.g. ``[p.get_text() for p in fitz.open(path)]``.

    Returns:
        {'overall': 'pass'|'fail', 'checks': [...], 'summary': str}
    """
    page_texts = list(page_texts or [])
    pages_lower = "\n".join(page_texts).lower()

    checks: List[Dict[str, str]] = [
        _check_sections_present(pages_lower),
        _check_exec_summary_narrative(page_texts),
        _check_findings_rendered(db, tenant_id, page_texts, pages_lower),
        _check_no_empty_pages(page_texts),
        _check_risk_posture_present(pages_lower),
    ]

    failed = [c for c in checks if c["status"] == "fail"]
    overall = "fail" if failed else "pass"

    if overall == "pass":
        summary = (f"PASS — {len(checks)}/{len(checks)} quality checks satisfied "
                   f"across {len(page_texts)} page(s).")
    else:
        summary = (f"FAIL — {len(failed)}/{len(checks)} quality check(s) failed: "
                   + ", ".join(c["name"] for c in failed) + ".")

    return {"overall": overall, "checks": checks, "summary": summary}
