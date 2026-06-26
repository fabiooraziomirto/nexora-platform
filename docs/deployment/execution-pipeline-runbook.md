# Execution Pipeline — Operator Runbook

## Overview

The execution pipeline moves a command from the cloud (execution-service) to an
edge device (via nexora-edge) and back.  The lifecycle is:

    queued → dispatched → running → succeeded | failed | timeout | cancelled

## Common Symptoms

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Executions stuck in `dispatched` | Gateway can't reach agent | Check `s4t_lr_agent_sessions` gauge; restart agent |
| Spike in `429` responses | Device queue full | Increase `MAX_EXECUTIONS_PER_DEVICE` or drain old tasks |
| Timeout rate alert fires | Agent too slow or dead | Inspect `s4t_lr_delivery_failures_total`; redeploy agent |
| Kafka consumer lag | Gateway behind on events | Scale gateway replicas; check Kafka broker health |

## Replay / Rollback

If outbox is enabled and rows are stuck in `dead` status:

```bash
python scripts/replay_execution_outbox.py --db "$DATABASE_URL" --status dead
```

Inspect the payloads, then manually re-publish via Kafka CLI or fix the
underlying issue and re-run the outbox worker.

## Partial Outage Scenarios

**Kafka down**: execution-service still creates executions (queued state) but
cannot dispatch.  Gateway has no new events.  Once Kafka recovers, dispatch
endpoints become functional again.

**Gateway down**: dispatched events queue in Kafka.  When gateway restarts, it
resumes from its consumer group offset.  Already-dispatched executions will
time out if the gateway stays down beyond the threshold.

**MySQL down**: all services return 5xx.  Recovery is automatic once MySQL is
reachable.  No data loss for committed transactions.
