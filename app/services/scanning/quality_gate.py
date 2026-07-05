"""
Scan quality gate.

The recurring failure mode of this platform is a tool that *runs* and reports
``status: success`` but silently produces nothing (a bad argument, a stubbed
persistence path, a flaky TLS connect, an empty template dir). Those zeros only
get noticed at report time, in front of the client.

This module turns "impossible" results into loud, immediate failures. After a
scan it inspects the persisted state (and the per-tool result dicts, if given)
and asserts sanity invariants — e.g. *"there are live HTTPS services but zero
certificates, so tlsx must have failed"*. It returns a structured verdict
(pass / warn / fail) with a reason per check, so callers can retry, alert, or
block a report from going out on degraded data.
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import func

from app.models.database import Asset, AssetType, Service, Finding
from app.models.enrichment import Certificate, Endpoint

logger = logging.getLogger(__name__)

PASS = "pass"
WARN = "warn"
FAIL = "fail"

# Severity ordering for the overall verdict (worst wins)
_ORDER = {PASS: 0, WARN: 1, FAIL: 2}


class Check:
    def __init__(self, name: str, status: str, detail: str, expected=None, actual=None):
        self.name = name
        self.status = status
        self.detail = detail
        self.expected = expected
        self.actual = actual

    def as_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "expected": self.expected,
            "actual": self.actual,
        }


def evaluate_scan_quality(
    db,
    tenant_id: int,
    tool_results: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """Run sanity checks over a tenant's scan output.

    Args:
        db: SQLAlchemy session
        tenant_id: tenant to evaluate
        tool_results: optional {tool_name: result_dict} from the scan tasks
            (httpx, naabu, tlsx, katana, nuclei). Enables checks that the DB
            state alone can't make (e.g. did nuclei actually scan any targets).

    Returns:
        {
          'overall': 'pass'|'warn'|'fail',
          'checks': [ {name,status,detail,expected,actual}, ... ],
          'failures': [names],
          'warnings': [names],
          'summary': str,
        }
    """
    tool_results = tool_results or {}
    checks: List[Check] = []

    # --- counts from the DB -------------------------------------------------
    def _count(model):
        return (
            db.query(func.count(model.id))
            .join(Asset, model.asset_id == Asset.id)
            .filter(Asset.tenant_id == tenant_id)
            .scalar()
            or 0
        )

    asset_count = (
        db.query(func.count(Asset.id)).filter(Asset.tenant_id == tenant_id).scalar() or 0
    )
    web_hosts = (
        db.query(func.count(func.distinct(Asset.id)))
        .filter(Asset.tenant_id == tenant_id, Asset.type.in_([AssetType.DOMAIN, AssetType.SUBDOMAIN]))
        .scalar()
        or 0
    )
    service_count = _count(Service)
    # HTTPS-capable services: TLS flag set OR a standard TLS port
    https_service_count = (
        db.query(func.count(Service.id))
        .join(Asset, Service.asset_id == Asset.id)
        .filter(
            Asset.tenant_id == tenant_id,
            (Service.has_tls.is_(True)) | (Service.port.in_([443, 8443])),
        )
        .scalar()
        or 0
    )
    live_service_count = (
        db.query(func.count(Service.id))
        .join(Asset, Service.asset_id == Asset.id)
        .filter(Asset.tenant_id == tenant_id, Service.http_status.isnot(None))
        .scalar()
        or 0
    )
    cert_count = _count(Certificate)
    endpoint_count = _count(Endpoint)
    finding_count = _count(Finding)

    # --- helper to read a tool result --------------------------------------
    def _tool(name):
        return tool_results.get(name) or {}

    def _tool_errored(name):
        r = _tool(name)
        return bool(r.get("error")) or r.get("status") in ("failed", "error", "not_implemented")

    # --- 1. Discovery -------------------------------------------------------
    if asset_count == 0:
        checks.append(Check("discovery", FAIL, "No assets discovered — discovery produced nothing.", ">0", 0))
    else:
        checks.append(Check("discovery", PASS, f"{asset_count} assets discovered.", ">0", asset_count))

    # --- 2. HTTP probe (httpx) ---------------------------------------------
    if _tool_errored("httpx"):
        checks.append(Check("http_probe", FAIL, f"httpx reported an error: {_tool('httpx')}", None, None))
    elif web_hosts > 0 and live_service_count == 0:
        checks.append(Check(
            "http_probe", FAIL,
            f"{web_hosts} web hosts but 0 live HTTP services — httpx likely failed "
            f"(or every host is down).", ">0", 0,
        ))
    else:
        checks.append(Check("http_probe", PASS, f"{live_service_count} live HTTP services.", ">0", live_service_count))

    # --- 3. Port scan (naabu) ----------------------------------------------
    if _tool_errored("naabu"):
        checks.append(Check("port_scan", FAIL, f"naabu reported an error: {_tool('naabu')}", None, None))
    elif web_hosts > 0 and service_count == 0:
        checks.append(Check(
            "port_scan", FAIL,
            f"{web_hosts} live hosts but 0 services/ports recorded — naabu likely failed.",
            ">0", 0,
        ))
    else:
        naabu_ports = _tool("naabu").get("ports_discovered")
        detail = f"{service_count} services recorded"
        if naabu_ports is not None:
            detail += f" (naabu found {naabu_ports} ports)"
        checks.append(Check("port_scan", PASS, detail + ".", ">0", service_count))

    # --- 4. TLS / certificates (tlsx) — the flaky one ----------------------
    if _tool_errored("tlsx"):
        checks.append(Check("tls_certs", FAIL, f"tlsx reported an error: {_tool('tlsx')}", None, None))
    elif https_service_count > 0 and cert_count == 0:
        checks.append(Check(
            "tls_certs", FAIL,
            f"{https_service_count} HTTPS services but 0 certificates — tlsx failed "
            f"(impossible for live HTTPS hosts to have no cert).", ">0", 0,
        ))
    elif https_service_count > 0 and cert_count < max(1, https_service_count // 2):
        checks.append(Check(
            "tls_certs", WARN,
            f"Only {cert_count} certs for {https_service_count} HTTPS services — "
            f"tlsx may have partially failed.", f">= {https_service_count//2}", cert_count,
        ))
    else:
        checks.append(Check("tls_certs", PASS, f"{cert_count} certificates captured.", ">0", cert_count))

    # --- 5. Crawl / endpoints (katana) -------------------------------------
    if _tool_errored("katana"):
        checks.append(Check("crawl", FAIL, f"katana reported an error: {_tool('katana')}", None, None))
    elif live_service_count > 0 and endpoint_count == 0:
        checks.append(Check(
            "crawl", WARN,
            f"{live_service_count} live services but 0 endpoints — katana found nothing "
            f"(possible for a bare host, but check).", ">0", 0,
        ))
    else:
        checks.append(Check("crawl", PASS, f"{endpoint_count} endpoints discovered.", ">=0", endpoint_count))

    # --- 6. Vulnerability scan (nuclei) ------------------------------------
    nuclei = _tool("nuclei")
    if nuclei:
        if _tool_errored("nuclei"):
            checks.append(Check("vuln_scan", FAIL, f"nuclei reported an error: {nuclei}", None, None))
        elif nuclei.get("urls_scanned", 0) == 0 and live_service_count > 0:
            checks.append(Check(
                "vuln_scan", FAIL,
                "nuclei scanned 0 URLs despite live services — template dir or target "
                "selection failed.", ">0", 0,
            ))
        else:
            scanned = nuclei.get("urls_scanned", "?")
            detail = f"nuclei scanned {scanned} URLs, {finding_count} findings stored."
            # 0 findings is allowed, but flag it as info-worthy on a real surface
            status = PASS if finding_count > 0 or (isinstance(scanned, int) and scanned > 0) else WARN
            checks.append(Check("vuln_scan", status, detail, None, finding_count))
    else:
        checks.append(Check("vuln_scan", WARN, "No nuclei result supplied — cannot confirm it ran.", None, None))

    # --- overall verdict ----------------------------------------------------
    overall = PASS
    for c in checks:
        if _ORDER[c.status] > _ORDER[overall]:
            overall = c.status

    failures = [c.name for c in checks if c.status == FAIL]
    warnings = [c.name for c in checks if c.status == WARN]

    if overall == FAIL:
        summary = f"SCAN DEGRADED — {len(failures)} check(s) failed: {', '.join(failures)}. Do not trust these results / do not report."
    elif overall == WARN:
        summary = f"Scan completed with {len(warnings)} warning(s): {', '.join(warnings)}."
    else:
        summary = "All quality checks passed."

    result = {
        "overall": overall,
        "checks": [c.as_dict() for c in checks],
        "failures": failures,
        "warnings": warnings,
        "summary": summary,
    }

    log = logger.error if overall == FAIL else (logger.warning if overall == WARN else logger.info)
    log(f"[quality-gate] tenant {tenant_id}: {summary}")
    return result


# Tools that are safe to re-run when they return a suspicious zero (idempotent,
# stateless network reads). Used by the orchestrator's retry step.
RETRYABLE_ON_FAIL = {"tls_certs": "tlsx", "port_scan": "naabu", "http_probe": "httpx"}
