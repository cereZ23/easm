#!/usr/bin/env python3
"""
Verification script for Nuclei integration

Tests all components without requiring database or network access.
Validates that all modules import correctly and have proper structure.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all Nuclei-related modules import correctly"""
    print("Testing module imports...")

    try:
        from app.services.scanning.nuclei_service import NucleiService, calculate_risk_score_from_findings
        print("  ✅ nuclei_service imports successfully")

        from app.services.scanning.template_manager import TemplateManager, template_manager
        print("  ✅ template_manager imports successfully")

        from app.services.scanning.suppression_service import SuppressionService, COMMON_SUPPRESSIONS
        print("  ✅ suppression_service imports successfully")

        from app.tasks.scanning import (
            run_nuclei_scan,
            scan_single_asset,
            scan_critical_assets,
            update_nuclei_templates,
            update_asset_risk_scores
        )
        print("  ✅ scanning tasks import successfully")

        from app.repositories.finding_repository import FindingRepository
        print("  ✅ finding_repository imports successfully")

        return True

    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_nuclei_service_structure():
    """Test NucleiService has required methods"""
    print("\nTesting NucleiService structure...")

    from app.services.scanning.nuclei_service import NucleiService

    service = NucleiService(tenant_id=1)

    required_methods = [
        'scan_urls',
        'scan_asset',
        'parse_nuclei_result',
        '_validate_urls',
        '_build_nuclei_args',
        '_parse_nuclei_output',
        '_calculate_stats'
    ]

    for method in required_methods:
        if hasattr(service, method):
            print(f"  ✅ {method} exists")
        else:
            print(f"  ❌ {method} missing")
            return False

    return True


def test_template_manager_structure():
    """Test TemplateManager has required methods"""
    print("\nTesting TemplateManager structure...")

    from app.services.scanning.template_manager import TemplateManager

    manager = TemplateManager()

    required_methods = [
        'list_templates',
        'update_templates',
        'get_template_info',
        'validate_template',
        'get_categories',
        'get_recommended_templates',
        'get_template_stats'
    ]

    for method in required_methods:
        if hasattr(manager, method):
            print(f"  ✅ {method} exists")
        else:
            print(f"  ❌ {method} missing")
            return False

    # Test categories
    categories = manager.get_categories()
    expected_categories = ['cves', 'exposed-panels', 'misconfigurations']

    for cat in expected_categories:
        if cat in categories:
            print(f"  ✅ Category '{cat}' exists")
        else:
            print(f"  ❌ Category '{cat}' missing")
            return False

    return True


def test_suppression_service_structure():
    """Test SuppressionService structure (without DB)"""
    print("\nTesting SuppressionService structure...")

    from app.services.scanning.suppression_service import SuppressionService

    # Can't instantiate without DB, but can check class structure
    required_methods = [
        'should_suppress',
        'create_suppression',
        'update_suppression',
        'delete_suppression',
        'list_suppressions',
        'filter_findings'
    ]

    for method in required_methods:
        if hasattr(SuppressionService, method):
            print(f"  ✅ {method} exists")
        else:
            print(f"  ❌ {method} missing")
            return False

    return True


def test_risk_scoring():
    """Test risk score calculation"""
    print("\nTesting risk score calculation...")

    from app.services.scanning.nuclei_service import calculate_risk_score_from_findings

    # Test cases
    test_cases = [
        # (findings, expected_score)
        ([], 0.0),
        ([{'severity': 'critical'}], 3.0),
        ([{'severity': 'high'}], 2.0),
        ([{'severity': 'medium'}], 1.0),
        ([{'severity': 'low'}], 0.5),
        ([{'severity': 'info'}], 0.1),
        ([
            {'severity': 'critical'},
            {'severity': 'high'},
            {'severity': 'medium'}
        ], 6.0),
        ([
            {'severity': 'critical'},
            {'severity': 'critical'},
            {'severity': 'critical'},
            {'severity': 'high'},
            {'severity': 'high'}
        ], 10.0),  # Should cap at 10.0
    ]

    all_passed = True
    for findings, expected in test_cases:
        score = calculate_risk_score_from_findings(findings)
        if score == expected:
            print(f"  ✅ {len(findings)} findings → {score} (expected {expected})")
        else:
            print(f"  ❌ {len(findings)} findings → {score} (expected {expected})")
            all_passed = False

    return all_passed


def test_nuclei_result_parsing():
    """Test Nuclei result parsing"""
    print("\nTesting Nuclei result parsing...")

    from app.services.scanning.nuclei_service import NucleiService

    service = NucleiService(tenant_id=1)

    # Sample Nuclei JSON output
    sample_result = {
        "template-id": "CVE-2021-44228",
        "info": {
            "name": "Apache Log4j RCE",
            "severity": "critical",
            "description": "Apache Log4j2 JNDI features...",
            "tags": ["cve", "rce", "log4j"],
            "reference": ["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
            "classification": {
                "cvss-metrics": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                "cvss-score": 10.0,
                "cve-id": ["CVE-2021-44228"]
            }
        },
        "matcher-name": "version-check",
        "type": "http",
        "host": "https://example.com",
        "matched-at": "https://example.com/api/login",
        "timestamp": "2024-01-01T12:00:00Z"
    }

    finding = service.parse_nuclei_result(sample_result)

    if finding is None:
        print("  ❌ Failed to parse result")
        return False

    # Validate parsed fields
    checks = [
        (finding['template_id'] == "CVE-2021-44228", "template_id"),
        (finding['name'] == "Apache Log4j RCE", "name"),
        (finding['severity'] == "critical", "severity"),
        (finding['cvss_score'] == 10.0, "cvss_score"),
        (finding['cve_id'] == "CVE-2021-44228", "cve_id"),
        (finding['matched_at'] == "https://example.com/api/login", "matched_at"),
        (finding['host'] == "example.com", "host"),
        (finding['source'] == "nuclei", "source"),
    ]

    all_passed = True
    for check, field in checks:
        if check:
            print(f"  ✅ {field} parsed correctly")
        else:
            print(f"  ❌ {field} parsing failed")
            all_passed = False

    return all_passed


def test_config():
    """Test that Nuclei is enabled in config"""
    print("\nTesting configuration...")

    from app.config import settings

    checks = [
        (settings.feature_nuclei_enabled, "feature_nuclei_enabled"),
        ('nuclei' in settings.tool_allowed_tools, "nuclei in allowed_tools"),
        (settings.discovery_nuclei_timeout > 0, "nuclei_timeout configured"),
    ]

    all_passed = True
    for check, name in checks:
        if check:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name}")
            all_passed = False

    return all_passed


def main():
    """Run all verification tests"""
    print("=" * 70)
    print("NUCLEI INTEGRATION VERIFICATION")
    print("=" * 70)

    tests = [
        ("Module Imports", test_imports),
        ("NucleiService Structure", test_nuclei_service_structure),
        ("TemplateManager Structure", test_template_manager_structure),
        ("SuppressionService Structure", test_suppression_service_structure),
        ("Risk Scoring", test_risk_scoring),
        ("Nuclei Result Parsing", test_nuclei_result_parsing),
        ("Configuration", test_config),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ {name} test raised exception: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ All verification tests passed!")
        print("=" * 70)
        return 0
    else:
        print("❌ Some tests failed - please review above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
