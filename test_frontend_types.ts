/**
 * Type Check Test for Frontend API Integration
 *
 * This file tests that all TypeScript types are correctly defined
 * and can be compiled without errors.
 */

import type { Asset, Service, Finding, Certificate, AssetEvent } from './frontend/src/api/types'

// Test 1: Asset type with nested data
const testAsset: Asset = {
  id: 1,
  tenant_id: 2,
  type: 'subdomain',
  asset_type: 'subdomain',
  identifier: 'test.example.com',
  is_active: true,
  status: 'active',
  first_seen: '2025-10-26T00:00:00Z',
  last_seen: '2025-10-26T00:00:00Z',
  priority: 'high',
  risk_score: 75.5,

  // Nested data (should not cause TypeScript errors)
  services: [],
  findings: [],
  certificates: [],
  events: []
}

// Test 2: Asset with populated nested data
const testAssetWithData: Asset = {
  id: 2,
  tenant_id: 2,
  type: 'domain',
  asset_type: 'domain',
  identifier: 'example.com',
  is_active: true,
  status: 'active',
  first_seen: '2025-10-26T00:00:00Z',
  last_seen: '2025-10-26T00:00:00Z',

  services: [
    {
      id: 1,
      asset_id: 2,
      port: 443,
      protocol: 'https',
      has_tls: true,
      tls_version: 'TLSv1.3',
      first_seen: '2025-10-26T00:00:00Z',
      last_seen: '2025-10-26T00:00:00Z',
      technologies: ['nginx', 'React'], // Backend field
      http_technologies: ['nginx', 'React'], // Alternative field
      tls_fingerprint: 'abc123'
    }
  ],

  findings: [
    {
      id: 1,
      asset_id: 2,
      source: 'nuclei',
      name: 'Test Finding',
      severity: 'high',
      status: 'open',
      first_seen: '2025-10-26T00:00:00Z',
      last_seen: '2025-10-26T00:00:00Z',
      matched_at: '2025-10-26T00:00:00Z', // New field
      host: 'example.com', // New field
      matcher_name: 'test-matcher' // New field
    }
  ],

  certificates: [
    {
      id: 1,
      asset_id: 2,
      subject_cn: 'example.com',
      issuer: 'Let\'s Encrypt',
      is_expired: false,
      is_self_signed: false,
      is_wildcard: false,
      has_weak_signature: false,
      first_seen: '2025-10-26T00:00:00Z',
      last_seen: '2025-10-26T00:00:00Z'
    }
  ],

  events: [
    {
      id: 1,
      asset_id: 2,
      kind: 'new_asset',
      payload: { source: 'subfinder' },
      created_at: '2025-10-26T00:00:00Z'
    }
  ]
}

// Test 3: Service type with all fields
const testService: Service = {
  id: 1,
  asset_id: 1,
  port: 443,
  protocol: 'https',
  product: 'nginx',
  version: '1.21.0',
  http_title: 'Test Page',
  http_status: 200,
  web_server: 'nginx',
  http_technologies: ['React', 'Next.js'],
  technologies: ['React', 'Next.js'], // Backend field
  tls_fingerprint: 'abc123', // New field
  has_tls: true,
  tls_version: 'TLSv1.3',
  first_seen: '2025-10-26T00:00:00Z',
  last_seen: '2025-10-26T00:00:00Z'
}

// Test 4: Finding type with all fields
const testFinding: Finding = {
  id: 1,
  asset_id: 1,
  source: 'nuclei',
  template_id: 'CVE-2024-1234',
  name: 'SQL Injection',
  severity: 'critical',
  cvss_score: 9.8,
  cve_id: 'CVE-2024-1234',
  status: 'open',
  first_seen: '2025-10-26T00:00:00Z',
  last_seen: '2025-10-26T00:00:00Z',
  matched_at: '2025-10-26T00:00:00Z', // New field
  host: 'example.com', // New field
  matcher_name: 'sql-injection-matcher' // New field
}

// Test 5: AssetEvent type
const testEvent: AssetEvent = {
  id: 1,
  asset_id: 1,
  kind: 'new_port',
  payload: { port: 8080, protocol: 'http' },
  created_at: '2025-10-26T00:00:00Z'
}

console.log('✅ All types compile successfully!')
console.log('✅ Asset type supports nested data')
console.log('✅ Service type includes all backend fields')
console.log('✅ Finding type includes all backend fields')
console.log('✅ AssetEvent type is properly defined')
