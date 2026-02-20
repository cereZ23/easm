/**
 * COMPREHENSIVE EASM UI TEST SCRIPT
 *
 * Run this in browser console at http://localhost:13000
 *
 * This script will:
 * 1. Test all API endpoints
 * 2. Check component rendering
 * 3. Verify data flow
 * 4. Test authentication
 * 5. Report all issues found
 */

const API_BASE = 'http://localhost:18000';

const testResults = {
    passed: [],
    failed: [],
    warnings: []
};

function logTest(name, passed, details) {
    const result = { name, details, timestamp: new Date().toISOString() };
    if (passed) {
        testResults.passed.push(result);
        console.log(`✅ PASS: ${name}`, details);
    } else {
        testResults.failed.push(result);
        console.error(`❌ FAIL: ${name}`, details);
    }
}

function logWarning(name, details) {
    testResults.warnings.push({ name, details, timestamp: new Date().toISOString() });
    console.warn(`⚠️  WARN: ${name}`, details);
}

async function testAPI() {
    console.log('\n🔍 TESTING API CONNECTIVITY\n');

    try {
        const response = await fetch(`${API_BASE}/`);
        const data = await response.json();
        logTest('API Root Endpoint', response.ok, data);
    } catch (error) {
        logTest('API Root Endpoint', false, { error: error.message });
        return false;
    }

    return true;
}

async function testLogin() {
    console.log('\n🔐 TESTING AUTHENTICATION\n');

    try {
        const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: 'admin@example.com',
                password: 'admin123'
            })
        });

        const data = await response.json();

        if (response.ok && data.access_token) {
            logTest('Login Success', true, {
                user: data.user,
                hasToken: true
            });
            window.TEST_TOKEN = data.access_token;
            window.TEST_USER = data.user;
            return data.access_token;
        } else {
            logTest('Login Failed', false, data);
            return null;
        }
    } catch (error) {
        logTest('Login Error', false, { error: error.message });
        return null;
    }
}

