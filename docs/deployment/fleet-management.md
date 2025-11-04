# Fleet Management Advanced Guide - Stack4Things v2.0

## 🎯 Overview

Stack4Things v2.0 implementa un sistema avanzato di gestione flotte che permette:
- Bulk operations su dispositivi
- Fleet hierarchy (nested fleets)
- Fleet policies e auto-management
- Fleet health monitoring
- Fleet analytics e statistics

## 🏗️ Fleet Architecture

```
┌─────────────────────────────────────────┐
│   Fleet Hierarchy                      │
│                                          │
│  ┌──────────────────────────────────┐  │
│  │  Production Fleet (root)          │  │
│  │  ┌──────────────────────────────┐ │  │
│  │  │  Edge Fleet (nested)         │ │  │
│  │  │  - Device 1                  │ │  │
│  │  │  - Device 2                  │ │  │
│  │  └──────────────────────────────┘ │  │
│  │  ┌──────────────────────────────┐ │  │
│  │  │  Cloud Fleet (nested)         │ │  │
│  │  │  - Device 3                  │ │  │
│  │  │  - Device 4                  │ │  │
│  │  └──────────────────────────────┘ │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## 📋 Fleet Model

### Database Schema

```python
# models/fleet.py
class Fleet(Base):
    __tablename__ = "fleets"
    
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    project_id = Column(String(36), nullable=False)
    owner_id = Column(String(36), nullable=False)
    
    # Hierarchy
    parent_fleet_id = Column(String(36), ForeignKey('fleets.uuid'), nullable=True)
    
    # Fleet metadata
    tags = Column(JSON)  # ["production", "edge", "sensor"]
    metadata = Column(JSON)
    
    # Policies
    auto_add_policy = Column(JSON)  # Criteria per auto-add devices
    health_policy = Column(JSON)  # Health check criteria
    
    # Statistics
    device_count = Column(Integer, default=0)
    online_count = Column(Integer, default=0)
    last_health_check = Column(DateTime)
    
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Relationships
    devices = relationship("FleetDevice", back_populates="fleet")
    child_fleets = relationship("Fleet", backref="parent_fleet")

class FleetDevice(Base):
    __tablename__ = "fleet_devices"
    
    id = Column(Integer, primary_key=True)
    fleet_id = Column(String(36), ForeignKey('fleets.uuid'))
    device_id = Column(String(36), ForeignKey('devices.uuid'))
    added_at = Column(DateTime)
    added_by = Column(String(36))
    
    # Fleet-specific device metadata
    device_role = Column(String(50))  # "manager", "worker", "monitor"
    device_tags = Column(JSON)
```

## 🔧 Fleet Operations

### Bulk Operations

```python
# services/fleet-service/src/fleet_service/operations.py
class FleetOperations:
    async def deploy_plugin_to_fleet(
        self,
        fleet_id: str,
        plugin_id: str,
        parameters: dict = None
    ) -> FleetOperation:
        """Deploy plugin to all devices in fleet"""
        
        fleet = await Fleet.get_by_uuid(fleet_id)
        devices = await fleet.get_devices()
        
        operation = FleetOperation(
            fleet_id=fleet_id,
            operation_type="plugin_deploy",
            status="running",
            total_devices=len(devices),
            completed_devices=0
        )
        await operation.save()
        
        # Execute in parallel
        results = []
        for device in devices:
            try:
                result = await execution_service.execute_plugin(
                    device_id=device.uuid,
                    plugin_id=plugin_id,
                    parameters=parameters
                )
                results.append({
                    'device_id': device.uuid,
                    'status': 'success',
                    'result': result
                })
            except Exception as e:
                results.append({
                    'device_id': device.uuid,
                    'status': 'error',
                    'error': str(e)
                })
            
            operation.completed_devices += 1
            await operation.save()
        
        operation.status = "completed"
        operation.results = results
        await operation.save()
        
        return operation
    
    async def execute_command_on_fleet(
        self,
        fleet_id: str,
        command: str,
        parameters: dict = None
    ) -> FleetOperation:
        """Execute command on all devices in fleet"""
        # Similar implementation
        pass
    
    async def get_fleet_health(self, fleet_id: str) -> FleetHealth:
        """Get fleet health status"""
        fleet = await Fleet.get_by_uuid(fleet_id)
        devices = await fleet.get_devices()
        
        online_count = sum(1 for d in devices if d.status == "ONLINE")
        offline_count = len(devices) - online_count
        
        return FleetHealth(
            fleet_id=fleet_id,
            total_devices=len(devices),
            online_devices=online_count,
            offline_devices=offline_count,
            health_percentage=(online_count / len(devices) * 100) if devices else 0
        )
```

## 📊 Fleet API

### Extended Fleet Endpoints

```python
# services/fleet-service/src/fleet_service/api/v2/fleets.py

@router.post("/fleets/{fleet_id}/deploy")
async def deploy_to_fleet(
    fleet_id: UUID,
    deployment: FleetDeployment,
    request: Request
):
    """Deploy plugin/configuration to fleet"""
    # RBAC check
    require_permission("iot:fleet:deploy")
    
    if deployment.type == "plugin":
        operation = await fleet_ops.deploy_plugin_to_fleet(
            fleet_id, deployment.plugin_id, deployment.parameters
        )
    elif deployment.type == "command":
        operation = await fleet_ops.execute_command_on_fleet(
            fleet_id, deployment.command, deployment.parameters
        )
    
    return operation

