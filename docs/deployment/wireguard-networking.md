# WireGuard Virtual Networking Guide - Stack4Things v2.0

## 🎯 Overview

Stack4Things v2.0 utilizza **WireGuard** per creare una rete virtuale sicura tra dispositivi IoT e cloud infrastructure, bypassando NAT e firewall.

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│         Kubernetes Cluster                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  WireGuard Gateway Service                           │  │
│  │  - WireGuard Server (wg0)                            │  │
│  │  - Management API                                     │  │
│  │  - Config Generator                                  │  │
│  │  - Peer Manager                                      │  │
│  │  IP: 10.8.0.1/16                                     │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────────────────────┘
               │ WireGuard Tunnel (UDP 51820)
               │
┌──────────────▼──────────────────────────────────────────────┐
│         IoT Devices                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Device 1 - WireGuard Client                         │  │
│  │  IP: 10.8.0.10/32                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Device 2 - WireGuard Client                         │  │
│  │  IP: 10.8.0.11/32                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Device N - WireGuard Client                          │  │
│  │  IP: 10.8.0.N/32                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 WireGuard Gateway Service

### Service Structure

```python
# services/wireguard-gateway-service/
services/wireguard-gateway-service/
├── src/
│   └── wireguard_gateway/
│       ├── main.py
│       ├── api/
│       │   └── v1/
│       │       ├── peers.py
│       │       ├── configs.py
│       │       └── stats.py
│       ├── core/
│       │   ├── wireguard.py    # WireGuard server management
│       │   ├── key_manager.py  # Key generation/management
│       │   └── config_gen.py    # Config generation
│       └── models/
│           └── peer.py
├── Dockerfile
└── k8s/
    ├── deployment.yaml
    └── service.yaml
```

### WireGuard Server Management

```python
# services/wireguard-gateway-service/src/wireguard_gateway/core/wireguard.py
import subprocess
import json
from typing import List, Dict

class WireGuardManager:
    def __init__(self, interface: str = "wg0"):
        self.interface = interface
        self.config_path = f"/etc/wireguard/{interface}.conf"
    
    def add_peer(self, public_key: str, allowed_ips: str) -> bool:
        """Add peer to WireGuard configuration"""
        cmd = [
            "wg", "set", self.interface,
            "peer", public_key,
            "allowed-ips", allowed_ips
        ]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def remove_peer(self, public_key: str) -> bool:
        """Remove peer from WireGuard"""
        cmd = [
            "wg", "set", self.interface,
            "peer", public_key, "remove"
        ]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def get_peers(self) -> List[Dict]:
        """Get all peers and their status"""
        cmd = ["wg", "show", self.interface, "dump"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        peers = []
        for line in result.stdout.strip().split('\n')[1:]:  # Skip interface line
            parts = line.split('\t')
            if len(parts) >= 4:
                peers.append({
                    'public_key': parts[0],
                    'allowed_ips': parts[3],
                    'latest_handshake': parts[4] if len(parts) > 4 else None,
                    'transfer_rx': parts[5] if len(parts) > 5 else None,
                    'transfer_tx': parts[6] if len(parts) > 6 else None,
                })
        return peers
    
    def reload_config(self) -> bool:
        """Reload WireGuard configuration"""
        cmd = ["wg-quick", "down", self.interface]
        subprocess.run(cmd)
        cmd = ["wg-quick", "up", self.interface]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
```

### Key Management

```python
# services/wireguard-gateway-service/src/wireguard_gateway/core/key_manager.py
import subprocess
import secrets
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization

class KeyManager:
    def generate_keypair(self) -> tuple[str, str]:
        """Generate WireGuard keypair"""
        # Generate private key
        private_key = subprocess.run(
            ["wg", "genkey"],
            capture_output=True,
            text=True
        ).stdout.strip()
        
        # Generate public key from private
        public_key = subprocess.run(
            ["wg", "pubkey"],
            input=private_key,
            capture_output=True,
            text=True
        ).stdout.strip()
        
        return private_key, public_key
    
    def store_keypair(self, device_id: str, private_key: str, public_key: str):
        """Store keypair securely (Vault/Secrets)"""
        # Store in Vault or Kubernetes Secrets
        pass
    
    def get_keypair(self, device_id: str) -> tuple[str, str]:
        """Retrieve keypair for device"""
        # Get from Vault/Kubernetes Secrets
        pass
```