async function testTenants(token) {
    console.log('\n🏢 TESTING TENANT ENDPOINTS\n');

    try {
        const response = await fetch(`${API_BASE}/api/v1/tenants`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (response.ok && Array.isArray(data)) {
            logTest('Fetch Tenants', true, {
                count: data.length,
                tenants: data
            });

            if (data.length > 0) {
                window.TEST_TENANT_ID = data[0].id;
                return data[0].id;
            }
        } else {
            logTest('Fetch Tenants', false, data);
        }
    } catch (error) {
        logTest('Fetch Tenants Error', false, { error: error.message });
    }

    return null;
}

async function testDashboard(token, tenantId) {
    console.log('\n📊 TESTING DASHBOARD\n');

    try {
        const response = await fetch(`${API_BASE}/api/v1/tenants/${tenantId}/dashboard`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (response.ok) {
            logTest('Dashboard Data', true, data);

            // Check for expected fields
            if (!data.stats) {
                logWarning('Dashboard Missing Stats', 'stats field is missing');
            }
            if (!data.tenant) {
                logWarning('Dashboard Missing Tenant', 'tenant field is missing');
            }
        } else {
            logTest('Dashboard Data', false, data);
        }
    } catch (error) {
        logTest('Dashboard Error', false, { error: error.message });
    }
}

async function testAssets(token, tenantId) {
    console.log('\n🌐 TESTING ASSETS ENDPOINT\n');

    try {
        const response = await fetch(`${API_BASE}/api/v1/tenants/${tenantId}/assets?page=1&page_size=10`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (response.ok) {
            logTest('Fetch Assets', true, {
                total: data.total,
                page: data.page,
                itemCount: data.items?.length,
                firstAsset: data.items?.[0]
            });
        } else {
            logTest('Fetch Assets', false, data);
        }
    } catch (error) {
        logTest('Fetch Assets Error', false, { error: error.message });
    }
}

async function testFindings(token, tenantId) {
    console.log('\n⚠️  TESTING FINDINGS ENDPOINT\n');

    try {
        const response = await fetch(`${API_BASE}/api/v1/tenants/${tenantId}/findings?page=1&page_size=10`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (response.ok) {
            logTest('Fetch Findings', true, {
                total: data.total,
                page: data.page,
                itemCount: data.items?.length,
                firstFinding: data.items?.[0]
            });

            if (data.total === 0) {
                logWarning('No Findings', 'Expected findings from testasp.vulnweb.com');
            }
        } else {
            logTest('Fetch Findings', false, data);
        }
    } catch (error) {
        logTest('Fetch Findings Error', false, { error: error.message });
    }
}

async function testServices(token, tenantId) {
    console.log('\n🔌 TESTING SERVICES ENDPOINT\n');

    try {
        const response = await fetch(`${API_BASE}/api/v1/tenants/${tenantId}/services?page=1&page_size=10`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (response.ok) {
            logTest('Fetch Services', true, {
                total: data.total,
                page: data.page,
                itemCount: data.items?.length,
                firstService: data.items?.[0]
            });
        } else {
            logTest('Fetch Services', false, data);
        }
    } catch (error) {
        logTest('Fetch Services Error', false, { error: error.message });
    }
}

async function testCertificates(token, tenantId) {
    console.log('\n🔒 TESTING CERTIFICATES ENDPOINT\n');

    try {
        const response = await fetch(`${API_BASE}/api/v1/tenants/${tenantId}/certificates?page=1&page_size=10`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (response.ok) {
            logTest('Fetch Certificates', true, {
                total: data.total,
                page: data.page,
                itemCount: data.items?.length,
                firstCert: data.items?.[0]
            });
        } else {
            logTest('Fetch Certificates', false, data);
        }
    } catch (error) {
        logTest('Fetch Certificates Error', false, { error: error.message });
    }
}

async function checkVueApp() {
    console.log('\n⚛️  CHECKING VUE APPLICATION\n');

    // Check if Vue app exists
    const app = document.getElementById('app');
    if (!app) {
        logTest('Vue App Element', false, 'No #app element found');
        return false;
    } else {
        logTest('Vue App Element', true, 'Found #app element');
    }

    // Check if Vue is loaded
    if (window.__VUE__) {
        logTest('Vue Runtime', true, 'Vue is loaded');
    } else {
        logWarning('Vue Runtime', 'Vue devtools not detected (might be production mode)');
    }

    // Check for router
    const routerLinks = document.querySelectorAll('a[href^="/"]');
    if (routerLinks.length > 0) {
        logTest('Vue Router', true, `Found ${routerLinks.length} router links`);
    } else {
        logWarning('Vue Router', 'No router links found');
    }

    // Check for Pinia store (look for data attributes or specific classes)
    const hasStore = !!localStorage.getItem('accessToken') || !!localStorage.getItem('theme');
    logTest('Pinia Store (localStorage check)', hasStore, {
        hasToken: !!localStorage.getItem('accessToken'),
        hasTheme: !!localStorage.getItem('theme')
    });

    return true;
}

function checkConsoleErrors() {
    console.log('\n🐛 CHECKING FOR CONSOLE ERRORS\n');

    // This is informational - can't reliably check past errors
    logWarning('Console Errors', 'Check browser console for any JavaScript errors manually');
}

function checkNetworkErrors() {
    console.log('\n🌐 CHECKING FOR NETWORK ERRORS\n');

    logWarning('Network Errors', 'Open DevTools Network tab and check for failed requests');
}

function checkDOMRendering() {
    console.log('\n🎨 CHECKING DOM RENDERING\n');

    // Check if main navigation exists
    const nav = document.querySelector('nav');
    if (nav) {
        logTest('Navigation Element', true, 'Found nav element');
    } else {
        logTest('Navigation Element', false, 'No nav element found');
    }

    // Check for sidebar
    const sidebar = document.querySelector('aside');
    if (sidebar) {
        logTest('Sidebar Element', true, 'Found aside element');
    } else {
        logWarning('Sidebar Element', 'No aside element found - might be on login page');
    }

    // Check for main content
    const main = document.querySelector('main');
    if (main) {
        logTest('Main Content', true, 'Found main element');
    } else {
        logWarning('Main Content', 'No main element found - might be on login page');
    }
}

function printSummary() {
    console.log('\n\n═══════════════════════════════════════════════════');
    console.log('📊 TEST SUMMARY');
    console.log('═══════════════════════════════════════════════════\n');

    console.log(`✅ Passed: ${testResults.passed.length}`);
    console.log(`❌ Failed: ${testResults.failed.length}`);
    console.log(`⚠️  Warnings: ${testResults.warnings.length}`);
    console.log(`📈 Total: ${testResults.passed.length + testResults.failed.length}\n`);

    if (testResults.failed.length > 0) {
        console.log('❌ FAILED TESTS:');
        testResults.failed.forEach(test => {
            console.log(`   • ${test.name}`);
            console.log(`     ${JSON.stringify(test.details)}`);
        });
        console.log('');
    }

    if (testResults.warnings.length > 0) {
        console.log('⚠️  WARNINGS:');
        testResults.warnings.forEach(warn => {
            console.log(`   • ${warn.name}: ${JSON.stringify(warn.details)}`);
        });
        console.log('');
    }

    const successRate = ((testResults.passed.length / (testResults.passed.length + testResults.failed.length)) * 100).toFixed(1);
    console.log(`Success Rate: ${successRate}%`);

    console.log('\n═══════════════════════════════════════════════════\n');

    // Return results for programmatic access
    return testResults;
}

async function runAllTests() {
    console.clear();
    console.log('═══════════════════════════════════════════════════');
    console.log('🚀 EASM UI COMPREHENSIVE TEST SUITE');
    console.log('═══════════════════════════════════════════════════\n');

    // Reset results
    testResults.passed = [];
    testResults.failed = [];
    testResults.warnings = [];

    // Test API connectivity
    const apiOk = await testAPI();
    if (!apiOk) {
        console.error('❌ API is not reachable. Stopping tests.');
        return printSummary();
    }

    // Test authentication
    const token = await testLogin();
    if (!token) {
        console.error('❌ Authentication failed. Stopping tests.');
        return printSummary();
    }

    // Test tenant loading
    const tenantId = await testTenants(token);
    if (!tenantId) {
        console.error('❌ No tenants found. Stopping tests.');
        return printSummary();
    }

    // Test all endpoints
    await testDashboard(token, tenantId);
    await testAssets(token, tenantId);
    await testFindings(token, tenantId);
    await testServices(token, tenantId);
    await testCertificates(token, tenantId);

    // Check frontend
    await checkVueApp();
    checkDOMRendering();
    checkConsoleErrors();
    checkNetworkErrors();

    // Print summary
    return printSummary();
}

// Export to window for easy access
window.runEASMTests = runAllTests;
window.testResults = testResults;

console.log('');
console.log('✅ Test script loaded!');
console.log('');
console.log('Run tests by calling: runEASMTests()');
console.log('Or just copy-paste: window.runEASMTests()');
console.log('');

// Auto-run if desired
// Uncomment the next line to auto-run:
// runAllTests();
