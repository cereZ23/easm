"""
Client-facing PDF security report generator for the EASM platform.

Produces a polished "External Attack Surface Assessment" PDF deliverable using
pure ReportLab (Platypus). No external system libraries, no network access, no
external fonts — Helvetica family only.

Public API:
    generate_scan_report(db, tenant_id, prepared_by="Security Team") -> bytes

The module is fully self-contained and defensive: it never assumes a field is
present, and renders sensible "nothing found" states for empty result sets.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.models.database import Asset, AssetType, Service
from app.repositories.asset_repository import AssetRepository
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.endpoint_repository import EndpointRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.service_repository import ServiceRepository

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
PRIMARY = colors.HexColor("#0F2A43")   # deep navy — brand primary
PRIMARY_DK = colors.HexColor("#0A1E30")  # darker navy for the cover band
ACCENT = colors.HexColor("#1B9AAA")    # teal accent
INK = colors.HexColor("#1B2733")       # body text
MUTED = colors.HexColor("#5A6B7B")     # secondary text
HAIRLINE = colors.HexColor("#D7DEE5")  # table grid / rules
ZEBRA = colors.HexColor("#F4F7FA")     # alternating row shade
CARD_BG = colors.HexColor("#F0F5F9")   # KPI card background
LIGHT = colors.HexColor("#FFFFFF")

SEV_COLORS = {
    "critical": colors.HexColor("#B00020"),
    "high": colors.HexColor("#E65100"),
    "medium": colors.HexColor("#F9A825"),
    "low": colors.HexColor("#1565C0"),
    "info": colors.HexColor("#607D8B"),
}
SEV_ORDER = ["critical", "high", "medium", "low", "info"]

# Subdomain tokens that make an asset "higher interest" to an attacker.
INTERESTING_TOKENS = (
    "dev", "staging", "stage", "test", "uat", "internal", "intranet",
    "admin", "vpn", "mail", "webmail", "smtp", "posta", "git", "jenkins",
    "ci", "backup", "old", "legacy", "preview", "sandbox", "demo", "beta",
)

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _s(value: Any, default: str = "—") -> str:
    """Safe string; None/empty -> default."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _fmt_date(value: Any) -> str:
    if not value:
        return "—"
    try:
        return value.strftime("%d %b %Y")
    except Exception:
        return _s(value)


def _sev_value(finding) -> str:
    sev = getattr(finding, "severity", None)
    val = getattr(sev, "value", sev)
    return str(val).lower() if val is not None else "info"


def _clip(text: str, limit: int) -> str:
    text = _s(text, "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _tech_list(value: Any) -> str:
    """Render http_technologies (list) or technologies (json text) compactly."""
    if not value:
        return "—"
    items: List[str] = []
    if isinstance(value, (list, tuple)):
        items = [str(v) for v in value if v]
    elif isinstance(value, str):
        raw = value.strip()
        if raw.startswith("["):
            import json
            try:
                parsed = json.loads(raw)
                items = [str(v) for v in parsed if v]
            except Exception:
                items = [raw]
        elif raw:
            items = [raw]
    if not items:
        return "—"
    joined = ", ".join(items[:4])
    if len(items) > 4:
        joined += f" +{len(items) - 4}"
    return _clip(joined, 60)


def _is_interesting_asset(identifier: str) -> Optional[str]:
    """Return the matched interest token, or None."""
    ident = (identifier or "").lower()
    label = ident.split(".")[0] if "." in ident else ident
    for token in INTERESTING_TOKENS:
        if token in label:
            return token
    return None


# ---------------------------------------------------------------------------
# Custom flowables
# ---------------------------------------------------------------------------
class HRule(Flowable):
    """A colored horizontal rule used as a section underline."""

    def __init__(self, width: float, thickness: float = 2.2, color=ACCENT):
        super().__init__()
        self.width = width
        self.thickness = thickness
        self.color = color

    def wrap(self, aw, ah):
        return self.width, self.thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.thickness / 2.0, self.width, self.thickness / 2.0)


class SeverityBarChart(Flowable):
    """Horizontal proportional bar chart of findings-by-severity."""

    def __init__(self, counts: Dict[str, int], width: float, row_h: float = 15):
        super().__init__()
        self.counts = counts
        self.width = width
        self.row_h = row_h
        self.gap = 7
        self.label_w = 62
        self.value_w = 34
        self._rows = SEV_ORDER
        self.height = len(self._rows) * (self.row_h + self.gap)

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        max_val = max([self.counts.get(s, 0) for s in self._rows] + [1])
        track_w = self.width - self.label_w - self.value_w - 10
        y = self.height - self.row_h
        for sev in self._rows:
            val = self.counts.get(sev, 0)
            color = SEV_COLORS[sev]
            # label
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(0, y + self.row_h / 2 - 3, sev.capitalize())
            # track
            c.setFillColor(colors.HexColor("#EDF1F5"))
            c.roundRect(self.label_w, y, track_w, self.row_h, 3, stroke=0, fill=1)
            # bar
            bar_w = (val / max_val) * track_w if max_val else 0
            if bar_w > 0:
                c.setFillColor(color)
                c.roundRect(self.label_w, y, max(bar_w, 3), self.row_h, 3, stroke=0, fill=1)
            # value
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawRightString(self.width, y + self.row_h / 2 - 3, str(val))
            y -= (self.row_h + self.gap)


# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------
def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: Dict[str, ParagraphStyle] = {}

    s["h1"] = ParagraphStyle(
        "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
        fontSize=17, leading=21, textColor=PRIMARY, spaceBefore=2, spaceAfter=2,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=16, textColor=PRIMARY, spaceBefore=12, spaceAfter=4,
    )
    s["kicker"] = ParagraphStyle(
        "kicker", fontName="Helvetica-Bold", fontSize=8, leading=10,
        textColor=ACCENT, spaceAfter=1, tracking=1,
    )
    s["body"] = ParagraphStyle(
        "body", parent=base["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=14, textColor=INK, spaceAfter=6,
    )
    s["muted"] = ParagraphStyle(
        "muted", fontName="Helvetica", fontSize=8.5, leading=12, textColor=MUTED,
    )
    s["cell"] = ParagraphStyle(
        "cell", fontName="Helvetica", fontSize=8, leading=10.5, textColor=INK,
    )
    s["cell_r"] = ParagraphStyle(
        "cell_r", parent=s["cell"], alignment=TA_RIGHT,
    )
    s["cell_head"] = ParagraphStyle(
        "cell_head", fontName="Helvetica-Bold", fontSize=8, leading=10.5,
        textColor=LIGHT,
    )
    s["cell_head_r"] = ParagraphStyle(
        "cell_head_r", parent=s["cell_head"], alignment=TA_RIGHT,
    )
    s["finding_name"] = ParagraphStyle(
        "finding_name", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK,
    )
    s["reco"] = ParagraphStyle(
        "reco", fontName="Helvetica", fontSize=9.3, leading=13.5, textColor=INK,
        spaceAfter=7, leftIndent=2,
    )
    # cover styles
    s["cover_title"] = ParagraphStyle(
        "cover_title", fontName="Helvetica-Bold", fontSize=32, leading=37,
        textColor=LIGHT,
    )
    s["cover_sub"] = ParagraphStyle(
        "cover_sub", fontName="Helvetica", fontSize=13, leading=18,
        textColor=colors.HexColor("#C7D6E2"),
    )
    s["cover_client"] = ParagraphStyle(
        "cover_client", fontName="Helvetica-Bold", fontSize=22, leading=26,
        textColor=ACCENT,
    )
    s["cover_meta"] = ParagraphStyle(
        "cover_meta", fontName="Helvetica", fontSize=10.5, leading=16,
        textColor=colors.HexColor("#AEC0CE"),
    )
    s["cover_meta_v"] = ParagraphStyle(
        "cover_meta_v", fontName="Helvetica-Bold", fontSize=10.5, leading=16,
        textColor=LIGHT,
    )
    return s


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------
def _collect(db, tenant_id: int) -> Dict[str, Any]:
    """Gather everything the report needs, defensively."""
    asset_repo = AssetRepository(db)
    svc_repo = ServiceRepository(db)
    cert_repo = CertificateRepository(db)
    ep_repo = EndpointRepository(db)
    find_repo = FindingRepository(db)

    assets = asset_repo.get_by_tenant(tenant_id, is_active=True, limit=2000) or []

    # Services across all assets (join by tenant).
    services: List[Service] = (
        db.query(Service).join(Asset).filter(Asset.tenant_id == tenant_id)
        .order_by(Asset.identifier, Service.port).all()
    )

    finding_stats = find_repo.get_finding_stats(tenant_id, days=0) or {}
    findings = find_repo.get_findings(tenant_id, limit=2000) or []
    cert_stats = cert_repo.get_certificate_stats(tenant_id) or {}
    ep_stats = ep_repo.get_endpoint_stats(tenant_id) or {}

    # Certificates for the whole tenant (order by expiry).
    from app.models.enrichment import Certificate, Endpoint
    certs = (
        db.query(Certificate).join(Asset).filter(Asset.tenant_id == tenant_id)
        .order_by(Certificate.not_after).all()
    )
    endpoints_all = (
        db.query(Endpoint).join(Asset).filter(Asset.tenant_id == tenant_id).all()
    )
    api_endpoints = ep_repo.get_api_endpoints(tenant_id, limit=2000) or []
    sensitive_endpoints = ep_repo.get_sensitive_endpoints(tenant_id, limit=2000) or []
    expiring = cert_repo.get_expiring_soon(tenant_id, days_threshold=30, limit=500) or []

    by_sev = finding_stats.get("by_severity") or {s: 0 for s in SEV_ORDER}

    return {
        "assets": assets,
        "services": services,
        "findings": findings,
        "finding_stats": finding_stats,
        "by_sev": by_sev,
        "cert_stats": cert_stats,
        "certs": certs,
        "ep_stats": ep_stats,
        "endpoints_all": endpoints_all,
        "api_endpoints": api_endpoints,
        "sensitive_endpoints": sensitive_endpoints,
        "expiring": expiring,
    }


def _risk_posture(data: Dict[str, Any]) -> Tuple[str, colors.Color]:
    """Derive an overall risk posture from findings + asset risk scores."""
    by_sev = data["by_sev"]
    if by_sev.get("critical", 0) > 0:
        return "Critical", SEV_COLORS["critical"]
    if by_sev.get("high", 0) > 0:
        return "High", SEV_COLORS["high"]
    max_risk = max([getattr(a, "risk_score", 0.0) or 0.0 for a in data["assets"]] + [0.0])
    if by_sev.get("medium", 0) > 0 or max_risk >= 50:
        return "Medium", SEV_COLORS["medium"]
    if by_sev.get("low", 0) > 0 or by_sev.get("info", 0) > 0 or max_risk >= 20:
        return "Low", SEV_COLORS["low"]
    return "Low", SEV_COLORS["low"]


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def _section_header(story: List, st: Dict, kicker: str, title: str, content_w: float):
    story.append(Spacer(1, 2))
    story.append(Paragraph(kicker.upper(), st["kicker"]))
    story.append(Paragraph(title, st["h1"]))
    story.append(HRule(content_w, thickness=2.2, color=ACCENT))
    story.append(Spacer(1, 8))


def _sev_chip(sev: str, st: Dict) -> Table:
    """A small colored severity chip as a one-cell table."""
    color = SEV_COLORS.get(sev, MUTED)
    p = Paragraph(
        f'<font color="#FFFFFF"><b>{sev.upper()}</b></font>',
        ParagraphStyle("chip", fontName="Helvetica-Bold", fontSize=7, leading=9,
                       alignment=TA_CENTER, textColor=LIGHT),
    )
    t = Table([[p]], colWidths=[52], rowHeights=[13])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]))
    return t