### Config Generator

```python
# services/wireguard-gateway-service/src/wireguard_gateway/core/config_gen.py
class ConfigGenerator:
    def __init__(self, gateway_endpoint: str, gateway_public_key: str):
        self.gateway_endpoint = gateway_endpoint
        self.gateway_public_key = gateway_public_key
    
    def generate_device_config(
        self,
        device_id: str,
        device_private_key: str,
        device_ip: str
    ) -> str:
        """Generate WireGuard config for device"""
        config = f"""[Interface]
PrivateKey = {device_private_key}
Address = {device_ip}/32
DNS = 10.8.0.1

[Peer]
PublicKey = {self.gateway_public_key}
Endpoint = {self.gateway_endpoint}:51820
AllowedIPs = 10.8.0.0/16
PersistentKeepalive = 25
"""
        return config
    
    def generate_qr_code(self, config: str) -> bytes:
        """Generate QR code for mobile setup"""
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(config)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        # Convert to bytes
        return img.tobytes()
```

## 🚀 API Endpoints

### WireGuard Gateway API

```python
# services/wireguard-gateway-service/src/wireguard_gateway/api/v1/peers.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/wireguard", tags=["wireguard"])

class PeerCreate(BaseModel):
    device_id: str
    device_name: str
    project_id: str

class PeerResponse(BaseModel):
    device_id: str
    public_key: str
    ip_address: str
    config: str
    qr_code: str  # Base64 encoded

@router.post("/peers", response_model=PeerResponse)
async def create_peer(peer_data: PeerCreate):
    """Create WireGuard peer for device"""
    # Generate keypair
    private_key, public_key = key_manager.generate_keypair()
    
    # Allocate IP
    ip_address = ip_allocator.allocate_ip(peer_data.device_id)
    
    # Add to WireGuard
    wg_manager.add_peer(public_key, f"{ip_address}/32")
    
    # Generate config
    config = config_gen.generate_device_config(
        peer_data.device_id,
        private_key,
        ip_address
    )
    
    # Generate QR code
    qr_code = config_gen.generate_qr_code(config)
    
    # Store in database
    peer = Peer(
        device_id=peer_data.device_id,
        public_key=public_key,
        ip_address=ip_address,
        project_id=peer_data.project_id
    )
    await peer.save()
    
    return PeerResponse(
        device_id=peer_data.device_id,
        public_key=public_key,
        ip_address=ip_address,
        config=config,
        qr_code=base64.b64encode(qr_code).decode()
    )

@router.delete("/peers/{device_id}")
async def delete_peer(device_id: str):
    """Remove WireGuard peer"""
    peer = await Peer.get_by_device_id(device_id)
    wg_manager.remove_peer(peer.public_key)
    await peer.delete()

@router.get("/peers/{device_id}/status")
async def get_peer_status(device_id: str):
    """Get peer connection status"""
    peer = await Peer.get_by_device_id(device_id)
    peers = wg_manager.get_peers()
    
    peer_status = next(
        (p for p in peers if p['public_key'] == peer.public_key),
        None
    )
    
    return {
        "device_id": device_id,
        "connected": peer_status is not None,
        "latest_handshake": peer_status.get('latest_handshake') if peer_status else None,
        "transfer_rx": peer_status.get('transfer_rx') if peer_status else None,
        "transfer_tx": peer_status.get('transfer_tx') if peer_status else None,
    }
```

## 🔄 Integration con Device Service

### Auto-Configuration Device

