# Nexora Platform — Research Status Report

**Data**: 25 Giugno 2026  
**Repository**: `nexora-platform`  
**Maturity**: Pre-release (Nexora v0.1.0 — MVP Stage)  
**Scopo**: Analisi dello stato reale del codice per pianificare la valutazione sperimentale di un paper accademico.

---

## SEZIONE 1 — STATO IMPLEMENTAZIONE PER SERVIZIO

### Riepilogo

| Servizio | Struttura | Completezza | Test | Error handling | Metriche | TODO/FIXME |
|---|---|---|---|---|---|---|
| device-service | Modular | ✅ Completo | ✅ 314 righe | ✅ Reale | ⚠️ Definite, non usate | ❌ |
| plugin-service | Flat | ✅ Completo | ⚠️ Scaffold (33 righe) | ✅ Reale | ✅ HTTP requests + duration | ❌ |
| execution-service | Flat | ✅ Completo | ✅ 199 righe | ✅ Reale | ✅ + Active executions Gauge | ❌ |
| fleet-service | Flat | ✅ Completo | ⚠️ Scaffold (24 righe) | Minimale | ✅ HTTP requests + duration | ❌ |
| dns-service | Flat | ✅ Completo | ⚠️ Scaffold (24 righe) | Minimale | ✅ HTTP requests + duration | ❌ |
| network-service | Flat | ✅ Completo | ⚠️ Scaffold (24 righe) | Minimale | ✅ HTTP requests + duration | ❌ |
| webservice-service | Flat | ✅ Completo | ⚠️ Scaffold (24 righe) | Minimale | ✅ HTTP requests + duration | ❌ |
| nexora-edge | Flat | ✅ Completo | ❌ Assenti | ✅ Reale + retry | ✅ Completo (7 metriche) | ❌ |
| nexora-device-emulator | Script | ✅ Funzionale | ❌ N/A | Minimale | ❌ Assenti | ❌ |
| rbac-service | Modular | ✅ Completo | ❌ Assenti | ✅ Reale | ❌ Assenti | ❌ |

### Note per servizio

**device-service** — Il più maturo. Implementa bootstrap token con scadenza e revocation list, heartbeat state tracking, auth middleware completo. Redis è configurato in `core/config.py` ma non referenziato in nessun punto del codice. Le metriche sono definite in `core/metrics.py` ma `setup_metrics()` è vuota — non vengono mai tracciate.

**execution-service** — Servizio più rilevante per la ricerca. State machine completa (`queued → dispatched → running → succeeded/failed/timeout/cancelled`). Background loop di timeout ogni 5 secondi (`_timeout_loop`, riga 187). Idempotency key support. Limite per-device (`MAX_EXECUTIONS_PER_DEVICE`, HTTP 429). Kafka retry con backoff esponenziale.

**nexora-edge** — Il gateway ha il set di metriche più ricco della piattaforma: contatori per dispatch, delivery, failure, sessioni attive, pending dispatch per device. In-memory session cache (`agent_sessions`, `dispatch_cache`) — nessun distributed store, non scalabile orizzontalmente.

**plugin-service** — CRUD completo. Risponde sia su `/api/v2/plugins` (legacy) che su `/api/v2/modules`. Solo scaffold di test (health check).

**fleet/dns/network/webservice-service** — Pattern identico: CRUD MySQL-backed, metriche HTTP, event publish su Kafka. Test scaffold (24 righe each, nessun test reale).

---

## SEZIONE 2 — OSSERVABILITÀ ESISTENTE

### 2.1 Metriche effettivamente esposte oggi

#### Metriche HTTP standard (presenti su plugin, execution, fleet, dns, network, webservice)
```
s4t_http_requests_total          Counter  [service, method, path, status]
s4t_http_request_duration_seconds Histogram [service, method, path]
```

#### Metriche specifiche execution-service
```
s4t_active_executions            Gauge    [service]
```

#### Metriche specifiche nexora-edge (il set più completo)
```
s4t_lr_dispatch_events_total          Counter  [service]
s4t_lr_delivery_attempts_total        Counter  [service, device_id]
s4t_lr_delivery_failures_total        Counter  [service, device_id]
s4t_lr_agent_sessions                 Gauge    [service]
s4t_lr_pending_dispatches             Gauge    [service]
s4t_lr_per_device_pending_dispatches  Gauge    [service, device_id]
s4t_lr_request_duration_seconds       Histogram [service, method, path]
```