def _std_table_style(ncols: int) -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), LIGHT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT, ZEBRA]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, PRIMARY),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, HAIRLINE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, HAIRLINE),
    ])


def _empty_note(story: List, st: Dict, text: str):
    box = Table([[Paragraph(text, st["muted"])]], colWidths=[PAGE_W - 2 * MARGIN])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(box)


# --- Executive summary ------------------------------------------------------
def _kpi_cards(data: Dict, content_w: float, st: Dict) -> Table:
    posture, posture_color = _risk_posture(data)
    n_assets = len(data["assets"])
    n_services = len(data["services"])
    n_open_ports = len({(s.asset_id, s.port) for s in data["services"] if s.port})
    n_certs = data["cert_stats"].get("total", 0)
    n_endpoints = data["ep_stats"].get("total", 0)
    n_findings = data["finding_stats"].get("total", 0)

    cards = [
        ("ASSETS", str(n_assets), PRIMARY),
        ("OPEN PORTS", str(n_open_ports), PRIMARY),
        ("CERTIFICATES", str(n_certs), PRIMARY),
        ("ENDPOINTS", str(n_endpoints), PRIMARY),
        ("FINDINGS", str(n_findings), PRIMARY),
        ("RISK POSTURE", posture.upper(), posture_color),
    ]

    def card_cell(label, value, accent):
        val_style = ParagraphStyle(
            "kpi_val", fontName="Helvetica-Bold", fontSize=19, leading=22,
            textColor=accent, alignment=TA_LEFT,
        )
        lab_style = ParagraphStyle(
            "kpi_lab", fontName="Helvetica-Bold", fontSize=7, leading=9,
            textColor=MUTED, alignment=TA_LEFT,
        )
        inner = Table(
            [[Paragraph(value, val_style)], [Paragraph(label, lab_style)]],
            colWidths=[content_w / 6 - 6],
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, accent),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        return inner

    row = [card_cell(l, v, a) for (l, v, a) in cards]
    grid = Table([row], colWidths=[content_w / 6] * 6)
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return grid


def _build_exec_summary(story, data, content_w, st, client_name):
    _section_header(story, st, "Section 01", "Executive Summary", content_w)

    posture, _ = _risk_posture(data)
    n_assets = len(data["assets"])
    n_services = len(data["services"])
    n_findings = data["finding_stats"].get("total", 0)
    by_sev = data["by_sev"]
    crit_high = by_sev.get("critical", 0) + by_sev.get("high", 0)
    n_interesting = sum(1 for a in data["assets"]
                        if _is_interesting_asset(getattr(a, "identifier", "")))
    expiring = len(data["expiring"])

    if n_findings == 0:
        finding_sentence = (
            "Automated vulnerability scanning did not surface any confirmed "
            "findings across the assessed surface at the time of reporting."
        )
    else:
        finding_sentence = (
            f"Automated scanning identified <b>{n_findings}</b> finding(s), including "
            f"<b>{crit_high}</b> of critical or high severity that warrant prioritised "
            f"remediation."
        )

    para = (
        f"This report presents the results of an external attack surface assessment "
        f"conducted for <b>{client_name}</b>. Using passive and active discovery, the "
        f"engagement mapped <b>{n_assets}</b> internet-facing asset(s) and enumerated "
        f"<b>{n_services}</b> exposed network service(s). {finding_sentence} "
        f"Of the discovered hosts, <b>{n_interesting}</b> exhibit naming patterns "
        f"(development, internal, mail or staging) that typically merit tighter access "
        f"controls. The overall risk posture of the external estate is assessed as "
        f"<b>{posture.upper()}</b>."
    )
    story.append(Paragraph(para, st["body"]))
    story.append(Spacer(1, 10))
    story.append(_kpi_cards(data, content_w, st))
    story.append(Spacer(1, 6))

    # Small callouts row
    notes = []
    if expiring:
        notes.append(f"{expiring} certificate(s) expiring within 30 days")
    if data["cert_stats"].get("self_signed", 0):
        notes.append(f"{data['cert_stats']['self_signed']} self-signed certificate(s)")
    if data["ep_stats"].get("api_endpoints", 0):
        notes.append(f"{data['ep_stats']['api_endpoints']} API endpoint(s) discovered")
    if n_interesting:
        notes.append(f"{n_interesting} high-interest subdomain(s)")
    if notes:
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "<b>Key observations:</b> " + "  •  ".join(notes), st["muted"]))