@router.get("/fleets/{fleet_id}/health")
async def get_fleet_health(fleet_id: UUID):
    """Get fleet health status"""
    health = await fleet_ops.get_fleet_health(fleet_id)
    return health

@router.get("/fleets/{fleet_id}/statistics")
async def get_fleet_statistics(fleet_id: UUID):
    """Get fleet statistics"""
    stats = await fleet_service.get_statistics(fleet_id)
    return stats

@router.post("/fleets/{fleet_id}/policies")
async def set_fleet_policy(fleet_id: UUID, policy: FleetPolicy):
    """Set fleet policy (auto-add, health checks, etc.)"""
    await fleet_service.set_policy(fleet_id, policy)
    return {"status": "ok"}

@router.post("/fleets/{fleet_id}/devices/bulk")
async def bulk_add_devices(
    fleet_id: UUID,
    device_ids: List[UUID]
):
    """Bulk add devices to fleet"""
    await fleet_service.add_devices(fleet_id, device_ids)
    return {"status": "ok", "added": len(device_ids)}
```

## 🔍 Fleet Policies

### Auto-Add Policy

```python
# Auto-add devices based on criteria
class AutoAddPolicy:
    def __init__(self, criteria: dict):
        self.criteria = criteria
    
    def matches(self, device: Device) -> bool:
        """Check if device matches criteria"""
        if 'tags' in self.criteria:
            if not all(tag in device.tags for tag in self.criteria['tags']):
                return False
        
        if 'location' in self.criteria:
            if device.location != self.criteria['location']:
                return False
        
        if 'device_type' in self.criteria:
            if device.device_type != self.criteria['device_type']:
                return False
        
        return True

# Usage
fleet.auto_add_policy = {
    "tags": ["production", "edge"],
    "device_type": "raspberry-pi"
}

# When device registered, check policies
if fleet.auto_add_policy:
    policy = AutoAddPolicy(fleet.auto_add_policy)
    if policy.matches(device):
        await fleet.add_device(device)
```

## 📈 Fleet Analytics

### Statistics Collection

```python
class FleetStatistics:
    async def collect_statistics(self, fleet_id: str) -> dict:
        """Collect fleet statistics"""
        fleet = await Fleet.get_by_uuid(fleet_id)
        devices = await fleet.get_devices()
        
        # Device status distribution
        status_dist = {}
        for device in devices:
            status_dist[device.status] = status_dist.get(device.status, 0) + 1
        
        # Device type distribution
        type_dist = {}
        for device in devices:
            type_dist[device.device_type] = type_dist.get(device.device_type, 0) + 1
        
        # Plugin usage
        plugin_usage = {}
        for device in devices:
            plugins = await device.get_plugins()
            for plugin in plugins:
                plugin_usage[plugin.name] = plugin_usage.get(plugin.name, 0) + 1
        
        # Network stats (if WireGuard enabled)
        network_stats = {}
        if fleet.wireguard_enabled:
            for device in devices:
                wg_status = await wireguard_api.get_peer_status(device.uuid)
                network_stats[device.uuid] = {
                    "connected": wg_status.connected,
                    "transfer_rx": wg_status.transfer_rx,
                    "transfer_tx": wg_status.transfer_tx
                }
        
        return {
            "fleet_id": fleet_id,
            "total_devices": len(devices),
            "status_distribution": status_dist,
            "type_distribution": type_dist,
            "plugin_usage": plugin_usage,
            "network_stats": network_stats,
            "health_score": self.calculate_health_score(fleet),
            "last_updated": datetime.utcnow()
        }
```

## 🔐 RBAC per Fleet

### Fleet Permissions

```python
# Fleet-specific RBAC
FLEET_POLICIES = {
    "iot:fleet:get": "role:user_iot",
    "iot:fleet:create": "role:manager_iot_project",
    "iot:fleet:update": "role:fleet_manager or role:manager_iot_project",
    "iot:fleet:delete": "role:admin_iot_project",
    "iot:fleet:add_device": "role:fleet_manager",
    "iot:fleet:remove_device": "role:fleet_manager",
    "iot:fleet:deploy": "role:fleet_manager",
    "iot:fleet:execute": "role:fleet_manager",
    "iot:fleet:manage": "role:fleet_manager",
}

# Resource-level: Fleet ownership
class FleetPermission(Base):
    __tablename__ = "fleet_permissions"
    
    id = Column(Integer, primary_key=True)
    fleet_id = Column(String(36), ForeignKey('fleets.uuid'))
    user_id = Column(String(36))
    role = Column(String(50))  # "manager", "operator", "viewer"
    permissions = Column(JSON)  # ["deploy", "execute", "manage"]
```

## 🧪 Testing Fleet Operations

```python
# tests/fleet/test_fleet_operations.py
@pytest.mark.asyncio
async def test_deploy_plugin_to_fleet():
    fleet = await create_test_fleet()
    device1 = await create_test_device()
    device2 = await create_test_device()
    await fleet.add_devices([device1, device2])
    
    plugin = await create_test_plugin()
    
    operation = await fleet_ops.deploy_plugin_to_fleet(
        fleet.uuid, plugin.uuid
    )
    
    assert operation.status == "completed"
    assert operation.total_devices == 2
    assert operation.completed_devices == 2
    assert len(operation.results) == 2
```

## 📚 References

- [Fleet Management Patterns](https://docs.aws.amazon.com/iot/latest/developerguide/iot-thing-groups.html)
- [Bulk Operations Best Practices](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/)


