// Auth types
export interface User {
  id: number
  email: string
  username: string
  full_name?: string
  is_active: boolean
  is_superuser: boolean
  created_at: string
  last_login?: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface RefreshResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// Tenant types
export interface Tenant {
  id: number
  name: string
  slug: string
  description?: string
  is_active: boolean
  created_at: string
  updated_at?: string
}

// Asset types
export interface Asset {
  id: number
  tenant_id: number
  type: 'domain' | 'subdomain' | 'ip' | 'url' | 'service'
  asset_type: string  // For compatibility
  identifier: string
  priority?: string
  risk_score?: number
  enrichment_status?: string
  is_active: boolean
  status: string  // For compatibility
  first_seen: string
  last_seen: string
  ip_address?: string
  last_enriched_at?: string
  priority_updated_at?: string
  priority_auto_calculated?: boolean
  service_count?: number
  certificate_count?: number
  endpoint_count?: number
  finding_count?: number
  metadata?: Record<string, any>
  // Nested data for detail view
  services?: Service[]
  findings?: Finding[]
  certificates?: Certificate[]
  events?: AssetEvent[]
}

// Asset Event types
export interface AssetEvent {
  id: number
  asset_id: number
  kind: string
  payload?: Record<string, any>
  created_at: string
}

// Finding types
export interface Finding {
  id: number
  asset_id: number
  source: string
  template_id?: string
  name: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  cvss_score?: number
  cve_id?: string
  evidence?: Record<string, any>
  first_seen: string
  last_seen: string
  status: 'open' | 'suppressed' | 'fixed'
  asset_identifier?: string
  asset_type?: string
  matched_at?: string
  host?: string
  matcher_name?: string
}

// Certificate types
export interface Certificate {
  id: number
  asset_id: number
  subject_cn?: string
  issuer?: string
  serial_number?: string
  not_before?: string
  not_after?: string
  is_expired: boolean
  days_until_expiry?: number
  san_domains?: string[]
  signature_algorithm?: string
  public_key_algorithm?: string
  public_key_bits?: number
  is_self_signed: boolean
  is_wildcard: boolean
  has_weak_signature: boolean
  first_seen: string
  last_seen: string
}

// Service types
export interface Service {
  id: number
  asset_id: number
  port?: number
  protocol?: string
  product?: string
  version?: string
  http_title?: string
  http_status?: number
  web_server?: string
  http_technologies?: string[]
  technologies?: string[]  // Backend uses this field
  tls_fingerprint?: string
  has_tls: boolean
  tls_version?: string
  first_seen: string
  last_seen: string
}

// Dashboard stats
export interface TenantStats {
  total_assets: number
  assets_by_type: Record<string, number>
  total_services: number
  total_certificates: number
  total_endpoints: number
  total_findings: number
  findings_by_severity: Record<string, number>
  open_findings: number
  critical_findings: number
  high_findings: number
  expiring_certificates: number
  average_risk_score: number
}

export interface RecentActivity {
  id: number
  type: string
  description: string
  timestamp: string
  metadata?: Record<string, any>
}

export interface DashboardStats {
  tenant: Tenant
  stats: TenantStats
  recent_activity: RecentActivity[]
  trending_assets: any[]
  risk_distribution: Record<string, number>
}

// Paginated response
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
