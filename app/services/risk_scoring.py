"""
Comprehensive Risk Scoring Engine for EASM Platform

Calculates risk scores for assets based on multiple security factors:
- Vulnerability findings (Nuclei)
- TLS/certificate issues
- Exposed high-risk ports
- Login page exposure
- Asset age (new assets are higher risk)
- Service security posture
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.database import Asset, Service, Finding

logger = logging.getLogger(__name__)


class RiskScoringEngine:
    """
    Comprehensive risk scoring engine for EASM assets

    Score Range: 0.0 to 100.0
    - 0-20: Low Risk (Green)
    - 21-40: Medium Risk (Yellow)
    - 41-70: High Risk (Orange)
    - 71-100: Critical Risk (Red)
    """

    # Finding severity weights
    FINDING_WEIGHTS = {
        'critical': 15.0,
        'high': 10.0,
        'medium': 5.0,
        'low': 2.0,
        'info': 0.5
    }

    # Risk modifiers
    NEW_ASSET_BONUS = 10.0  # Asset discovered in last 7 days
    EXPIRED_CERT_PENALTY = 15.0
    EXPIRING_CERT_PENALTY = 8.0  # < 30 days
    CERT_MISMATCH_PENALTY = 12.0
    LOGIN_PAGE_EXPOSED = 10.0
    HTTP_LOGIN_EXPOSED = 15.0  # Login over HTTP (no TLS)

    # High-risk ports (database, admin, remote access)
    HIGH_RISK_PORTS = {
        22: 8.0,    # SSH
        23: 10.0,   # Telnet (very high risk)
        445: 8.0,   # SMB
        1433: 7.0,  # MSSQL
        3306: 7.0,  # MySQL
        3389: 9.0,  # RDP
        5432: 7.0,  # PostgreSQL
        5984: 6.0,  # CouchDB
        6379: 7.0,  # Redis
        7001: 6.0,  # WebLogic
        8089: 5.0,  # Splunk
        9200: 7.0,  # Elasticsearch
        27017: 7.0, # MongoDB
    }

    # Login page indicators
    LOGIN_INDICATORS = [
        'login', 'signin', 'sign-in', 'auth', 'sso',
        'admin', 'console', 'dashboard', 'portal'
    ]

    def __init__(self, db: Session):
        """
        Initialize risk scoring engine

        Args:
            db: Database session
        """
        self.db = db

    def calculate_asset_risk(self, asset_id: int) -> Dict:
        """
        Calculate comprehensive risk score for an asset

        Args:
            asset_id: Asset ID to score

        Returns:
            Dict with score breakdown and recommendations
        """
        asset = self.db.query(Asset).filter_by(id=asset_id).first()

        if not asset:
            logger.warning(f"Asset {asset_id} not found for risk scoring")
            return {
                'asset_id': asset_id,
                'risk_score': 0.0,
                'error': 'asset_not_found'
            }

        # Initialize score components
        components = {
            'findings_score': 0.0,
            'certificate_score': 0.0,
            'port_exposure_score': 0.0,
            'service_security_score': 0.0,
            'asset_age_score': 0.0
        }

        recommendations = []

        # 1. Findings Score (Nuclei vulnerabilities)
        findings_data = self._score_findings(asset)
        components['findings_score'] = findings_data['score']
        recommendations.extend(findings_data.get('recommendations', []))

        # 2. Certificate/TLS Score
        cert_data = self._score_certificates(asset)
        components['certificate_score'] = cert_data['score']
        recommendations.extend(cert_data.get('recommendations', []))

        # 3. Port Exposure Score
        port_data = self._score_port_exposure(asset)
        components['port_exposure_score'] = port_data['score']
        recommendations.extend(port_data.get('recommendations', []))

        # 4. Service Security Score (login pages, HTTP vs HTTPS, etc.)
        service_data = self._score_service_security(asset)
        components['service_security_score'] = service_data['score']
        recommendations.extend(service_data.get('recommendations', []))

        # 5. Asset Age Score (new assets get bonus)
        age_data = self._score_asset_age(asset)
        components['asset_age_score'] = age_data['score']
        recommendations.extend(age_data.get('recommendations', []))

        # Calculate total score (capped at 100.0)
        total_score = sum(components.values())
        total_score = min(total_score, 100.0)

        # Determine risk level
        risk_level = self._get_risk_level(total_score)

        return {
            'asset_id': asset_id,
            'asset_identifier': asset.identifier,
            'risk_score': round(total_score, 2),
            'risk_level': risk_level,
            'components': components,
            'recommendations': recommendations,
            'last_calculated': datetime.utcnow().isoformat()
        }

    def _score_findings(self, asset: Asset) -> Dict:
        """Score based on vulnerability findings"""
        findings = self.db.query(Finding).filter_by(
            asset_id=asset.id,
            status='open'
        ).all()

        score = 0.0
        recommendations = []
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}

        for finding in findings:
            severity = finding.severity.lower() if finding.severity else 'info'
            weight = self.FINDING_WEIGHTS.get(severity, 0.0)
            score += weight

            if severity in severity_counts:
                severity_counts[severity] += 1

        # Add recommendations based on findings
        if severity_counts['critical'] > 0:
            recommendations.append({
                'priority': 'critical',
                'message': f"{severity_counts['critical']} critical vulnerabilities require immediate remediation"
            })

        if severity_counts['high'] > 0:
            recommendations.append({
                'priority': 'high',
                'message': f"{severity_counts['high']} high-severity vulnerabilities need urgent attention"
            })

        return {
            'score': min(score, 50.0),  # Cap findings score at 50
            'severity_counts': severity_counts,
            'recommendations': recommendations
        }

    def _score_certificates(self, asset: Asset) -> Dict:
        """Score based on TLS certificate security"""
        # Query certificates using raw SQL since there's no ORM model
        query = text("""
            SELECT id, subject_cn, is_expired, days_until_expiry
            FROM certificates
            WHERE asset_id = :asset_id
        """)

        result = self.db.execute(query, {'asset_id': asset.id})
        certificates = result.fetchall()

        score = 0.0
        recommendations = []
        issues = []

        for cert in certificates:
            cert_id, subject_cn, is_expired, days_until_expiry = cert

            # Check for expired certificates
            if is_expired:
                score += self.EXPIRED_CERT_PENALTY
                issues.append('expired_certificate')
                recommendations.append({
                    'priority': 'critical',
                    'message': f"Certificate expired for {asset.identifier}"
                })

            # Check for expiring certificates (< 30 days)
            elif days_until_expiry is not None and days_until_expiry < 30:
                score += self.EXPIRING_CERT_PENALTY
                issues.append('expiring_certificate')
                recommendations.append({
                    'priority': 'medium',
                    'message': f"Certificate expires in {days_until_expiry} days for {asset.identifier}"
                })

            # Check for certificate CN mismatch
            if subject_cn and asset.identifier:
                # Simple mismatch check
                cn_clean = subject_cn.replace('*.', '')
                if cn_clean not in asset.identifier and asset.identifier not in cn_clean:
                    score += self.CERT_MISMATCH_PENALTY
                    issues.append('certificate_mismatch')
                    recommendations.append({
                        'priority': 'high',
                        'message': f"Certificate CN '{subject_cn}' doesn't match '{asset.identifier}'"
                    })

        return {
            'score': min(score, 30.0),  # Cap certificate score at 30
            'issues': issues,
            'recommendations': recommendations
        }

    def _score_port_exposure(self, asset: Asset) -> Dict:
        """Score based on exposed high-risk ports"""
        services = self.db.query(Service).filter_by(asset_id=asset.id).all()

        score = 0.0
        recommendations = []
        exposed_ports = []

        for service in services:
            if service.port in self.HIGH_RISK_PORTS:
                port_penalty = self.HIGH_RISK_PORTS[service.port]
                score += port_penalty
                exposed_ports.append(service.port)

                port_names = {
                    22: 'SSH', 23: 'Telnet', 445: 'SMB',
                    1433: 'MSSQL', 3306: 'MySQL', 3389: 'RDP',
                    5432: 'PostgreSQL', 5984: 'CouchDB',
                    6379: 'Redis', 7001: 'WebLogic',
                    8089: 'Splunk', 9200: 'Elasticsearch',
                    27017: 'MongoDB'
                }

                port_name = port_names.get(service.port, f'Port {service.port}')

                recommendations.append({
                    'priority': 'high' if service.port in [23, 3389] else 'medium',
                    'message': f"High-risk {port_name} service exposed on {asset.identifier}"
                })

        return {
            'score': min(score, 40.0),  # Cap port exposure score at 40
            'exposed_high_risk_ports': exposed_ports,
            'recommendations': recommendations
        }

    def _score_service_security(self, asset: Asset) -> Dict:
        """Score based on service security (login pages, HTTP, etc.)"""
        services = self.db.query(Service).filter_by(asset_id=asset.id).all()

        score = 0.0
        recommendations = []
        issues = []

        for service in services:
            # Check for login pages
            is_login_page = False
            title = (service.http_title or '').lower()

            for indicator in self.LOGIN_INDICATORS:
                if indicator in title:
                    is_login_page = True
                    break

            if is_login_page:
                # Check if it's over HTTP (no TLS)
                if service.protocol == 'http' and not service.has_tls:
                    score += self.HTTP_LOGIN_EXPOSED
                    issues.append('http_login_exposed')
                    recommendations.append({
                        'priority': 'critical',
                        'message': f"Login page '{service.http_title}' exposed over HTTP (no encryption) on {asset.identifier}"
                    })
                else:
                    # HTTPS login page
                    score += self.LOGIN_PAGE_EXPOSED
                    recommendations.append({
                        'priority': 'medium',
                        'message': f"Login page '{service.http_title}' exposed to internet on {asset.identifier}"
                    })

        return {
            'score': min(score, 25.0),  # Cap service security score at 25
            'issues': issues,
            'recommendations': recommendations
        }

    def _score_asset_age(self, asset: Asset) -> Dict:
        """Score based on asset age (new assets get bonus for monitoring)"""
        score = 0.0
        recommendations = []

        if asset.first_seen:
            days_since_discovery = (datetime.utcnow() - asset.first_seen).days

            if days_since_discovery <= 7:
                score += self.NEW_ASSET_BONUS
                recommendations.append({
                    'priority': 'high',
                    'message': f"New asset discovered {days_since_discovery} days ago - requires additional monitoring"
                })

        return {
            'score': score,
            'recommendations': recommendations
        }

    def _get_risk_level(self, score: float) -> str:
        """Determine risk level from score"""
        if score >= 71.0:
            return 'critical'
        elif score >= 41.0:
            return 'high'
        elif score >= 21.0:
            return 'medium'
        else:
            return 'low'

    def calculate_tenant_risk_scorecard(self, tenant_id: int) -> Dict:
        """
        Calculate risk scorecard for entire tenant

        Args:
            tenant_id: Tenant ID

        Returns:
            Aggregated risk metrics for tenant
        """
        assets = self.db.query(Asset).filter_by(
            tenant_id=tenant_id,
            is_active=True
        ).all()

        if not assets:
            return {
                'tenant_id': tenant_id,
                'total_assets': 0,
                'average_risk_score': 0.0,
                'risk_distribution': {}
            }

        risk_levels = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        total_score = 0.0
        high_risk_assets = []

        for asset in assets:
            if asset.risk_score is not None:
                total_score += asset.risk_score
                level = self._get_risk_level(asset.risk_score)
                risk_levels[level] += 1

                if asset.risk_score >= 70.0:
                    high_risk_assets.append({
                        'identifier': asset.identifier,
                        'risk_score': asset.risk_score
                    })

        average_score = total_score / len(assets) if assets else 0.0

        return {
            'tenant_id': tenant_id,
            'total_assets': len(assets),
            'average_risk_score': round(average_score, 2),
            'risk_distribution': risk_levels,
            'high_risk_assets': sorted(high_risk_assets, key=lambda x: x['risk_score'], reverse=True)[:10],
            'last_calculated': datetime.utcnow().isoformat()
        }


def batch_calculate_risk_scores(db: Session, tenant_id: int, batch_size: int = 100) -> Dict:
    """
    Calculate risk scores for all assets in a tenant (batch operation)

    Args:
        db: Database session
        tenant_id: Tenant ID
        batch_size: Number of assets to process per batch

    Returns:
        Summary of risk score calculations
    """
    from app.repositories.asset_repository import AssetRepository

    logger.info(f"Starting batch risk score calculation for tenant {tenant_id}")

    engine = RiskScoringEngine(db)
    asset_repo = AssetRepository(db)

    # Get all active assets for tenant
    assets = db.query(Asset).filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).all()

    total_assets = len(assets)
    processed = 0
    updated = 0

    logger.info(f"Processing {total_assets} assets for risk scoring")

    # Process in batches
    for i in range(0, total_assets, batch_size):
        batch = assets[i:i + batch_size]

        for asset in batch:
            try:
                # Calculate risk score
                result = engine.calculate_asset_risk(asset.id)

                # Update asset risk score
                if 'risk_score' in result:
                    asset_repo.update_risk_score(asset.id, result['risk_score'])
                    updated += 1

                processed += 1

            except Exception as e:
                logger.error(f"Error calculating risk for asset {asset.id}: {e}", exc_info=True)

        # Commit batch
        db.commit()
        logger.debug(f"Processed batch {i//batch_size + 1}: {len(batch)} assets")

    logger.info(f"Risk scoring complete: {updated}/{total_assets} assets updated")

    return {
        'tenant_id': tenant_id,
        'total_assets': total_assets,
        'processed': processed,
        'updated': updated
    }