#### device-service — Definite ma NON istanziate
```python
# libraries/common e device-service/core/metrics.py definiscono:
device_operations          Counter  [operation, status]
device_operation_duration  Histogram [operation]
active_devices             Gauge
# setup_metrics() è vuota — nessuna di queste viene registrata
```

#### Servizi senza nessuna metrica
- , `rbac-service`, `nexora-device-emulator`

---

### 2.2 Metriche assenti per la valutazione sperimentale

| Metrica necessaria | Status | Note |
|---|---|---|
| Latenza dispatch end-to-end (POST /executions → Kafka → gateway → agent) | ❌ Assente | Misurabile solo con trace distribuito esterno |
| Latenza delivery gateway→agent | ❌ Assente | `delivery_attempts_total` presente ma non timing |
| Throughput events/sec per Kafka topic | ❌ Assente | Nessun Kafka consumer lag metric |
| Tempo di provisioning device (register → first heartbeat) | ❌ Assente | Non instrumentato in device-service |
| Tasso di timeout esecuzioni (timeout/total) | ⚠️ Derivabile | `s4t_active_executions` + HTTP status counts, non diretto |
| Kafka availability (down/up) | ❌ Assente | Nessuna metrica per Kafka connectivity |
| Agent disconnect/reconnect rate | ❌ Assente | `s4t_lr_agent_sessions` Gauge presente ma non eventi di churn |
| Execution failure rate per device | ⚠️ Parziale | `s4t_lr_delivery_failures_total` per device_id |
| DB query latency | ❌ Assente | Nessuna SQLAlchemy instrumentation |

---

### 2.3 Prometheus Rules e Alert esistenti

**`infrastructure/kubernetes/monitoring/prometheus/prometheus-rules.yaml`**:
```yaml
- HighErrorRate:    rate(http_requests_total[5m]) con status 5xx > 5%  — finestra 5m
- HighLatency:      http_request_duration_seconds p95 > 1s             — finestra 5m
- ServiceDown:      up{job=~"nxr.*"} == 0                     — finestra 1m
- HighCPUUsage:     container_cpu > 80%                                — finestra 5m
- HighMemoryUsage:  container_memory > 90%                             — finestra 5m
```

**`infrastructure/kubernetes/monitoring/prometheus/slo-rules.yaml`**:
```yaml
- High5xxErrorRate: s4t_http_requests_total 5xx rate > 2%  — finestra 10m
- HighP95Latency:   s4t_http_request_duration_seconds p95 > 0.7s — finestra 10m
```

Le regole SLO usano il prefisso `s4t_` — compatibili con le metriche effettivamente esposte. Le regole generiche usano `http_requests_total` senza prefisso — potrebbero non corrispondere.

---

## SEZIONE 3 — CI/CD E TESTING

### 3.1 Script di validazione locale

| Script | Funzione |
|---|---|
| `test-all.sh` | Orchestratore completo: Python syntax, YAML, shell, imports, Docker compose smoke, API contracts, cross-service, E2E |
| `contract-tests-api.py` | Positive + negative API contract checks su tutti i CRUD endpoint |
| `nexora-device-emulator-e2e.sh` | NexoraEdge lifecycle E2E: register → create execution → dispatch → callback → verify |
| `integration-cross-service.sh` | Flusso cross-service (device → execution → gateway) |
| `test-reproducibility.sh` | Verifica file setup, Poetry config, import reproducibility |
| `test-imports.sh` | Import check per common library |
| `chaos-drill.sh` | Chaos engineering scenarios (kill containers, verify recovery) |
| `dr-gameday.sh` | Disaster recovery simulation |
| `perf-baseline.sh` | Performance baseline con `hey` |
| `event-replay.py` | Replay JSONL event stream con filtri (timestamp, tenant, correlation_id) |
| `replay_execution_outbox.py` | DLQ replay utility per execution outbox |
| `postalpha-validation.sh` | Checklist post-alpha completo |
| `setup-dev.sh`, `setup-venv.sh`, `install-deps.sh`, `verify-setup.sh` | Setup ambiente di sviluppo |

### 3.2 Pipeline CI/CD

**Status**: ❌ Nessuna pipeline automatica presente.

- ❌ No `.github/workflows/`
- ❌ No `.gitlab-ci.yml`
- ❌ No `Jenkinsfile`
- ❌ No `Makefile`

**Presente**: pre-commit hooks (`.pre-commit-config.yaml`) — Black, Ruff, mypy, Bandit, file checks. Eseguiti solo localmente al commit.

### 3.3 Progressive Delivery

