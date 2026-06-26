const DEVICE_BASE = import.meta.env.VITE_DEVICE_SERVICE_URL ?? ''
const FLEET_BASE  = import.meta.env.VITE_FLEET_SERVICE_URL  ?? ''

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${url}`)
  return r.json() as Promise<T>
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

async function del(url: string): Promise<void> {
  const r = await fetch(url, { method: 'DELETE' })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface Device {
  id: string
  name: string
  device_type: string
  status: 'online' | 'offline' | 'unknown'
  description?: string
  last_seen?: string
}

export interface DeviceListResponse {
  items: Device[]
  total: number
}

export interface TelemetrySample {
  id: string
  device_id: string
  metric: string
  value: number
  ts: string
  tags?: Record<string, string>
}

export interface TelemetryQueryResponse {
  device_id: string
  samples: TelemetrySample[]
  count: number
}

export interface TelemetryLatestResponse {
  device_id: string
  readings: Record<string, { value: number; ts: string; tags?: Record<string, string> }>
}

export interface SLO {
  id: string
  device_id: string
  metric: string
  operator: string
  threshold: number
  description?: string
  enabled: boolean
  created_at: string
}

export interface SLOViolation {
  id: string
  slo_id: string
  device_id: string
  metric: string
  observed_value: number
  threshold: number
  operator: string
  violated_at: string
}

export interface Fleet {
  id: string
  name: string
  description?: string
}

export interface FleetListResponse {
  items: Fleet[]
  total: number
}

export interface FleetHealthDevice {
  device_id: string
  name?: string
  status: string
  last_seen?: string
  device_type?: string
}

export interface FleetHealthResponse {
  fleet_id: string
  fleet_name: string
  summary: { online: number; offline: number; unknown: number; total: number }
  devices: FleetHealthDevice[]
}

// ── API calls ────────────────────────────────────────────────────────────────

export const api = {
  // Devices
  listDevices: (page = 1, page_size = 50) =>
    get<DeviceListResponse>(`${DEVICE_BASE}/api/v2/devices?page=${page}&page_size=${page_size}`),

  getDevice: (id: string) =>
    get<Device>(`${DEVICE_BASE}/api/v2/devices/${id}`),

  // Telemetry
  getTelemetry: (deviceId: string, metric?: string, hours = 24) => {
    const q = new URLSearchParams({ hours: String(hours), limit: '500' })
    if (metric) q.set('metric', metric)
    return get<TelemetryQueryResponse>(`${DEVICE_BASE}/api/v2/devices/${deviceId}/telemetry?${q}`)
  },

  getLatestTelemetry: (deviceId: string) =>
    get<TelemetryLatestResponse>(`${DEVICE_BASE}/api/v2/devices/${deviceId}/telemetry/latest`),

  // SLOs
  listSLOs: (deviceId: string) =>
    get<SLO[]>(`${DEVICE_BASE}/api/v2/devices/${deviceId}/slos`),

  listViolations: (deviceId: string, hours = 24) =>
    get<SLOViolation[]>(`${DEVICE_BASE}/api/v2/devices/${deviceId}/slos/violations?hours=${hours}`),

  createSLO: (deviceId: string, body: Omit<SLO, 'id' | 'device_id' | 'enabled' | 'created_at'>) =>
    post<SLO>(`${DEVICE_BASE}/api/v2/devices/${deviceId}/slos`, body),

  deleteSLO: (deviceId: string, sloId: string) =>
    del(`${DEVICE_BASE}/api/v2/devices/${deviceId}/slos/${sloId}`),

  // Fleets
  listFleets: () =>
    get<FleetListResponse>(`${FLEET_BASE}/api/v2/fleets`),

  getFleetHealth: (fleetId: string) =>
    get<FleetHealthResponse>(`${FLEET_BASE}/api/v2/fleets/${fleetId}/health`),
}