# --- Risk overview ----------------------------------------------------------
def _build_risk_overview(story, data, content_w, st):
    _section_header(story, st, "Section 02", "Risk Overview", content_w)
    by_sev = data["by_sev"]
    total = data["finding_stats"].get("total", 0)

    story.append(Paragraph(
        "The distribution below summarises confirmed findings by severity. Severities "
        "follow the CVSS-aligned scale used throughout this report.", st["body"]))

    left_w = content_w * 0.50
    right_w = content_w * 0.50

    # Table of counts (sized to fit the left column)
    header = [Paragraph("Severity", st["cell_head"]),
              Paragraph("Findings", st["cell_head_r"]),
              Paragraph("Share", st["cell_head_r"])]
    rows = [header]
    for sev in SEV_ORDER:
        cnt = by_sev.get(sev, 0)
        share = f"{(cnt / total * 100):.0f}%" if total else "0%"
        chip = _sev_chip(sev, st)
        rows.append([chip,
                     Paragraph(str(cnt), st["cell_r"]),
                     Paragraph(share, st["cell_r"])])
    rows.append([Paragraph("<b>Total</b>", st["cell"]),
                 Paragraph(f"<b>{total}</b>", st["cell_r"]),
                 Paragraph("<b>100%</b>" if total else "—", st["cell_r"])])

    inner_w = left_w - 10
    tbl = Table(rows, colWidths=[inner_w * 0.5, inner_w * 0.28, inner_w * 0.22])
    tstyle = _std_table_style(3)
    tstyle.add("BACKGROUND", (0, -1), (-1, -1), CARD_BG)
    tstyle.add("LINEABOVE", (0, -1), (-1, -1), 0.8, PRIMARY)
    tbl.setStyle(tstyle)

    chart = SeverityBarChart(by_sev, right_w - 8)
    two = Table([[tbl, chart]], colWidths=[left_w, right_w])
    two.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(two)


# --- Attack surface inventory ----------------------------------------------
def _build_inventory(story, data, content_w, st):
    _section_header(story, st, "Section 03", "Attack Surface Inventory", content_w)
    assets = sorted(
        data["assets"],
        key=lambda a: (getattr(a, "risk_score", 0.0) or 0.0),
        reverse=True,
    )

    story.append(Paragraph(
        "Discovered internet-facing assets attributed to the organisation. Hosts flagged "
        "as <b>high-interest</b> (development, internal, staging or mail infrastructure) "
        "are typically exposed unintentionally and should be reviewed first.", st["body"]))

    if not assets:
        _empty_note(story, st, "No active assets were discovered for this tenant.")
    else:
        header = [Paragraph("Host / Identifier", st["cell_head"]),
                  Paragraph("Type", st["cell_head"]),
                  Paragraph("Interest", st["cell_head"]),
                  Paragraph("Risk", st["cell_head_r"]),
                  Paragraph("Enrichment", st["cell_head"]),
                  Paragraph("First Seen", st["cell_head"])]
        rows = [header]
        highlight_rows = []
        for i, a in enumerate(assets, start=1):
            ident = _s(getattr(a, "identifier", ""))
            token = _is_interesting_asset(ident)
            atype = getattr(getattr(a, "type", None), "value", "—")
            risk = getattr(a, "risk_score", 0.0) or 0.0
            interest = (f'<font color="#E65100"><b>{token}</b></font>'
                        if token else "—")
            rows.append([
                Paragraph(_clip(ident, 46), st["cell"]),
                Paragraph(_s(atype), st["cell"]),
                Paragraph(interest, st["cell"]),
                Paragraph(f"{risk:.0f}", st["cell_r"]),
                Paragraph(_s(getattr(a, "enrichment_status", None)), st["cell"]),
                Paragraph(_fmt_date(getattr(a, "first_seen", None)), st["cell"]),
            ])
            if token:
                highlight_rows.append(i)

        widths = [content_w * x for x in (0.34, 0.12, 0.12, 0.09, 0.16, 0.17)]
        tbl = Table(rows, colWidths=widths, repeatRows=1)
        tstyle = _std_table_style(6)
        for r in highlight_rows:
            tstyle.add("BACKGROUND", (0, r), (-1, r), colors.HexColor("#FFF3E6"))
        tbl.setStyle(tstyle)
        story.append(tbl)

    # Services / open ports
    story.append(Spacer(1, 4))
    story.append(Paragraph("Exposed Services &amp; Open Ports", st["h2"]))
    story.append(HRule(content_w, thickness=1.2, color=HAIRLINE))
    story.append(Spacer(1, 6))

    services = data["services"]
    if not services:
        _empty_note(story, st, "No open ports or services were observed on the assessed hosts.")
    else:
        header = [Paragraph("Host", st["cell_head"]),
                  Paragraph("Port", st["cell_head_r"]),
                  Paragraph("Proto", st["cell_head"]),
                  Paragraph("Server / Product", st["cell_head"]),
                  Paragraph("Technologies", st["cell_head"]),
                  Paragraph("HTTP", st["cell_head_r"]),
                  Paragraph("TLS", st["cell_head"])]
        rows = [header]
        shown = services[:40]
        for s in shown:
            host = _s(getattr(getattr(s, "asset", None), "identifier", None))
            server = _s(getattr(s, "web_server", None) or getattr(s, "product", None))
            tech = _tech_list(getattr(s, "http_technologies", None)
                              or getattr(s, "technologies", None))
            http = getattr(s, "http_status", None)
            tls = "Yes" if getattr(s, "has_tls", False) else "—"
            tls_v = getattr(s, "tls_version", None)
            tls_disp = f"{tls}" + (f" ({tls_v})" if tls == "Yes" and tls_v else "")
            rows.append([
                Paragraph(_clip(host, 30), st["cell"]),
                Paragraph(_s(getattr(s, "port", None)), st["cell_r"]),
                Paragraph(_s(getattr(s, "protocol", None)), st["cell"]),
                Paragraph(_clip(server, 24), st["cell"]),
                Paragraph(tech, st["cell"]),
                Paragraph(_s(http), st["cell_r"]),
                Paragraph(tls_disp, st["cell"]),
            ])
        widths = [content_w * x for x in (0.23, 0.07, 0.08, 0.19, 0.24, 0.07, 0.12)]
        tbl = Table(rows, colWidths=widths, repeatRows=1)
        tbl.setStyle(_std_table_style(7))
        story.append(tbl)
        if len(services) > len(shown):
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"…and {len(services) - len(shown)} more service(s) not shown.", st["muted"]))


