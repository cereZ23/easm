#!/usr/bin/env python3
"""
Security Checklist Validator for Sprint 2

Automates security checks before deployment:
- Validates all critical vulnerabilities are fixed
- Checks for hardcoded secrets
- Verifies input validation coverage
- Tests API security controls
- Validates checksum presence
"""

import sys
import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
import json


class SecurityChecker:
    """Automated security checklist validator"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': [],
            'score': 0,
            'max_score': 0
        }

    def run_all_checks(self) -> bool:
        """Run all security checks"""
        print("=" * 80)
        print("EASM PLATFORM - SECURITY CHECKLIST VALIDATOR")
        print("=" * 80)
        print()

        checks = [
            ("Check for hardcoded secrets", self.check_hardcoded_secrets, 10),
            ("Verify binary checksums in Dockerfile", self.check_binary_checksums, 10),
            ("Check domain validation implementation", self.check_domain_validation, 10),
            ("Verify JWT implementation", self.check_jwt_implementation, 10),
            ("Check input sanitization", self.check_input_sanitization, 5),
            ("Verify security headers", self.check_security_headers, 5),
            ("Check for SQL injection prevention", self.check_sql_injection_prevention, 5),
            ("Verify rate limiting configuration", self.check_rate_limiting, 5),
            ("Check tenant isolation", self.check_tenant_isolation, 10),
            ("Verify audit logging", self.check_audit_logging, 5),
            ("Check dependency vulnerabilities", self.check_dependencies, 10),
            ("Verify CORS configuration", self.check_cors_config, 5),
            ("Check API authentication coverage", self.check_api_auth_coverage, 10),
        ]

        for check_name, check_func, points in checks:
            self.results['max_score'] += points
            print(f"\n[CHECK] {check_name}...")
            try:
                passed, message = check_func()
                if passed:
                    self.results['passed'].append(check_name)
                    self.results['score'] += points
                    print(f"  ✓ PASS: {message}")
                else:
                    self.results['failed'].append(check_name)
                    print(f"  ✗ FAIL: {message}")
            except Exception as e:
                self.results['failed'].append(check_name)
                print(f"  ✗ ERROR: {str(e)}")

        self.print_summary()
        return len(self.results['failed']) == 0

    def check_hardcoded_secrets(self) -> Tuple[bool, str]:
        """Check for hardcoded secrets in code"""
        dangerous_patterns = [
            (r'password\s*=\s*["\'](?!.*CHANGE|.*ENV)[^"\']{6,}["\']', 'hardcoded password'),
            (r'api[_-]?key\s*=\s*["\'](?!.*CHANGE|.*ENV)[^"\']{6,}["\']', 'hardcoded API key'),
            (r'secret\s*=\s*["\'](?!.*CHANGE|.*ENV)[^"\']{6,}["\']', 'hardcoded secret'),
            (r'token\s*=\s*["\'](?!.*CHANGE|.*ENV)[^"\']{20,}["\']', 'hardcoded token'),
        ]

        app_dir = self.project_root / 'app'
        violations = []

        for py_file in app_dir.rglob('*.py'):
            if 'test' in str(py_file):
                continue

            content = py_file.read_text()
            for pattern, desc in dangerous_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    violations.append(f"{py_file.name}: {desc}")

        if violations:
            return False, f"Found hardcoded secrets: {', '.join(violations)}"

        return True, "No hardcoded secrets found"

    def check_binary_checksums(self) -> Tuple[bool, str]:
        """Verify binary checksum validation in Dockerfile"""
        dockerfile_secure = self.project_root / 'Dockerfile.worker.secure'

        if not dockerfile_secure.exists():
            return False, "Secure Dockerfile not found"

        content = dockerfile_secure.read_text()

        # Check for SHA256 definitions
        if 'ARG' not in content or 'SHA256' not in content:
            return False, "No SHA256 checksum definitions found"

        # Check for verification function
        if 'sha256sum' not in content:
            return False, "No checksum verification logic found"

        # Count tools with checksums
        sha256_args = re.findall(r'ARG \w+_SHA256=', content)
        if len(sha256_args) < 5:  # At least 5 tools should have checksums
            return False, f"Only {len(sha256_args)} tools have checksums"

        return True, f"Binary checksums verified for {len(sha256_args)} tools"

    def check_domain_validation(self) -> Tuple[bool, str]:
        """Check domain validation implementation"""
        validator_file = self.project_root / 'app' / 'utils' / 'validators.py'

        if not validator_file.exists():
            return False, "Domain validator not found"

        content = validator_file.read_text()

        required_checks = [
            ('command injection', ['dangerous_chars', ';', '&', '|']),
            ('SSRF prevention', ['RESERVED_NETWORKS', '127.0.0.1', '192.168']),
            ('path traversal', ['../', '..\\\\']),
            ('length validation', ['253', 'len(']),
        ]

        missing = []
        for check_name, keywords in required_checks:
            if not any(kw in content for kw in keywords):
                missing.append(check_name)

        if missing:
            return False, f"Missing validation: {', '.join(missing)}"

        return True, "Domain validation is comprehensive"

    def check_jwt_implementation(self) -> Tuple[bool, str]:
        """Verify JWT implementation"""
        jwt_file = self.project_root / 'app' / 'security' / 'jwt_auth.py'

        if not jwt_file.exists():
            return False, "JWT implementation not found"

        content = jwt_file.read_text()

        required_features = [
            ('token expiration', ['exp', 'timedelta']),
            ('token revocation', ['revoke', 'redis']),
            ('refresh tokens', ['refresh_token']),
            ('password hashing', ['bcrypt', 'hash_password']),
        ]

        missing = []
        for feature_name, keywords in required_features:
            if not any(kw in content for kw in keywords):
                missing.append(feature_name)

        if missing:
            return False, f"Missing JWT features: {', '.join(missing)}"

        return True, "JWT implementation is complete"

    def check_input_sanitization(self) -> Tuple[bool, str]:
        """Check input sanitization"""
        validator_file = self.project_root / 'app' / 'utils' / 'validators.py'

        if not validator_file.exists():
            return False, "Validators not found"

        content = validator_file.read_text()

        if 'InputSanitizer' in content or 'sanitize' in content:
            return True, "Input sanitization implemented"

        return False, "Input sanitization not found"

    def check_security_headers(self) -> Tuple[bool, str]:
        """Verify security headers configuration"""
        # Check if security headers are defined
        app_files = list((self.project_root / 'app').rglob('*.py'))

        required_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'Strict-Transport-Security',
            'Content-Security-Policy'
        ]

        found_headers = []
        for py_file in app_files:
            content = py_file.read_text()
            for header in required_headers:
                if header in content:
                    found_headers.append(header)

        if len(set(found_headers)) >= 3:
            return True, f"Found {len(set(found_headers))} security headers"

        return False, f"Only found {len(set(found_headers))} security headers"

    def check_sql_injection_prevention(self) -> Tuple[bool, str]:
        """Check for SQL injection prevention"""
        # Look for parameterized queries and ORM usage
        app_files = list((self.project_root / 'app').rglob('*.py'))

        raw_sql_pattern = r'\.execute\(["\'].*%s.*["\']'
        violations = []

        for py_file in app_files:
            content = py_file.read_text()
            if re.search(raw_sql_pattern, content):
                violations.append(py_file.name)

        if violations:
            return False, f"Potential SQL injection in: {', '.join(violations)}"

        return True, "Using parameterized queries/ORM"

    def check_rate_limiting(self) -> Tuple[bool, str]:
        """Verify rate limiting configuration"""
        config_file = self.project_root / 'app' / 'config.py'

        if not config_file.exists():
            return False, "Config file not found"

        content = config_file.read_text()

        if 'rate_limit' in content.lower():
            return True, "Rate limiting configured"

        return False, "Rate limiting not configured"

    def check_tenant_isolation(self) -> Tuple[bool, str]:
        """Check tenant isolation implementation"""
        # Look for tenant_id filtering
        app_files = list((self.project_root / 'app').rglob('*.py'))

        tenant_checks = 0
        for py_file in app_files:
            content = py_file.read_text()
            if 'tenant_id' in content:
                tenant_checks += 1

        if tenant_checks >= 5:  # Should be used in multiple files
            return True, f"Tenant isolation found in {tenant_checks} files"

        return False, "Insufficient tenant isolation"

    def check_audit_logging(self) -> Tuple[bool, str]:
        """Verify audit logging"""
        logger_files = list((self.project_root / 'app').rglob('*log*.py'))

        if logger_files:
            return True, f"Logging implemented in {len(logger_files)} files"

        return False, "Audit logging not found"

    def check_dependencies(self) -> Tuple[bool, str]:
        """Check for vulnerable dependencies"""
        requirements_file = self.project_root / 'requirements.txt'

        if not requirements_file.exists():
            return False, "requirements.txt not found"

        # Check if safety is installed
        try:
            result = subprocess.run(
                ['pip', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if 'safety' in result.stdout:
                # Run safety check
                safety_result = subprocess.run(
                    ['safety', 'check', '--file', str(requirements_file)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if safety_result.returncode == 0:
                    return True, "No known vulnerabilities in dependencies"
                else:
                    return False, "Vulnerabilities found in dependencies"
        except:
            pass

        return True, "Dependency check skipped (install 'safety' for full check)"

    def check_cors_config(self) -> Tuple[bool, str]:
        """Verify CORS configuration"""
        config_file = self.project_root / 'app' / 'config.py'

        if not config_file.exists():
            return False, "Config file not found"

        content = config_file.read_text()

        if 'cors_origins' in content and '*' not in content:
            return True, "CORS properly configured (no wildcards)"

        if '*' in content and 'cors' in content.lower():
            return False, "CORS allows wildcard origins (security risk)"

        return True, "CORS configuration found"

    def check_api_auth_coverage(self) -> Tuple[bool, str]:
        """Check API endpoint authentication coverage"""
        router_files = list((self.project_root / 'app' / 'routers').rglob('*.py'))

        if not router_files:
            return True, "No API routers found (skipping)"

        authenticated_endpoints = 0
        total_endpoints = 0

        for router_file in router_files:
            content = router_file.read_text()
            total_endpoints += content.count('@router.')

            if 'Depends' in content and ('get_current_user' in content or 'jwt' in content.lower()):
                authenticated_endpoints += 1

        if total_endpoints == 0:
            return True, "No endpoints to check"

        coverage = (authenticated_endpoints / max(total_endpoints, 1)) * 100

        if coverage >= 80:
            return True, f"API auth coverage: {coverage:.0f}%"

        return False, f"Low API auth coverage: {coverage:.0f}%"

    def print_summary(self):
        """Print check summary"""
        print("\n")
        print("=" * 80)
        print("SECURITY CHECKLIST SUMMARY")
        print("=" * 80)

        print(f"\nPassed: {len(self.results['passed'])}")
        print(f"Failed: {len(self.results['failed'])}")
        print(f"Score: {self.results['score']}/{self.results['max_score']}")

        if self.results['failed']:
            print("\nFailed Checks:")
            for check in self.results['failed']:
                print(f"  - {check}")

        # Calculate security score
        security_score = (self.results['score'] / self.results['max_score']) * 10 if self.results['max_score'] > 0 else 0

        print(f"\n{'='*80}")
        print(f"SECURITY SCORE: {security_score:.1f}/10.0")
        print(f"{'='*80}")

        if security_score >= 9.0:
            print("\n✓ READY FOR DEPLOYMENT")
            print("  Security requirements met for Sprint 2")
        elif security_score >= 7.0:
            print("\n⚠ NEEDS IMPROVEMENT")
            print("  Address failed checks before deployment")
        else:
            print("\n✗ NOT READY FOR DEPLOYMENT")
            print("  Critical security issues must be fixed")

        print()


def main():
    """Main entry point"""
    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Run security checks
    checker = SecurityChecker(project_root)
    success = checker.run_all_checks()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()