**`infrastructure/kubernetes/progressive-delivery/rollout-device.yaml`**:
```yaml
kind: Rollout  # argoproj.io/v1alpha1
strategy: canary
  steps:
    - setWeight: 20   # pause: 2m
    - setWeight: 50   # pause: 2m
    - (automatic promotion)
```

Presente solo per `device-service`. Nessun rollout per gli altri servizi.

### 3.4 Copertura test

| Servizio | Test lines | Copertura effettiva |
|---|---|---|
| execution-service | 199 | CRUD, lifecycle completo, idempotency, 429, 409, timeout, cancel, field validation |
| device-service | 314 | CRUD + 7 agent test case (register, heartbeat, expiry, revocation) |
| plugin-service | 33 | Solo health check |
| fleet/dns/network/webservice | ~24 ciascuno | Template scaffold, nessun test reale |
| nexora-edge | 0 | Nessun test |
| rbac-service | 0 | Nessun test |

### 3.5 Gap per una pipeline CI minima

Per avere lint + test + build funzionante basterebbero:

1. **GitHub Actions workflow** con jobs: `ruff check`, `black --check`, `pytest` per execution-service e device-service (i due con test reali), `docker build` per ogni servizio.
2. **Test per nexora-edge** — il componente più critico non ha test.
3. **Completare test scaffold** di fleet/dns/network/webservice con almeno CRUD test.
4. **Estendere Argo Rollout** agli altri servizi critici (execution, nexora-edge).

---

## SEZIONE 4 — PARITÀ CON NXR/IOTRONIC LEGACY

### 4.1 Matrice di parità (`docs/deployment/nexora-parity-matrix.md`)

| Concetto Legacy | Equivalente Nexora v2.0 | Note |
|---|---|---|
| Board / node identity | `device-service /api/v2/devices` | UUID-based REST CRUD |
| Board registration (WAMP `wamp.session.on_join`) | `POST /api/v2/agents/register` | Bootstrap token sostituisce WAMP realm |
| Session keepalive / conductor heartbeat | `POST /api/v2/agents/{id}/heartbeat` | HTTP POST periodico invece di WAMP ping |
| oslo.messaging RPC call to board | `POST /api/v2/executions` + `/dispatch` | Kafka envelope sostituisce AMQP cast/call |
| Lightning Rod result callback | `POST /api/v2/executions/{id}/callback` | Field validation stretta, state machine |
| Plugin injection | `plugin-service /api/v2/plugins` | REST CRUD; injection tramite execution pipeline |
| Fleet / group management | `fleet-service /api/v2/fleets` | REST CRUD con member management |
| VPN / network tunnels | `network-service /api/v2/ports` | Networking endpoint astratto |
| DNS auto-registration | `dns-service /api/v2/dns/records` | REST CRUD per DNS record |
| Webservice exposure | `webservice-service /api/v2/webservices` | Port-based service exposure |
| Crossbar.io session transport | `nexora-edge` | Kafka consumer + HTTP delivery, in-memory sessions |
| OpenStack Keystone auth | Keycloak (primary) + Keystone (fallback) | JWT-based, configurabile |

**NON replicato**:
- WAMP topic subscriptions e pub/sub pattern
- oslo.messaging conductor RPC topology
- Autobahn/Twisted reactor loop nell'agent
- Direct board-to-board communication via Crossbar
- OpenStack Glance (image provisioning), Cinder (storage), Nova (compute) — adapter presenti in `libraries/common/src/common/openstack/` ma non cablati end-to-end

### 4.2 Compatibilità plugin-service

`plugin-service` risponde sia su `/api/v2/plugins` (legacy) che su `/api/v2/modules`. Differenza: la versione v2.0 aggiunge il campo `version` (default "0.1.0") non presente nel legacy. CRUD funzionale; il meccanismo di injection tramite execution pipeline non è esplicitamente documentato nel codice.

---

## SEZIONE 5 — ADR ESISTENTI E DECISIONI NON DOCUMENTATE

### 5.1 ADR presenti in `docs/adr/`

**ADR-0001** — *NexoraEdge Gateway and Execution Pipeline* (Accepted, 2026-03-28)

Decisione: sostituire WAMP/Crossbar.io + oslo.messaging con HTTP REST + Kafka. Il ciclo di vita dell'esecuzione è gestito da execution-service (create→dispatch→callback); i dispatch event vengono pubblicati su Kafka (`nxr.execution.dispatched`); il gateway li consuma, li mette in cache, e li consegna agli edge agent via HTTP. Gli agent fanno callback a execution-service. La state machine impone transizioni valide. Il gateway è stateless (scalabile orizzontalmente) — ma questa claim è invalidata dalla in-memory cache, vedi sotto.