# --- TLS / certificates -----------------------------------------------------
def _build_certificates(story, data, content_w, st):
    _section_header(story, st, "Section 04", "TLS &amp; Certificates", content_w)
    stats = data["cert_stats"]
    certs = data["certs"]

    story.append(Paragraph(
        f"A total of <b>{stats.get('total', 0)}</b> certificate(s) were observed: "
        f"<b>{stats.get('expiring_soon', 0)}</b> expiring within 30 days, "
        f"<b>{stats.get('expired', 0)}</b> already expired, "
        f"<b>{stats.get('self_signed', 0)}</b> self-signed and "
        f"<b>{stats.get('wildcards', 0)}</b> wildcard. Certificates nearing expiry are "
        f"highlighted and should be renewed to avoid service disruption.", st["body"]))

    if not certs:
        _empty_note(story, st, "No TLS certificates were collected during this assessment.")
        return

    header = [Paragraph("Subject / CN", st["cell_head"]),
              Paragraph("Issuer", st["cell_head"]),
              Paragraph("Expires", st["cell_head"]),
              Paragraph("Days Left", st["cell_head_r"]),
              Paragraph("Flags", st["cell_head"])]
    rows = [header]
    warn_rows = []
    for i, c in enumerate(certs[:40], start=1):
        cn = _s(getattr(c, "subject_cn", None))
        issuer = _clip(_s(getattr(c, "issuer", None)), 30)
        days = getattr(c, "days_until_expiry", None)
        expired = getattr(c, "is_expired", False)
        flags = []
        if getattr(c, "is_wildcard", False):
            flags.append("wildcard")
        if getattr(c, "is_self_signed", False):
            flags.append("self-signed")
        if getattr(c, "has_weak_signature", False):
            flags.append("weak-sig")
        if expired:
            flags.append("EXPIRED")
        days_disp = "expired" if expired else (_s(days) if days is not None else "—")
        rows.append([
            Paragraph(_clip(cn, 34), st["cell"]),
            Paragraph(issuer, st["cell"]),
            Paragraph(_fmt_date(getattr(c, "not_after", None)), st["cell"]),
            Paragraph(days_disp, st["cell_r"]),
            Paragraph(", ".join(flags) if flags else "—", st["cell"]),
        ])
        if expired or (isinstance(days, int) and days < 30):
            warn_rows.append(i)

    widths = [content_w * x for x in (0.30, 0.24, 0.15, 0.12, 0.19)]
    tbl = Table(rows, colWidths=widths, repeatRows=1)
    tstyle = _std_table_style(5)
    for r in warn_rows:
        tstyle.add("BACKGROUND", (0, r), (-1, r), colors.HexColor("#FEF7E6"))
        tstyle.add("TEXTCOLOR", (3, r), (3, r), SEV_COLORS["medium"])
    tbl.setStyle(tstyle)
    story.append(tbl)
    if len(certs) > 40:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"…and {len(certs) - 40} more certificate(s).", st["muted"]))


# --- Endpoints --------------------------------------------------------------
def _build_endpoints(story, data, content_w, st):
    _section_header(story, st, "Section 05", "Discovered Endpoints", content_w)
    stats = data["ep_stats"]
    by_type = stats.get("by_type", {}) or {}

    story.append(Paragraph(
        f"Web crawling discovered <b>{stats.get('total', 0)}</b> endpoint(s), of which "
        f"<b>{stats.get('api_endpoints', 0)}</b> appear to be API endpoints and "
        f"<b>{stats.get('forms', 0)}</b> are forms. API and sensitive endpoints expand "
        f"the exploitable attack surface and should be reviewed for authentication and "
        f"input validation.", st["body"]))

    # Counts-by-type chips row
    if by_type:
        type_cells = []
        for t, cnt in sorted(by_type.items(), key=lambda kv: kv[1], reverse=True):
            type_cells.append(Paragraph(
                f'<font color="#0F2A43"><b>{cnt}</b></font> '
                f'<font color="#5A6B7B">{_s(t)}</font>', st["cell"]))
        if type_cells:
            ncol = min(len(type_cells), 6)
            # pad
            while len(type_cells) % ncol != 0:
                type_cells.append(Paragraph("", st["cell"]))
            grid_rows = [type_cells[i:i + ncol] for i in range(0, len(type_cells), ncol)]
            g = Table(grid_rows, colWidths=[content_w / ncol] * ncol)
            g.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, HAIRLINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, HAIRLINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(g)
            story.append(Spacer(1, 8))

    # Notable endpoints: API + sensitive, de-duplicated
    notable = []
    seen = set()
    for ep in list(data["api_endpoints"]) + list(data["sensitive_endpoints"]):
        key = (getattr(ep, "url", None), getattr(ep, "method", None))
        if key in seen:
            continue
        seen.add(key)
        notable.append(ep)

    if not notable:
        _empty_note(story, st,
                    "No API or sensitive endpoints were identified during crawling.")
        return

    story.append(Paragraph("Notable Endpoints (API &amp; Sensitive)", st["h2"]))
    story.append(HRule(content_w, thickness=1.2, color=HAIRLINE))
    story.append(Spacer(1, 6))

    header = [Paragraph("Method", st["cell_head"]),
              Paragraph("URL", st["cell_head"]),
              Paragraph("Type", st["cell_head"]),
              Paragraph("API", st["cell_head"]),
              Paragraph("Status", st["cell_head_r"])]
    rows = [header]
    shown = notable[:25]
    for ep in shown:
        rows.append([
            Paragraph(_s(getattr(ep, "method", None)), st["cell"]),
            Paragraph(_clip(_s(getattr(ep, "url", None)), 62), st["cell"]),
            Paragraph(_s(getattr(ep, "endpoint_type", None)), st["cell"]),
            Paragraph("Yes" if getattr(ep, "is_api", False) else "—", st["cell"]),
            Paragraph(_s(getattr(ep, "status_code", None)), st["cell_r"]),
        ])
    widths = [content_w * x for x in (0.10, 0.56, 0.13, 0.09, 0.12)]
    tbl = Table(rows, colWidths=widths, repeatRows=1)
    tbl.setStyle(_std_table_style(5))
    story.append(tbl)
    if len(notable) > len(shown):
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"…and {len(notable) - len(shown)} more notable endpoint(s).", st["muted"]))


