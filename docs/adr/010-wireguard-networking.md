# ADR-010: Virtual Networking - WireGuard

## Status
**Accepted** - 2024-01-XX

## Context

Stack4Things v2.0 necessita di:
- Virtual networking per dispositivi IoT
- Secure tunnel tra dispositivi e cloud
- Bypass NAT/Firewall
- Multi-tenant network isolation
- Performance efficiente (low overhead)
- Supporto per migliaia di dispositivi

## Decision

Utilizzare **WireGuard** per virtual networking invece di soluzioni più complesse.

Architettura:
```
┌─────────────────────────────────────────────────────────────┐
│              Cloud Infrastructure                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  WireGuard Gateway (Kubernetes)                       │ │
│  │  - Hub per tutti i dispositivi                        │ │
│  │  - Routing centralizzato                              │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────────────────────┘
               │ WireGuard Tunnel (UDP)
               │
┌──────────────▼──────────────────────────────────────────────┐
│              Edge / IoT Devices                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  WireGuard Client                                    │ │
│  │  - Config automatica                                 │ │
│  │  - Auto-reconnect                                    │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Motivazioni

### WireGuard Advantages
- ✅ **Performance**: Fastest VPN protocol (low overhead)
- ✅ **Security**: Modern cryptography (ChaCha20, Curve25519)
- ✅ **Simplicity**: Simple configuration, easy to manage
- ✅ **Cross-platform**: Support Linux, Windows, macOS, iOS, Android
- ✅ **Kernel-space**: Linux kernel module (high performance)
- ✅ **Mobile-friendly**: Low battery consumption
- ✅ **NAT traversal**: Built-in NAT punching

### vs OpenVPN
- ✅ Molto più veloce (3-5x throughput)
- ✅ Configurazione più semplice
- ✅ Overhead minore
- ✅ Reconnection più veloce

### vs IPSec
- ✅ Configurazione più semplice
- ✅ Migliore per mobile devices
- ✅ NAT traversal migliore

### vs Neutron VPNaaS
- ✅ Performance superiori
- ✅ Più semplice da gestire
- ✅ Supporto mobile migliore
- ⚠️ Meno integrato con OpenStack (ma gestibile)

## Architecture Details

### WireGuard Gateway Service

```
┌─────────────────────────────────────────┐
│   WireGuard Gateway Service             │
│   (Kubernetes Deployment)               │
│                                          │
│  ┌──────────────────────────────────┐  │
│  │  WireGuard Server                 │  │
│  │  - Config generation              │  │
│  │  - Peer management                │  │
│  │  - Routing rules                  │  │
│  └──────────────────────────────────┘  │
│                                          │
│  ┌──────────────────────────────────┐  │
│  │  Management API                  │  │
│  │  - Add/remove peers              │  │
│  │  - Generate configs               │  │
│  │  - Monitor connections            │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Network Topology

```
┌─────────────────────────────────────────┐
│   WireGuard Network (10.8.0.0/16)       │
│                                          │
│   Gateway: 10.8.0.1                      │
│                                          │
│   Device 1: 10.8.0.10/32                │
│   Device 2: 10.8.0.11/32                │
│   Device 3: 10.8.0.12/32                │
│   ...                                    │
│                                          │
│   Fleet A: 10.8.1.0/24                  │
│   Fleet B: 10.8.2.0/24                  │
└─────────────────────────────────────────┘
```

### Integration con Neutron

```
WireGuard Network
    │
    ├── Neutron Network (optional)
    │   └── For integration with OpenStack VMs
    │
    └── Direct Routing
        └── Direct access to devices
```

## Implementation

### WireGuard Gateway Service

**Componenti**:
- WireGuard server (wg-quick)
- Management API (REST/gRPC)
- Config generator
- Peer manager
- Monitoring/health checks

### Device Configuration

**Auto-configuration**:
- Config generata automaticamente
- Push via WAMP/API
- QR code per setup mobile
- Auto-reconnect logic

### Network Isolation

**Multi-tenant**:
- Separate WireGuard networks per project
- Firewall rules per isolation
- Route tables per segregation

## Configuration Example

### Gateway Config

```ini
# /etc/wireguard/wg0.conf
[Interface]
Address = 10.8.0.1/16
ListenPort = 51820
PrivateKey = <gateway-private-key>

# Device 1
[Peer]
PublicKey = <device1-public-key>
AllowedIPs = 10.8.0.10/32

# Device 2
[Peer]
PublicKey = <device2-public-key>
AllowedIPs = 10.8.0.11/32
```

### Device Config

```ini
# Device WireGuard config
[Interface]
Address = 10.8.0.10/32
PrivateKey = <device-private-key>

[Peer]
PublicKey = <gateway-public-key>
Endpoint = gateway.stack4things.local:51820
AllowedIPs = 10.8.0.0/16
PersistentKeepalive = 25
```

## Consequences

### Positive
- ✅ Performance eccellenti
- ✅ Setup semplice
- ✅ Secure by default
- ✅ Mobile-friendly
- ✅ Scalabile (migliaia di dispositivi)

### Negative
- ⚠️ Richiede gestione chiavi
- ⚠️ Network routing complesso per multi-tenant
- ⚠️ Monitoring necessario

### Mitigation
- Automated key management
- Centralized routing management
- Comprehensive monitoring

## Alternatives Considered

### OpenVPN
- ⚠️ Più lento di WireGuard
- ⚠️ Configurazione più complessa
- ✅ Più maturo

### IPSec
- ⚠️ Complessità alta
- ⚠️ Performance inferiori
- ✅ Standard enterprise

### Neutron VPNaaS
- ✅ Integrazione OpenStack
- ⚠️ Performance limitate
- ⚠️ Meno flessibile

### Tailscale/ZeroTier (SaaS)
- ✅ Managed service
- ❌ Vendor lock-in
- ❌ Costo mensile
- ❌ Meno controllo

## References

- [WireGuard Documentation](https://www.wireguard.com/)
- [WireGuard Quick Start](https://www.wireguard.com/quickstart/)
- [WireGuard for Kubernetes](https://github.com/WireGuard/wg-quick)
- [WireGuard Performance](https://www.wireguard.com/performance/)


