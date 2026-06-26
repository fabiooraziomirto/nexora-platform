const DEVICE_BASE  = import.meta.env.VITE_DEVICE_SERVICE_URL  ?? ''
const FLEET_BASE   = import.meta.env.VITE_FLEET_SERVICE_URL   ?? ''
const PLUGIN_BASE  = import.meta.env.VITE_PLUGIN_SERVICE_URL  ?? ''
const EXEC_BASE    = import.meta.env.VITE_EXEC_SERVICE_URL    ?? ''
const NET_BASE     = import.meta.env.VITE_NET_SERVICE_URL     ?? ''
const WS_BASE      = import.meta.env.VITE_WS_SERVICE_URL      ?? ''

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

async function patch<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: 'PATCH',
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

export interface DeviceCreate {
  name: string
  device_type: string
  description?: string
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

export interface Plugin {
  id: string
  name: string
  version: string
  module_type: string
  status: string
  artifact_uri: string
  artifact_checksum: string
  runtime_type: string
  entrypoint: string
  timeout_seconds: number
  memory_limit_mb: number
  permissions: string[]
  required_capabilities: string[]
  created_at: string
  updated_at: string
}

export interface PluginListResponse { items: Plugin[]; total: number }

export interface PluginCreate {
  name: string
  version: string
  module_type: string
  artifact_uri: string
  artifact_checksum: string
  runtime_type: string
  entrypoint?: string
  timeout_seconds?: number
  memory_limit_mb?: number
  permissions?: string[]
}

export interface Execution {
  id: string
  device_id: string
  command: string
  status: string
  execution_type: string
  plugin_id: string | null
  args: Record<string, unknown> | null
  invocation_mode: string
  exit_code: number | null
  result_stdout: string
  result_stderr: string
  function_result: unknown
  tenant_id: string
  owner_id: string
  created_at: string
  dispatched_at: string | null
  running_at: string | null
  dispatch_latency_seconds: number | null
}

export interface ExecutionListResponse { items: Execution[]; total: number }

export interface ExecutionCreate {
  device_id: string
  execution_type: string
  command: string
  plugin_id?: string
  args?: Record<string, unknown>
}

export interface Port {
  id: string
  device_id: string
  network_id: string
  status: string
  ip_address: string
}

export interface PortListResponse { items: Port[]; total: number }

export interface PortCreate {
  device_id: string
  network_id: string
  ip_address: string
  status?: string
}

export interface Webservice {
  id: string
  device_id: string
  port: number
  status: string
  hostname: string
  tls_enabled: boolean
}

export interface WebserviceListResponse { items: Webservice[]; total: number }

export interface WebserviceCreate {
  device_id: string
  port: number
  hostname: string
  tls_enabled?: boolean
  status?: string
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

export interface FleetMembersResponse {
  fleet_id: string
  members: { device_id: string }[]
}

// ── API calls ────────────────────────────────────────────────────────────────

export const api = {
  // Devices
  listDevices: (page = 1, page_size = 100) =>
    get<DeviceListResponse>(`${DEVICE_BASE}/api/v2/devices?page=${page}&page_size=${page_size}`),

  getDevice: (id: string) =>
    get<Device>(`${DEVICE_BASE}/api/v2/devices/${id}`),

  createDevice: (body: DeviceCreate) =>
    post<Device>(`${DEVICE_BASE}/api/v2/devices`, body),

  updateDevice: (id: string, body: Partial<DeviceCreate>) =>
    patch<Device>(`${DEVICE_BASE}/api/v2/devices/${id}`, body),

  deleteDevice: (id: string) =>
    del(`${DEVICE_BASE}/api/v2/devices/${id}`),

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

  // Plugins
  listPlugins: (page = 1, page_size = 100) =>
    get<PluginListResponse>(`${PLUGIN_BASE}/api/v2/plugins?page=${page}&page_size=${page_size}`),

  getPlugin: (id: string) =>
    get<Plugin>(`${PLUGIN_BASE}/api/v2/plugins/${id}`),

  createPlugin: (body: PluginCreate) =>
    post<Plugin>(`${PLUGIN_BASE}/api/v2/plugins`, body),

  activatePlugin: (id: string) =>
    patch<Plugin>(`${PLUGIN_BASE}/api/v2/plugins/${id}/activate`, {}),

  deprecatePlugin: (id: string) =>
    patch<Plugin>(`${PLUGIN_BASE}/api/v2/plugins/${id}/deprecate`, {}),

  deletePlugin: (id: string) =>
    del(`${PLUGIN_BASE}/api/v2/plugins/${id}`),

  // Executions
  listExecutions: (page = 1, page_size = 100, device_id?: string) => {
    const q = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (device_id) q.set('device_id', device_id)
    return get<ExecutionListResponse>(`${EXEC_BASE}/api/v2/executions?${q}`)
  },

  createExecution: (body: ExecutionCreate) =>
    post<Execution>(`${EXEC_BASE}/api/v2/executions`, body),

  dispatchExecution: (id: string) =>
    post<Execution>(`${EXEC_BASE}/api/v2/executions/${id}/dispatch`, {}),

  cancelExecution: (id: string) =>
    post<Execution>(`${EXEC_BASE}/api/v2/executions/${id}/cancel`, {}),

  deleteExecution: (id: string) =>
    del(`${EXEC_BASE}/api/v2/executions/${id}`),

  // Ports
  listPorts: (page = 1, page_size = 100) =>
    get<PortListResponse>(`${NET_BASE}/api/v2/ports?page=${page}&page_size=${page_size}`),

  createPort: (body: PortCreate) =>
    post<Port>(`${NET_BASE}/api/v2/ports`, body),

  updatePort: (id: string, body: Partial<Port>) =>
    patch<Port>(`${NET_BASE}/api/v2/ports/${id}`, body),

  deletePort: (id: string) =>
    del(`${NET_BASE}/api/v2/ports/${id}`),

  // Webservices
  listWebservices: (page = 1, page_size = 100) =>
    get<WebserviceListResponse>(`${WS_BASE}/api/v2/webservices?page=${page}&page_size=${page_size}`),

  createWebservice: (body: WebserviceCreate) =>
    post<Webservice>(`${WS_BASE}/api/v2/webservices`, body),

  updateWebservice: (id: string, body: Partial<Webservice>) =>
    patch<Webservice>(`${WS_BASE}/api/v2/webservices/${id}`, body),

  deleteWebservice: (id: string) =>
    del(`${WS_BASE}/api/v2/webservices/${id}`),

  // Fleets
  listFleets: () =>
    get<FleetListResponse>(`${FLEET_BASE}/api/v2/fleets`),

  getFleet: (fleetId: string) =>
    get<Fleet>(`${FLEET_BASE}/api/v2/fleets/${fleetId}`),

  createFleet: (body: { name: string; description?: string }) =>
    post<Fleet>(`${FLEET_BASE}/api/v2/fleets`, body),

  deleteFleet: (fleetId: string) =>
    del(`${FLEET_BASE}/api/v2/fleets/${fleetId}`),

  getFleetHealth: (fleetId: string) =>
    get<FleetHealthResponse>(`${FLEET_BASE}/api/v2/fleets/${fleetId}/health`),

  getFleetMembers: (fleetId: string) =>
    get<FleetMembersResponse>(`${FLEET_BASE}/api/v2/fleets/${fleetId}/members`),

  addFleetMember: (fleetId: string, deviceId: string) =>
    post<unknown>(`${FLEET_BASE}/api/v2/fleets/${fleetId}/members`, { device_id: deviceId }),

  removeFleetMember: (fleetId: string, deviceId: string) =>
    del(`${FLEET_BASE}/api/v2/fleets/${fleetId}/members/${deviceId}`),
}