# --- Findings ---------------------------------------------------------------
def _build_findings(story, data, content_w, st):
    _section_header(story, st, "Section 06", "Findings &amp; Vulnerabilities", content_w)
    findings = data["findings"]
    total = data["finding_stats"].get("total", 0)

    if not findings:
        story.append(Paragraph(
            "No confirmed vulnerabilities were identified across the assessed attack "
            "surface at the time of this report. This is a positive result; however, "
            "attack surface changes continuously and periodic reassessment is "
            "recommended to maintain this posture.", st["body"]))
        _empty_note(story, st, "No open findings — clean result. See recommendations for "
                               "proactive hardening guidance.")
        return

    story.append(Paragraph(
        f"A total of <b>{total}</b> finding(s) are detailed below, grouped by severity "
        f"from most to least critical. Each entry lists the affected host, associated "
        f"CVE or detection template, and CVSS score where available.", st["body"]))
    story.append(Spacer(1, 4))

    # Group by severity
    grouped: Dict[str, List] = {s: [] for s in SEV_ORDER}
    for f in findings:
        grouped.setdefault(_sev_value(f), []).append(f)

    PER_SEV_CAP = 20
    for sev in SEV_ORDER:
        group = grouped.get(sev, [])
        if not group:
            continue
        block = []
        chip = _sev_chip(sev, st)
        heading = Table(
            [[chip, Paragraph(f"<b>{sev.capitalize()} severity</b> "
                              f'<font color="#5A6B7B">({len(group)})</font>',
                              ParagraphStyle("gh", fontName="Helvetica-Bold",
                                             fontSize=10.5, textColor=PRIMARY,
                                             leading=14))]],
            colWidths=[58, content_w - 58])
        heading.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        block.append(heading)

        header = [Paragraph("Finding", st["cell_head"]),
                  Paragraph("Affected Host / URL", st["cell_head"]),
                  Paragraph("CVE / Template", st["cell_head"]),
                  Paragraph("CVSS", st["cell_head_r"])]
        rows = [header]
        for f in group[:PER_SEV_CAP]:
            name = _s(getattr(f, "name", None))
            host = _s(getattr(f, "host", None) or getattr(f, "matched_at", None))
            ref = _s(getattr(f, "cve_id", None) or getattr(f, "template_id", None))
            cvss = getattr(f, "cvss_score", None)
            cvss_disp = f"{cvss:.1f}" if isinstance(cvss, (int, float)) else "—"
            rows.append([
                Paragraph(_clip(name, 52), st["finding_name"]),
                Paragraph(_clip(host, 46), st["cell"]),
                Paragraph(_clip(ref, 30), st["cell"]),
                Paragraph(cvss_disp, st["cell_r"]),
            ])
        widths = [content_w * x for x in (0.36, 0.32, 0.23, 0.09)]
        tbl = Table(rows, colWidths=widths, repeatRows=1)
        tstyle = _std_table_style(4)
        tstyle.add("LINEBEFORE", (0, 1), (0, -1), 2.5, SEV_COLORS[sev])
        tbl.setStyle(tstyle)
        block.append(tbl)
        if len(group) > PER_SEV_CAP:
            block.append(Spacer(1, 3))
            block.append(Paragraph(
                f"…and {len(group) - PER_SEV_CAP} more {sev} finding(s).", st["muted"]))
        block.append(Spacer(1, 8))
        story.append(KeepTogether(block))