```python
# Quando device si registra, automaticamente setup WireGuard
async def register_device(device_id: str, device_code: str):
    # ... registration logic ...
    
    # Create WireGuard peer
    wireguard_api = WireGuardAPIClient()
    peer_config = await wireguard_api.create_peer(
        device_id=device_id,
        device_name=device.name,
        project_id=device.project_id
    )
    
    # Push config to device via WAMP
    await wamp_agent.send_config(
        device_id,
        {
            "wireguard": {
                "config": peer_config.config,
                "qr_code": peer_config.qr_code,
                "ip_address": peer_config.ip_address
            }
        }
    )
```

## 🌐 Network Topology

### IP Allocation Strategy

```
WireGuard Network: 10.8.0.0/16

Gateway:         10.8.0.1
Reserved:        10.8.0.2 - 10.8.0.9

Devices:         10.8.0.10 - 10.8.255.254
  (per device: /32)

Fleet Networks:  10.8.1.0/24, 10.8.2.0/24, ...
  (per fleet: /24 subnet)
```

### Multi-Tenant Isolation

```python
# Firewall rules per isolation
class NetworkIsolation:
    def setup_project_isolation(self, project_id: str, subnet: str):
        """Setup firewall rules per project isolation"""
        # iptables rules
        # Allow only project devices to communicate
        pass
    
    def allow_fleet_communication(self, fleet_id: str, devices: List[str]):
        """Allow devices in fleet to communicate"""
        # Setup routing rules
        pass
```

## 🐳 Kubernetes Deployment

### WireGuard Gateway Deployment

```yaml
# infrastructure/kubernetes/wireguard-gateway/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wireguard-gateway
  namespace: stack4things
spec:
  replicas: 1  # Single gateway per ora
  selector:
    matchLabels:
      app: wireguard-gateway
  template:
    metadata:
      labels:
        app: wireguard-gateway
    spec:
      hostNetwork: true  # Required per WireGuard
      containers:
      - name: wireguard-gateway
        image: stack4things/wireguard-gateway:latest
        securityContext:
          privileged: true  # Required per WireGuard
          capabilities:
            add:
              - NET_ADMIN
              - SYS_MODULE
        ports:
        - containerPort: 51820
          protocol: UDP
        - containerPort: 8000
          protocol: TCP
        volumeMounts:
        - name: wireguard-config
          mountPath: /etc/wireguard
        env:
        - name: WIREGUARD_INTERFACE
          value: "wg0"
        - name: WIREGUARD_ADDRESS
          value: "10.8.0.1/16"
      volumes:
      - name: wireguard-config
        configMap:
          name: wireguard-config
---
apiVersion: v1
kind: Service
metadata:
  name: wireguard-gateway
  namespace: stack4things
spec:
  selector:
    app: wireguard-gateway
  ports:
  - port: 51820
    targetPort: 51820
    protocol: UDP
    name: wireguard
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: api
  type: LoadBalancer  # Per esporre WireGuard endpoint
```

## 📊 Monitoring

### Metrics

```python
# Prometheus metrics per WireGuard
wireguard_peers_total = Counter(
    'wireguard_peers_total',
    'Total number of WireGuard peers'
)

wireguard_peers_connected = Gauge(
    'wireguard_peers_connected',
    'Number of connected WireGuard peers'
)

wireguard_bytes_rx = Counter(
    'wireguard_bytes_received_total',
    'Total bytes received via WireGuard'
)

wireguard_bytes_tx = Counter(
    'wireguard_bytes_sent_total',
    'Total bytes sent via WireGuard'
)
```

## 🔒 Security

### Key Management

- Keys stored in Vault/Kubernetes Secrets
- Automatic key rotation (opzionale)
- Separate keys per device
- No key sharing

### Network Security

- Each device isolated by default
- Firewall rules per isolation
- Project-based network segmentation
- Audit logging per connessioni

## 📚 References

- [WireGuard Documentation](https://www.wireguard.com/)
- [WireGuard Quick Start](https://www.wireguard.com/quickstart/)
- [WireGuard for Kubernetes](https://github.com/WireGuard/wg-quick)
- [WireGuard Performance](https://www.wireguard.com/performance/)


