"""
False positive suppression service for Nuclei findings

Manages suppression rules to filter out false positives:
- Pattern-based suppression (regex on template_id, URL, etc.)
- Global suppressions (all tenants)
- Tenant-specific suppressions
- Time-based expiration
- Audit logging
"""

import re
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.database import Suppression, Finding
from app.utils.logger import TenantLoggerAdapter

logger = logging.getLogger(__name__)


class SuppressionService:
    """
    Service for managing finding suppressions

    Features:
    - Pattern-based suppression rules
    - Multi-tenant support
    - Expiration dates
    - Audit trail
    - Rule priority
    """

    def __init__(self, db: Session, tenant_id: Optional[int] = None):
        """
        Initialize suppression service

        Args:
            db: Database session
            tenant_id: Optional tenant ID for tenant-specific operations
        """
        self.db = db
        self.tenant_id = tenant_id
        self.logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id}) if tenant_id else logger

    def should_suppress(self, finding: Dict) -> tuple[bool, Optional[str]]:
        """
        Check if finding should be suppressed

        Applies suppression rules in priority order:
        1. Global suppressions
        2. Tenant-specific suppressions

        Args:
            finding: Finding dict with keys:
                - template_id
                - matched_at (URL)
                - host
                - severity
                - name

        Returns:
            Tuple of (should_suppress, reason)
        """
        # Get active suppressions
        suppressions = self._get_active_suppressions()

        for suppression in suppressions:
            if self._matches_suppression(finding, suppression):
                reason = f"Suppressed by rule: {suppression.name} (ID: {suppression.id})"
                self.logger.debug(f"Finding suppressed: {reason}")
                return True, reason

        return False, None

    def create_suppression(
        self,
        name: str,
        pattern_type: str,
        pattern: str,
        reason: str,
        expires_at: Optional[datetime] = None,
        is_global: bool = False
    ) -> Dict:
        """
        Create a new suppression rule

        Args:
            name: Human-readable name
            pattern_type: Type of pattern (template_id, url, host, severity, name)
            pattern: Regex pattern to match
            reason: Reason for suppression
            expires_at: Optional expiration date
            is_global: If True, applies to all tenants

        Returns:
            Created suppression dict
        """
        # Validate pattern is valid regex
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        # Create suppression
        suppression = Suppression(
            tenant_id=None if is_global else self.tenant_id,
            name=name,
            pattern_type=pattern_type,
            pattern=pattern,
            reason=reason,
            is_active=True,
            is_global=is_global,
            expires_at=expires_at,
            created_at=datetime.utcnow()
        )

        self.db.add(suppression)
        self.db.commit()
        self.db.refresh(suppression)

        self.logger.info(f"Created suppression rule: {name} (ID: {suppression.id})")

        return self._suppression_to_dict(suppression)

    def update_suppression(
        self,
        suppression_id: int,
        is_active: Optional[bool] = None,
        expires_at: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        Update suppression rule

        Args:
            suppression_id: Suppression ID
            is_active: Optional new active status
            expires_at: Optional new expiration date

        Returns:
            Updated suppression dict or None
        """
        suppression = self.db.query(Suppression).filter_by(id=suppression_id).first()

        if not suppression:
            return None

        # Check tenant ownership
        if not suppression.is_global and suppression.tenant_id != self.tenant_id:
            self.logger.warning(f"Attempted to update suppression from different tenant")
            return None

        if is_active is not None:
            suppression.is_active = is_active

        if expires_at is not None:
            suppression.expires_at = expires_at

        suppression.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(suppression)

        self.logger.info(f"Updated suppression rule: {suppression.name} (ID: {suppression_id})")

        return self._suppression_to_dict(suppression)

    def delete_suppression(self, suppression_id: int) -> bool:
        """
        Delete suppression rule

        Args:
            suppression_id: Suppression ID

        Returns:
            True if deleted, False otherwise
        """
        suppression = self.db.query(Suppression).filter_by(id=suppression_id).first()

        if not suppression:
            return False

        # Check tenant ownership
        if not suppression.is_global and suppression.tenant_id != self.tenant_id:
            self.logger.warning(f"Attempted to delete suppression from different tenant")
            return False

        self.db.delete(suppression)
        self.db.commit()

        self.logger.info(f"Deleted suppression rule: {suppression.name} (ID: {suppression_id})")

        return True

    def list_suppressions(
        self,
        include_global: bool = True,
        include_expired: bool = False
    ) -> List[Dict]:
        """
        List suppression rules

        Args:
            include_global: Include global suppressions
            include_expired: Include expired suppressions

        Returns:
            List of suppression dicts
        """
        query = self.db.query(Suppression)

        # Filter by tenant
        if include_global:
            query = query.filter(
                or_(
                    Suppression.tenant_id == self.tenant_id,
                    Suppression.is_global == True
                )
            )
        else:
            query = query.filter(Suppression.tenant_id == self.tenant_id)

        # Filter expired
        if not include_expired:
            query = query.filter(
                or_(
                    Suppression.expires_at.is_(None),
                    Suppression.expires_at > datetime.utcnow()
                )
            )

        suppressions = query.order_by(Suppression.created_at.desc()).all()

        return [self._suppression_to_dict(s) for s in suppressions]

    def filter_findings(self, findings: List[Dict]) -> tuple[List[Dict], List[Dict]]:
        """
        Filter findings through suppression rules

        Args:
            findings: List of finding dicts

        Returns:
            Tuple of (unsuppressed_findings, suppressed_findings)
        """
        unsuppressed = []
        suppressed = []

        for finding in findings:
            should_suppress, reason = self.should_suppress(finding)

            if should_suppress:
                finding['suppression_reason'] = reason
                suppressed.append(finding)
            else:
                unsuppressed.append(finding)

        self.logger.info(
            f"Filtered {len(findings)} findings: "
            f"{len(unsuppressed)} unsuppressed, {len(suppressed)} suppressed"
        )

        return unsuppressed, suppressed

    def _get_active_suppressions(self) -> List:
        """
        Get active suppressions for current tenant

        Returns:
            List of Suppression objects
        """
        now = datetime.utcnow()

        query = self.db.query(Suppression).filter(
            and_(
                Suppression.is_active == True,
                or_(
                    Suppression.expires_at.is_(None),
                    Suppression.expires_at > now
                ),
                or_(
                    Suppression.tenant_id == self.tenant_id,
                    Suppression.is_global == True
                )
            )
        )

        return query.order_by(Suppression.priority.desc()).all()

    def _matches_suppression(self, finding: Dict, suppression) -> bool:
        """
        Check if finding matches suppression rule

        Args:
            finding: Finding dict
            suppression: Suppression object

        Returns:
            True if matches, False otherwise
        """
        pattern_type = suppression.pattern_type
        pattern = suppression.pattern

        # Get value to match against
        value = None

        if pattern_type == 'template_id':
            value = finding.get('template_id', '')
        elif pattern_type == 'url':
            value = finding.get('matched_at', '')
        elif pattern_type == 'host':
            value = finding.get('host', '')
        elif pattern_type == 'severity':
            value = finding.get('severity', '')
        elif pattern_type == 'name':
            value = finding.get('name', '')
        else:
            return False

        # Match pattern
        try:
            if re.search(pattern, str(value), re.IGNORECASE):
                return True
        except re.error as e:
            self.logger.warning(f"Invalid regex in suppression {suppression.id}: {e}")
            return False

        return False

    def _suppression_to_dict(self, suppression) -> Dict:
        """Convert Suppression object to dict"""
        return {
            'id': suppression.id,
            'tenant_id': suppression.tenant_id,
            'name': suppression.name,
            'pattern_type': suppression.pattern_type,
            'pattern': suppression.pattern,
            'reason': suppression.reason,
            'is_active': suppression.is_active,
            'is_global': suppression.is_global,
            'priority': suppression.priority,
            'expires_at': suppression.expires_at.isoformat() if suppression.expires_at else None,
            'created_at': suppression.created_at.isoformat() if suppression.created_at else None,
            'updated_at': suppression.updated_at.isoformat() if suppression.updated_at else None
        }


# Common suppression patterns
COMMON_SUPPRESSIONS = [
    {
        'name': 'Suppress DNS CAA records on development',
        'pattern_type': 'template_id',
        'pattern': r'dns-caa-.*',
        'reason': 'Development environments do not require CAA records'
    },
    {
        'name': 'Suppress localhost findings',
        'pattern_type': 'host',
        'pattern': r'^(localhost|127\.0\.0\.1)$',
        'reason': 'Localhost findings are not relevant'
    },
    {
        'name': 'Suppress test/staging environments',
        'pattern_type': 'url',
        'pattern': r'(test|staging|dev)\.',
        'reason': 'Test environments may have intentional vulnerabilities'
    }
]