# --- Recommendations --------------------------------------------------------
def _build_recommendations(story, data, content_w, st):
    _section_header(story, st, "Section 07", "Recommendations", content_w)
    recos: List[Tuple[str, str]] = []  # (priority_label, text)

    by_sev = data["by_sev"]
    cert_stats = data["cert_stats"]
    ep_stats = data["ep_stats"]

    if by_sev.get("critical", 0):
        recos.append(("CRITICAL",
            f"Immediately remediate the {by_sev['critical']} critical-severity "
            f"finding(s). These represent the highest likelihood of exploitation and "
            f"should be escalated to the responsible owners within 24–48 hours."))
    if by_sev.get("high", 0):
        recos.append(("HIGH",
            f"Prioritise remediation of {by_sev['high']} high-severity finding(s) on a "
            f"short (7–14 day) timeline, applying vendor patches or configuration "
            f"hardening as appropriate."))

    expiring = len(data["expiring"])
    if expiring:
        recos.append(("HIGH",
            f"Renew the {expiring} TLS certificate(s) expiring within 30 days to avoid "
            f"service outages and browser trust warnings. Automate renewal (e.g. ACME) "
            f"where possible."))
    if cert_stats.get("expired", 0):
        recos.append(("HIGH",
            f"Replace {cert_stats['expired']} expired certificate(s); expired TLS "
            f"undermines trust and may break integrations."))
    if cert_stats.get("self_signed", 0):
        recos.append(("MEDIUM",
            f"Review {cert_stats['self_signed']} self-signed certificate(s). Replace "
            f"with CA-issued certificates on production hosts, or restrict the endpoints "
            f"to internal networks."))
    if cert_stats.get("weak_signatures", 0):
        recos.append(("MEDIUM",
            f"Reissue {cert_stats['weak_signatures']} certificate(s) using weak "
            f"signature algorithms (MD5/SHA-1) with modern SHA-256+ signatures."))

    interesting = [a for a in data["assets"]
                   if _is_interesting_asset(getattr(a, "identifier", ""))]
    if interesting:
        names = ", ".join(_s(getattr(a, "identifier", "")) for a in interesting[:5])
        more = f" (and {len(interesting) - 5} more)" if len(interesting) > 5 else ""
        recos.append(("MEDIUM",
            f"Restrict access to {len(interesting)} high-interest host(s) such as "
            f"{names}{more}. Development, staging and internal systems should sit behind "
            f"VPN/IP allow-listing rather than being publicly reachable."))

    # Plaintext / missing TLS on web services
    web_ports = {80, 8080, 8000, 8888}
    plain = [s for s in data["services"]
             if getattr(s, "port", None) in web_ports and not getattr(s, "has_tls", False)]
    if plain:
        recos.append(("MEDIUM",
            f"Enforce HTTPS on {len(plain)} web service(s) currently reachable over "
            f"plaintext HTTP. Redirect HTTP→HTTPS and enable HSTS."))

    if ep_stats.get("api_endpoints", 0):
        recos.append(("MEDIUM",
            f"Audit the {ep_stats['api_endpoints']} discovered API endpoint(s) for "
            f"authentication, authorization and rate-limiting. Ensure no sensitive data "
            f"is exposed without access control."))

    if by_sev.get("medium", 0):
        recos.append(("LOW",
            f"Schedule remediation of {by_sev['medium']} medium-severity finding(s) as "
            f"part of routine maintenance cycles."))

    # Always-on generic hardening advice.
    recos.append(("BASELINE",
        "Minimise the external footprint: decommission unused hosts and services, and "
        "close ports that are not required to be internet-facing."))
    recos.append(("BASELINE",
        "Establish continuous attack surface monitoring so that newly exposed assets, "
        "certificates and services are detected and triaged promptly."))
    recos.append(("BASELINE",
        "Re-run this assessment on a regular cadence (e.g. monthly) and after any major "
        "infrastructure change to validate the security posture over time."))

    prio_color = {
        "CRITICAL": SEV_COLORS["critical"],
        "HIGH": SEV_COLORS["high"],
        "MEDIUM": SEV_COLORS["medium"],
        "LOW": SEV_COLORS["low"],
        "BASELINE": ACCENT,
    }

    story.append(Paragraph(
        "The following actions are prioritised by urgency. Addressing higher-priority "
        "items first will yield the greatest reduction in exposure.", st["body"]))
    story.append(Spacer(1, 4))

    rows = []
    for label, text in recos:
        chip = Paragraph(
            f'<font color="#FFFFFF"><b>{label}</b></font>',
            ParagraphStyle("pchip", fontName="Helvetica-Bold", fontSize=6.7,
                           leading=9, alignment=TA_CENTER, textColor=LIGHT))
        chip_tbl = Table([[chip]], colWidths=[58], rowHeights=[14])
        chip_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), prio_color.get(label, ACCENT)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        rows.append([chip_tbl, Paragraph(text, st["reco"])])

    tbl = Table(rows, colWidths=[66, content_w - 66])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, HAIRLINE),
    ]))
    story.append(tbl)


# ---------------------------------------------------------------------------
# Page furniture (cover band, header, footer)
# ---------------------------------------------------------------------------
class _ReportDoc(BaseDocTemplate):
    def __init__(self, buffer, client_name: str, report_title: str, **kw):
        super().__init__(buffer, pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN + 8 * mm, bottomMargin=MARGIN + 4 * mm, **kw)
        self.client_name = client_name
        self.report_title = report_title
        self._page_count = 0

        content_frame = Frame(
            MARGIN, MARGIN + 4 * mm,
            PAGE_W - 2 * MARGIN, PAGE_H - (MARGIN + 8 * mm) - (MARGIN + 4 * mm),
            id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        cover_frame = Frame(
            MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN,
            id="cover", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

        self.addPageTemplates([
            PageTemplate(id="Cover", frames=[cover_frame], onPage=self._draw_cover),
            PageTemplate(id="Content", frames=[content_frame], onPage=self._draw_furniture),
        ])

    def _draw_cover(self, canvas, doc):
        canvas.saveState()
        # Full navy background
        canvas.setFillColor(PRIMARY_DK)
        canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        # Accent vertical band on the left
        canvas.setFillColor(ACCENT)
        canvas.rect(0, 0, 8 * mm, PAGE_H, stroke=0, fill=1)
        # Subtle top rule
        canvas.setFillColor(PRIMARY)
        canvas.rect(8 * mm, PAGE_H - 46 * mm, PAGE_W, 46 * mm, stroke=0, fill=1)
        # decorative thin accent line
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.4)
        canvas.line(24 * mm, PAGE_H - 120 * mm, 90 * mm, PAGE_H - 120 * mm)
        canvas.restoreState()

    def _draw_furniture(self, canvas, doc):
        canvas.saveState()
        # Header band
        canvas.setFillColor(PRIMARY)
        canvas.rect(0, PAGE_H - 12 * mm, PAGE_W, 12 * mm, stroke=0, fill=1)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - 12.8 * mm, PAGE_W, 0.8 * mm, stroke=0, fill=1)
        canvas.setFillColor(LIGHT)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawString(MARGIN, PAGE_H - 8 * mm, "EXTERNAL ATTACK SURFACE ASSESSMENT")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#C7D6E2"))
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 8 * mm, self.client_name)

        # Footer
        canvas.setStrokeColor(HAIRLINE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 8 * mm, f"CONFIDENTIAL — {self.client_name}")
        canvas.drawCentredString(PAGE_W / 2, 8 * mm, self.report_title)
        page_num = canvas.getPageNumber()
        canvas.drawRightString(
            PAGE_W - MARGIN, 8 * mm,
            f"Page {page_num} of {self._page_count}" if self._page_count
            else f"Page {page_num}")
        canvas.restoreState()

    def build(self, flowables):
        # Two-pass build to know the total page count for "Page X of Y".
        self._page_count = 0
        import copy
        # First pass: count pages on a throwaway buffer.
        counter = _PageCounter(io.BytesIO(), self.client_name, self.report_title)
        counter.addPageTemplates(self.pageTemplates)
        try:
            counter.build(copy.deepcopy(flowables))
            self._page_count = counter.total_pages
        except Exception:
            self._page_count = 0
        super().build(flowables)


