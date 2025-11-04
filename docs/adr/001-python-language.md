# ADR-001: Linguaggio di Programmazione - Python 3.11+

## Status
**Accepted** - 2024-01-XX

## Context

Stack4Things v2.0 necessita di un linguaggio di programmazione che:
- Supporti integrazione nativa con OpenStack (Keystone, Neutron, Designate)
- Offra performance adeguate per real-time communication (WAMP/WebSocket)
- Permetta rapid development e maintainability
- Abbia ecosystem maturo per microservizi cloud-native

## Decision

Utilizzare **Python 3.11+** come linguaggio principale per tutti i microservizi.

Motivazioni:
1. **Integrazione OpenStack**: Tutte le librerie OpenStack sono native Python
2. **Performance**: Python 3.11+ con asyncio offre performance eccellenti per I/O-bound operations
3. **Ecosystem**: FastAPI, SQLAlchemy async, Pydantic sono mature e performanti
4. **Team Skills**: Team già competente in Python
5. **Time to Market**: Sviluppo più rapido rispetto a linguaggi compilati

## Consequences

### Positive
- ✅ Integrazione seamless con OpenStack
- ✅ Rapid development
- ✅ Ecosystem maturo (FastAPI, SQLAlchemy, Pydantic)
- ✅ Team productivity alta
- ✅ Type hints (Python 3.11+) per type safety

### Negative
- ⚠️ Performance CPU-bound non ottimali (ma non critico per questo caso)
- ⚠️ Memory footprint maggiore rispetto a Go/Rust (accettabile)

### Neutral
- Ecosystem Python per microservizi cloud-native è maturo ma non quanto Go/Java

## Alternatives Considered

### Go
- ✅ Performance eccellenti
- ✅ Cloud-native design
- ❌ Integrazione OpenStack complessa
- ❌ Team deve imparare nuovo linguaggio
- ❌ WAMP support limitato

### Rust
- ✅ Performance massime
- ✅ Memory safety
- ❌ Integrazione OpenStack impossibile senza rewrite completo
- ❌ Learning curve molto ripida
- ❌ Development più lento

### Node.js/TypeScript
- ✅ Real-time support ottimo
- ❌ Single-threaded limitations
- ❌ OpenStack ecosystem limitato

## References

- [Python 3.11 Performance Improvements](https://docs.python.org/3/whatsnew/3.11.html)
- [FastAPI Performance](https://fastapi.tiangolo.com/#performance)
- [OpenStack Python SDK](https://docs.openstack.org/sdk/)

