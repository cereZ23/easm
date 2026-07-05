"""
Alerting tasks.

Delivers notifications for newly discovered critical/high findings and newly
discovered assets, using the channels configured in settings (generic webhook
and/or Slack). Runs are windowed (``alert_lookback_hours``) and intended to be
scheduled on Celery Beat at roughly the same cadence as the window so each
finding/asset is alerted once.

Delivery is best-effort per channel (see app.utils.notifications).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.celery_app import celery
from app.config import settings
from app.utils.logger import TenantLoggerAdapter
from app.utils.notifications import Notifier, severity_at_least

logger = logging.getLogger(__name__)


@celery.task(name='app.tasks.alerting.send_critical_alerts')
def send_critical_alerts(tenant_id: int, since_hours: Optional[int] = None):
    """
    Alert on new findings at/above the configured minimum severity.

    Args:
        tenant_id: Tenant ID
        since_hours: Look-back window (defaults to settings.alert_lookback_hours)

    Returns:
        Dict with alert delivery summary
    """
    from app.database import SessionLocal
    from app.repositories.finding_repository import FindingRepository

    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})
    notifier = Notifier()

    if not notifier.is_enabled():
        return {'status': 'disabled', 'findings_alerted': 0}

    lookback = since_hours if since_hours is not None else settings.alert_lookback_hours
    db = SessionLocal()

    try:
        finding_repo = FindingRepository(db)
        findings = finding_repo.get_new_findings(tenant_id, since_hours=lookback)

        # Filter to at/above the configured severity threshold
        alertable = [
            f for f in findings
            if severity_at_least(f.severity.value, settings.alert_min_severity)
        ]

        if not alertable:
            return {'status': 'no_findings', 'findings_alerted': 0}

        # Build the message (cap the detail list to keep payloads reasonable)
        by_sev = {}
        for f in alertable:
            by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
        summary = ', '.join(f"{n} {sev}" for sev, n in sorted(by_sev.items()))

        lines = [
            f"{len(alertable)} new finding(s) in the last {lookback}h: {summary}",
            "",
        ]
        for f in alertable[:20]:
            host = f.host or (f.matched_at or '')
            lines.append(f"[{f.severity.value.upper()}] {f.name} — {host}")
        if len(alertable) > 20:
            lines.append(f"...and {len(alertable) - 20} more")

        payload = {
            'tenant_id': tenant_id,
            'window_hours': lookback,
            'counts_by_severity': by_sev,
            'findings': [
                {
                    'name': f.name,
                    'severity': f.severity.value,
                    'template_id': f.template_id,
                    'cve_id': f.cve_id,
                    'host': f.host,
                    'matched_at': f.matched_at,
                }
                for f in alertable[:50]
            ],
        }

        result = notifier.send(
            title=f"EASM: {len(alertable)} new finding(s) for tenant {tenant_id}",
            text='\n'.join(lines),
            payload=payload,
        )

        tenant_logger.info(
            f"Critical alerts: {len(alertable)} findings, "
            f"delivered={result['delivered']} failed={result['failed']}"
        )

        return {
            'status': 'sent' if result['delivered'] else 'delivery_failed',
            'findings_alerted': len(alertable),
            'delivered': result['delivered'],
            'failed': result['failed'],
        }

    except Exception as e:
        tenant_logger.error(f"send_critical_alerts failed: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e), 'findings_alerted': 0}
    finally:
        db.close()


@celery.task(name='app.tasks.alerting.send_new_asset_alerts')
def send_new_asset_alerts(tenant_id: int, since_hours: Optional[int] = None):
    """
    Alert on assets first discovered within the look-back window.

    Args:
        tenant_id: Tenant ID
        since_hours: Look-back window (defaults to settings.alert_lookback_hours)

    Returns:
        Dict with alert delivery summary
    """
    from app.database import SessionLocal
    from app.models.database import Asset

    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})
    notifier = Notifier()

    if not notifier.is_enabled():
        return {'status': 'disabled', 'assets_alerted': 0}

    lookback = since_hours if since_hours is not None else settings.alert_lookback_hours
    cutoff = datetime.utcnow() - timedelta(hours=lookback)
    db = SessionLocal()

    try:
        new_assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.first_seen >= cutoff,
            Asset.is_active == True,
        ).order_by(Asset.first_seen.desc()).all()

        if not new_assets:
            return {'status': 'no_assets', 'assets_alerted': 0}

        lines = [f"{len(new_assets)} new asset(s) discovered in the last {lookback}h:", ""]
        for a in new_assets[:25]:
            lines.append(f"- {a.type.value}: {a.identifier}")
        if len(new_assets) > 25:
            lines.append(f"...and {len(new_assets) - 25} more")

        payload = {
            'tenant_id': tenant_id,
            'window_hours': lookback,
            'assets': [
                {'type': a.type.value, 'identifier': a.identifier}
                for a in new_assets[:100]
            ],
        }

        result = notifier.send(
            title=f"EASM: {len(new_assets)} new asset(s) for tenant {tenant_id}",
            text='\n'.join(lines),
            payload=payload,
        )

        tenant_logger.info(
            f"New-asset alerts: {len(new_assets)} assets, "
            f"delivered={result['delivered']} failed={result['failed']}"
        )

        return {
            'status': 'sent' if result['delivered'] else 'delivery_failed',
            'assets_alerted': len(new_assets),
            'delivered': result['delivered'],
            'failed': result['failed'],
        }

    except Exception as e:
        tenant_logger.error(f"send_new_asset_alerts failed: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e), 'assets_alerted': 0}
    finally:
        db.close()


@celery.task(name='app.tasks.alerting.dispatch_alerts')
def dispatch_alerts():
    """
    Fan out alert tasks for every tenant. Scheduled on Celery Beat.

    Skips all work when notifications are disabled so it is cheap to schedule.
    """
    if not settings.feature_notifications_enabled:
        return {'status': 'disabled', 'tenants': 0}

    from app.database import SessionLocal
    from app.models.database import Tenant

    db = SessionLocal()
    try:
        tenant_ids = [t.id for t in db.query(Tenant.id).all()]
    finally:
        db.close()

    for tenant_id in tenant_ids:
        send_critical_alerts.delay(tenant_id)
        send_new_asset_alerts.delay(tenant_id)

    return {'status': 'dispatched', 'tenants': len(tenant_ids)}