class _PageCounter(BaseDocTemplate):
    """Lightweight first pass that only counts total pages."""

    def __init__(self, buffer, client_name, report_title):
        super().__init__(buffer, pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN + 8 * mm, bottomMargin=MARGIN + 4 * mm)
        self.total_pages = 0

    def afterPage(self):
        self.total_pages += 1


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def generate_scan_report(db, tenant_id: int, prepared_by: str = "Security Team") -> bytes:
    """
    Generate the client-facing External Attack Surface Assessment PDF.

    Args:
        db: SQLAlchemy session.
        tenant_id: Tenant primary key.
        prepared_by: Name shown in the "Prepared by" field on the cover.

    Returns:
        The rendered PDF document as bytes.
    """
    from app.models.database import Tenant

    st = _styles()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    client_name = _s(getattr(tenant, "name", None), f"Tenant {tenant_id}")
    report_title = "External Attack Surface Assessment"
    report_date = datetime.utcnow().strftime("%d %B %Y")

    data = _collect(db, tenant_id)
    content_w = PAGE_W - 2 * MARGIN

    buf = io.BytesIO()
    doc = _ReportDoc(buf, client_name=client_name, report_title=report_title)

    story: List = []

    # ---- Cover page (rendered inside the Cover frame) ----
    story.append(NextPageTemplate("Content"))
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("SECURITY ASSESSMENT REPORT",
                           ParagraphStyle("cover_kicker", fontName="Helvetica-Bold",
                                          fontSize=11, textColor=ACCENT, leading=14)))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("External Attack<br/>Surface Assessment", st["cover_title"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("PREPARED FOR", st["cover_meta"]))
    story.append(Paragraph(client_name, st["cover_client"]))
    story.append(Spacer(1, 30 * mm))

    posture, posture_color = _risk_posture(data)
    meta_rows = [
        [Paragraph("Report date", st["cover_meta"]), Paragraph(report_date, st["cover_meta_v"])],
        [Paragraph("Prepared by", st["cover_meta"]), Paragraph(_s(prepared_by), st["cover_meta_v"])],
        [Paragraph("Assets assessed", st["cover_meta"]),
         Paragraph(str(len(data["assets"])), st["cover_meta_v"])],
        [Paragraph("Overall risk posture", st["cover_meta"]),
         Paragraph(f'<b>{posture.upper()}</b>',
                   ParagraphStyle("cp", fontName="Helvetica-Bold", fontSize=10.5,
                                  textColor=posture_color, leading=16))],
    ]
    meta_tbl = Table(meta_rows, colWidths=[42 * mm, 80 * mm])
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#2A4763")),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 22 * mm))

    # CONFIDENTIAL marker
    conf = Table([[Paragraph(
        '<font color="#FFFFFF"><b>CONFIDENTIAL</b></font>',
        ParagraphStyle("conf", fontName="Helvetica-Bold", fontSize=9,
                       alignment=TA_CENTER, textColor=LIGHT))]],
        colWidths=[42 * mm], rowHeights=[9 * mm])
    conf.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SEV_COLORS["critical"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(conf)
    story.append(Paragraph(
        "This document contains confidential information intended solely for the named "
        "recipient. Do not distribute without authorisation.",
        ParagraphStyle("conf_note", fontName="Helvetica", fontSize=7.5,
                       textColor=colors.HexColor("#8AA0B2"), leading=11, spaceBefore=6)))

    story.append(PageBreak())

    # ---- Content sections ----
    _build_exec_summary(story, data, content_w, st, client_name)
    story.append(PageBreak())
    _build_risk_overview(story, data, content_w, st)
    story.append(PageBreak())
    _build_inventory(story, data, content_w, st)
    story.append(PageBreak())
    _build_certificates(story, data, content_w, st)
    story.append(PageBreak())
    _build_endpoints(story, data, content_w, st)
    story.append(PageBreak())
    _build_findings(story, data, content_w, st)
    story.append(PageBreak())
    _build_recommendations(story, data, content_w, st)

    doc.build(story)
    return buf.getvalue()