**Totale ADR**: 1.

### 5.2 Decisioni architetturali senza ADR

| Decisione | Osservazione nel codice | Rischio |
|---|---|---|
| **Struttura modular vs flat** | device-service e rbac-service hanno `src/<name>/core/api/`; tutti gli altri sono `main.py` monolitici. Nessuna spiegazione documentata. | Medio — manutenzione inconsistente |
| **Gateway in-memory sessions** | `agent_sessions` e `dispatch_cache` sono `dict` Python in `nexora-edge/main.py` (riga ~29). ADR-0001 dichiara il gateway "stateless" ma la cache locale lo rende sticky. | **Alto** — impossibile scalare orizzontalmente senza perdere stato sessione |
| **Redis configurato ma non usato** | `REDIS_URL` presente in `device-service/core/config.py`; Redis è nel compose; nessun `import redis` nel codice del servizio. | Basso — risorsa sprecata |
| **KAFKA_REQUIRED=false di default** | Tutti i servizi hanno due flag separati: `KAFKA_ENABLED` (abilita publisher) e `KAFKA_REQUIRED` (fa fallire startup se Kafka non raggiungibile). Il default è degraded mode silenzioso. | Medio — in produzione si potrebbe credere che gli eventi vengano pubblicati anche se Kafka è down |
| **Dev-token bypass OIDC** | `AUTH_DEV_TOKEN` in tutti i servizi flat: se il token corrisponde, il middleware auth viene bypassato completamente (plugin-service riga 76, execution-service riga 29). | **Alto** — rischio sicurezza se `AUTH_ENABLED=false` o se il dev token trapela in produzione |
| **Timeout loop polling vs event-driven** | `execution-service` ha un background task async che ogni 5 secondi itera su tutte le execution `dispatched/running` e le porta in `timeout`. Approccio polling invece di evento schedulato. | Medio — falsi negativi se il loop è lento sotto carico |
| **Alembic + `_ensure_*_columns()` in parallelo** | I servizi flat hanno sia migrations Alembic che una funzione runtime `_ensure_*_columns()` che fa `ALTER TABLE` se le colonne mancano. Approccio duale non documentato. | Medio — conflitti di migrazione su ambienti esistenti |

---

## SEZIONE 6 — RIPRODUCIBILITÀ SPERIMENTALE

### 6.1 Analisi nexora-device-emulator (`services/nexora-device-emulator/emulator.py`, 112 righe)

### 6.2 Dispositivi simulabili

**Limite hardcoded**: ❌ Nessuno.

Lo script è single-threaded e simula **un solo board per invocazione**. Per simulare N device occorre lanciare N processi separati:

```bash
for i in $(seq 1 20); do
  BOARD_NAME="board-$i" python3 emulator.py &
done
```

Nessun meccanismo di batch, pool o threading interno. Scalabilità: O(N processi OS) per N board.

### 6.3 Supporto scenari di failure

❌ **Non supportato natively**.

| Scenario | Supportato | Note |
|---|---|---|
| Kill device / crash agent | ❌ | Solo `Ctrl+C` / `kill` esterno |
| Network delay simulato | ❌ | Nessun parametro `--delay` |
| Kafka down | ❌ | L'emulator non parla direttamente con Kafka (usa HTTP) — ma se execution-service è down il poll fallisce silenziosamente |
| Partial network partition | ❌ | Nessun supporto |
| Slow/hanging agent | ❌ | Nessun parametro per simulare latenza risposta |
| Failure injection su callback | ❌ | Il callback invia sempre `succeeded` |

Fallback esistente: try/except su tutte le HTTP call con `sleep(POLL_SECONDS)` e retry al ciclo successivo (nessun exit su errore).

### 6.4 Configurabilità

Tutti i parametri sono configurabili tramite **env vars** (nessun argomento CLI):

```bash
DEVICE_URL=http://device-service:8000      # default
EXEC_URL=http://execution-service:8000     # default (attenzione: nome env diverso dal valore default)
GW_URL=http://nexora-edge:8000    # default
BOOTSTRAP_TOKEN=dev-bootstrap:dev-bootstrap-token
BOARD_NAME=lr-board-<uuid8>               # auto-generato se non specificato
BOARD_TYPE=nexoraedge-emulator
HEARTBEAT_SECONDS=10
POLL_SECONDS=4
```

