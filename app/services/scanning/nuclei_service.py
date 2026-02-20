"""
Nuclei vulnerability scanner service

Provides comprehensive vulnerability scanning using ProjectDiscovery's Nuclei:
- Execute scans with customizable templates and severity filters
- Parse and normalize scan results
- Support for bulk scanning with rate limiting
- Integration with template management
- Security controls and validation

Architecture:
    URLValidator -> NucleiService -> SecureExecutor -> Nuclei
                         |
                         v
                   FindingRepository -> PostgreSQL
                         |
                         v
                    MinIO (raw JSON)
"""

import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse

from app.utils.secure_executor import SecureToolExecutor, ToolExecutionError
from app.utils.validators import URLValidator
from app.utils.storage import store_raw_output
from app.config import settings

logger = logging.getLogger(__name__)


class NucleiService:
    """
    Service for executing Nuclei vulnerability scans

    Security Features:
    - URL validation before scanning
    - Template whitelist/blacklist
    - Rate limiting
    - Resource limits via SecureToolExecutor
    - Output sanitization (credential detection)
    """

    # Default severity levels
    DEFAULT_SEVERITIES = ['critical', 'high', 'medium']

    # Template categories
    TEMPLATE_CATEGORIES = {
        'cves': 'CVE-based vulnerabilities',
        'exposed-panels': 'Exposed admin/login panels',
        'misconfigurations': 'Common misconfigurations',
        'default-logins': 'Default credentials',
        'takeovers': 'Subdomain takeovers',
        'exposures': 'Information disclosure',
        'technologies': 'Technology detection',
        'vulnerabilities': 'Generic vulnerabilities',
        'fuzzing': 'Fuzzing templates',
        'workflows': 'Workflow-based scans'
    }

    def __init__(self, tenant_id: int):
        """
        Initialize Nuclei service for tenant

        Args:
            tenant_id: Tenant ID for isolation and tracking
        """
        self.tenant_id = tenant_id
        self.url_validator = URLValidator()

    async def scan_urls(
        self,
        urls: List[str],
        templates: Optional[List[str]] = None,
        severity: Optional[List[str]] = None,
        rate_limit: int = 1000,  # Increased from 300 for faster scanning
        concurrency: int = 200,  # Increased from 50 for faster scanning
        timeout: int = 1800
    ) -> Dict:
        """
        Execute Nuclei scan on list of URLs

        Args:
            urls: List of URLs to scan
            templates: Optional list of template paths/categories
                Examples: ['cves/', 'exposed-panels/', 'custom-template.yaml']
            severity: Severity filter (critical, high, medium, low, info)
            rate_limit: Requests per second (default: 300)
            concurrency: Concurrent templates (default: 50)
            timeout: Scan timeout in seconds (default: 1800 = 30 min)

        Returns:
            Dict with scan results:
            {
                'findings': List[Dict],
                'stats': {
                    'urls_scanned': int,
                    'findings_count': int,
                    'by_severity': Dict[str, int]
                },
                'errors': List[str]
            }

        Raises:
            ToolExecutionError: If scan fails
        """
        logger.info(f"Starting Nuclei scan for tenant {self.tenant_id}: {len(urls)} URLs")

        # Validate URLs
        valid_urls, validation_errors = self._validate_urls(urls)

        if not valid_urls:
            logger.warning(f"No valid URLs for Nuclei scan (tenant {self.tenant_id})")
            return {
                'findings': [],
                'stats': {
                    'urls_scanned': 0,
                    'findings_count': 0,
                    'by_severity': {}
                },
                'errors': validation_errors
            }

        # Use defaults if not provided
        severity = severity or self.DEFAULT_SEVERITIES

        # Execute scan
        with SecureToolExecutor(self.tenant_id) as executor:
            # Create URLs input file
            urls_content = '\n'.join(valid_urls)
            urls_file = executor.create_input_file('urls.txt', urls_content)

            # Build Nuclei arguments
            args = self._build_nuclei_args(
                urls_file=urls_file,
                templates=templates,
                severity=severity,
                rate_limit=rate_limit,
                concurrency=concurrency
            )

            # Execute Nuclei
            logger.info(f"Executing Nuclei with args: {' '.join(args[:10])}...")

            try:
                returncode, stdout, stderr = executor.execute(
                    'nuclei',
                    args,
                    timeout=timeout
                )

                if returncode != 0 and returncode != 1:  # 1 is OK (findings found)
                    logger.warning(f"Nuclei returned code {returncode}: {stderr[:500]}")

            except ToolExecutionError as e:
                logger.error(f"Nuclei execution failed for tenant {self.tenant_id}: {e}")
                return {
                    'findings': [],
                    'stats': {
                        'urls_scanned': len(valid_urls),
                        'findings_count': 0,
                        'by_severity': {}
                    },
                    'errors': [str(e)] + validation_errors
                }

            # Parse results
            findings = self._parse_nuclei_output(stdout)

            # Calculate statistics
            stats = self._calculate_stats(valid_urls, findings)

            # Store raw output in MinIO
            store_raw_output(
                self.tenant_id,
                'nuclei',
                {
                    'urls': valid_urls,
                    'templates': templates,
                    'severity': severity,
                    'findings': findings,
                    'stats': stats,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

            logger.info(
                f"Nuclei scan complete for tenant {self.tenant_id}: "
                f"{stats['findings_count']} findings from {stats['urls_scanned']} URLs"
            )

            return {
                'findings': findings,
                'stats': stats,
                'errors': validation_errors
            }

    async def scan_asset(
        self,
        asset_id: int,
        asset_url: str,
        templates: Optional[List[str]] = None,
        severity: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Scan a single asset (convenience method)

        Args:
            asset_id: Asset ID for tracking
            asset_url: URL to scan
            templates: Optional template paths
            severity: Severity filter

        Returns:
            List of findings with asset_id attached
        """
        result = await self.scan_urls(
            urls=[asset_url],
            templates=templates,
            severity=severity
        )

        # Attach asset_id to each finding
        for finding in result['findings']:
            finding['asset_id'] = asset_id

        return result['findings']

    def _validate_urls(self, urls: List[str]) -> Tuple[List[str], List[str]]:
        """
        Validate URLs for scanning

        Security checks:
        - URL format validation
        - SSRF prevention (no internal IPs, metadata endpoints)
        - Scheme validation (http/https only)

        Args:
            urls: List of URLs to validate

        Returns:
            Tuple of (valid_urls, error_messages)
        """
        valid_urls = []
        errors = []

        for url in urls:
            is_valid, error = self.url_validator.validate_url(url)

            if is_valid:
                valid_urls.append(url)
            else:
                error_msg = f"Invalid URL '{url}': {error}"
                errors.append(error_msg)
                logger.warning(error_msg)

        return valid_urls, errors

    def _build_nuclei_args(
        self,
        urls_file: str,
        templates: Optional[List[str]],
        severity: List[str],
        rate_limit: int,
        concurrency: int
    ) -> List[str]:
        """
        Build Nuclei command arguments

        Args:
            urls_file: Path to file containing URLs
            templates: Template paths/categories
            severity: Severity filter
            rate_limit: Rate limit (requests/second)
            concurrency: Concurrent templates

        Returns:
            List of command arguments
        """
        args = [
            '-l', urls_file,           # Input URLs file
            '-jsonl',                  # JSONL output (Nuclei v3+)
            '-silent',                 # Minimal console output
            '-no-color',               # Disable colors
            '-stats',                  # Print statistics
            '-rl', str(rate_limit),    # Rate limit
            '-c', str(concurrency),    # Concurrency
            '-timeout', '10',          # Request timeout (seconds)
            '-retries', '1',           # Retry failed requests
        ]

        # Add severity filter
        if severity:
            severity_str = ','.join(severity)
            args.extend(['-severity', severity_str])

        # Add templates
        if templates:
            for template in templates:
                args.extend(['-t', template])
        else:
            # Default templates: Comprehensive coverage including fuzzing
            # Rely on severity filter to limit scope
            args.extend([
                '-t', 'cves/',                    # CVE vulnerabilities
                '-t', 'vulnerabilities/',         # Generic vulnerabilities (includes SQL injection)
                '-t', 'exposures/',               # Information disclosure
                '-t', 'misconfiguration/',        # Misconfigurations
                '-t', 'exposed-panels/',          # Admin panels
                '-t', 'fuzzing/',                 # Fuzzing templates (SQL, XSS, etc.)
            ])

        # Exclude certain templates that may cause DoS or are too noisy
        # Only exclude actual DoS templates, allow fuzzing/intrusive tests
        args.extend([
            '-exclude-tags', 'dos'  # Only exclude DoS attacks
        ])

        return args

    def _parse_nuclei_output(self, stdout: str) -> List[Dict]:
        """
        Parse Nuclei JSON output into normalized findings

        Nuclei JSON format:
        {
            "template-id": "CVE-2021-12345",
            "info": {
                "name": "Vulnerability Name",
                "severity": "critical",
                "description": "...",
                "tags": ["cve", "..."],
                "reference": ["https://..."],
                "classification": {
                    "cvss-metrics": "...",
                    "cvss-score": 9.8,
                    "cve-id": ["CVE-2021-12345"]
                }
            },
            "matcher-name": "version-check",
            "type": "http",
            "host": "https://example.com",
            "matched-at": "https://example.com/path",
            "timestamp": "2024-01-01T12:00:00Z",
            "curl-command": "...",
            "extracted-results": ["..."]
        }

        Args:
            stdout: Raw Nuclei output

        Returns:
            List of normalized finding dicts
        """
        findings = []

        for line in stdout.strip().split('\n'):
            if not line:
                continue

            try:
                result = json.loads(line)
                finding = self.parse_nuclei_result(result)

                if finding:
                    findings.append(finding)

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Nuclei JSON: {e}")
                continue

        return findings

    def parse_nuclei_result(self, result: Dict) -> Optional[Dict]:
        """
        Parse single Nuclei result into normalized finding

        Normalizes Nuclei output into our Finding model format with:
        - Consistent field names
        - Severity normalization
        - Evidence extraction
        - CVE/CVSS extraction

        Args:
            result: Nuclei JSON result

        Returns:
            Normalized finding dict or None if parsing fails
        """
        try:
            info = result.get('info', {})
            classification = info.get('classification', {})

            # Extract CVE ID
            cve_id = None
            cve_list = classification.get('cve-id', [])
            if cve_list and isinstance(cve_list, list):
                cve_id = cve_list[0]

            # Extract CVSS score
            cvss_score = classification.get('cvss-score')
            if cvss_score:
                try:
                    cvss_score = float(cvss_score)
                except (ValueError, TypeError):
                    cvss_score = None

            # Build evidence
            evidence = {
                'matched_at': result.get('matched-at') or result.get('host'),
                'matcher_name': result.get('matcher-name'),
                'extracted_results': result.get('extracted-results', []),
                'timestamp': result.get('timestamp'),
                'type': result.get('type'),
                'curl_command': result.get('curl-command'),
                'template_id': result.get('template-id'),
                'description': info.get('description'),
                'reference': info.get('reference', []),
                'tags': info.get('tags', [])
            }

            # Parse URL to get host
            matched_url = result.get('matched-at') or result.get('host')
            host = None
            if matched_url:
                try:
                    parsed = urlparse(matched_url)
                    host = parsed.hostname
                except Exception:
                    host = matched_url

            # Normalize severity
            severity = info.get('severity', 'info').lower()
            if severity not in ['critical', 'high', 'medium', 'low', 'info']:
                severity = 'info'

            finding = {
                'template_id': result.get('template-id'),
                'name': info.get('name', 'Unknown Vulnerability'),
                'severity': severity,
                'cvss_score': cvss_score,
                'cve_id': cve_id,
                'evidence': json.dumps(evidence),
                'matched_at': matched_url,
                'host': host,
                'source': 'nuclei',
                'discovered_at': datetime.utcnow()
            }

            return finding

        except Exception as e:
            logger.warning(f"Failed to parse Nuclei result: {e}")
            logger.debug(f"Result: {result}")
            return None

    def _calculate_stats(self, urls: List[str], findings: List[Dict]) -> Dict:
        """
        Calculate scan statistics

        Args:
            urls: List of scanned URLs
            findings: List of findings

        Returns:
            Statistics dict
        """
        stats = {
            'urls_scanned': len(urls),
            'findings_count': len(findings),
            'by_severity': {
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'info': 0
            }
        }

        # Count by severity
        for finding in findings:
            severity = finding.get('severity', 'info')
            if severity in stats['by_severity']:
                stats['by_severity'][severity] += 1

        return stats


def calculate_risk_score_from_findings(findings: List[Dict]) -> float:
    """
    Calculate risk score based on findings

    Scoring algorithm:
    - Critical finding: +3.0
    - High finding: +2.0
    - Medium finding: +1.0
    - Low finding: +0.5
    - Info finding: +0.1
    - Max score: 10.0

    Args:
        findings: List of finding dicts

    Returns:
        Risk score (0.0 to 10.0)
    """
    severity_weights = {
        'critical': 3.0,
        'high': 2.0,
        'medium': 1.0,
        'low': 0.5,
        'info': 0.1
    }

    score = 0.0

    for finding in findings:
        severity = finding.get('severity', 'info')
        weight = severity_weights.get(severity, 0.0)
        score += weight

    # Cap at 10.0
    return min(score, 10.0)