### 6.5 Flusso di connessione

Protocollo: **HTTP REST puro** (no WebSocket, no WAMP, no Kafka diretto).

```
1. POST /api/v2/agents/register         → device-service  (header: X-Bootstrap-Token)
2. POST /api/v2/agents/sessions/register → nexora-edge
3. Loop ogni HEARTBEAT_SECONDS:
   POST /api/v2/agents/{id}/heartbeat   → device-service
   POST /api/v2/agents/sessions/{id}/heartbeat → gateway
4. Loop ogni POLL_SECONDS:
   GET  /api/v2/executions              → execution-service
   POST /api/v2/deliver/{exec_id}       → gateway
   POST /api/v2/executions/{id}/callback (status: running)   → execution-service
   POST /api/v2/executions/{id}/callback (status: succeeded) → execution-service
```

### 6.6 Scriptabilità per test automatizzati

**Happy path**: ✅ scriptabile — `scripts/nexora-device-emulator-e2e.sh` fa esattamente questo in modo deterministico (device_id fisso, execution_id fisso, verifica `final_status == "succeeded"`).

**Scenario avanzati**: ❌ non supportati dallo script attuale.

Per esperimenti riproducibili suggerisco:

```bash
# Avvia N board
for i in $(seq 1 $N_BOARDS); do
  BOARD_NAME="board-$i" POLL_SECONDS=2 python3 emulator.py >> logs/board-$i.log 2>&1 &
  echo $! >> /tmp/board_pids
done

# Kill subset dopo X secondi (simula failure)
sleep $FAILURE_AT
head -n $((N_BOARDS/2)) /tmp/board_pids | xargs kill

# Verifica metriche Prometheus dopo recovery
```

### 6.7 Limiti per la valutazione sperimentale

| Aspetto | Status | Impatto |
|---|---|---|
| Board name deterministico | ⚠️ Auto-generato random se non specificato | Basso — basta settare `BOARD_NAME` |
| Exit code su failure | ❌ Sempre 0 | Medio — detection failure richiede parsing stdout |
| Metriche esportate | ❌ Nessuna (stdout only) | **Alto** — nessuna correlazione con Prometheus |
| Callback sempre `succeeded` | ❌ Non simula failure/timeout reali | **Alto** — non testa il comportamento in caso di errore agent |
| Execution parallele per board | ❌ Sequential poll cycle | Medio — non testa concorrenza |
| DLQ handling | ❌ Assente | Medio — nessun test per replay su failure |

---

## RIEPILOGO PER PIANIFICAZIONE SPERIMENTALE

### Cosa è pronto oggi

- ✅ Pipeline di esecuzione completa (queued → dispatched → running → succeeded/failed/timeout) — implementata e testata
- ✅ Metriche HTTP standard su tutti i servizi core
- ✅ Metriche specifiche sul gateway (delivery, sessions, failures per device)
- ✅ Alert Prometheus e SLO rules configurati
- ✅ E2E happy-path scriptabile e deterministico
- ✅ Parità funzionale con legacy Lightning Rod documentata in ADR-0001

### Cosa serve prima della valutazione sperimentale

**Priorità alta (bloccanti per misurare ciò che interessa)**:

1. **Instrumentare latenza end-to-end**: aggiungere timestamp `dispatched_at` su Kafka event e misurare delta a gateway delivery → `s4t_execution_dispatch_latency_seconds` Histogram.
2. **Attivare metriche device-service**: completare `setup_metrics()` in `device-service/core/metrics.py` per tracciare operazioni reali.
3. **Aggiungere metrica provisioning time**: misurare delta tra `register` e `first_heartbeat` in device-service.
4. **Emulatore multi-board con failure injection**: aggiungere supporto per `--kill-after N` e `--fail-callback-rate P` nell'emulatore per testare scenari di failure.

**Priorità media (necessari per claim di scalabilità)**:

5. **Sostituire in-memory cache nel gateway con Redis**: la claim ADR-0001 di gateway "stateless/horizontally scalable" è falsa oggi.
6. **Test nexora-edge**: il componente più critico non ha nessun test.
7. **Pipeline CI minima**: almeno lint + test per execution-service e device-service su push.

**Priorità bassa (nice-to-have)**:

8. Completare test CRUD per fleet/dns/network/webservice.
9. Estendere Argo Rollout a execution-service e nexora-edge.
10. Documentare ADR per le decisioni elencate in Sezione 5.2.

---

*Analisi condotta in modalità read-only — nessuna modifica al codice applicata.*
