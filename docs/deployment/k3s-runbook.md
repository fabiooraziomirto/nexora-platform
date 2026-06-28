# Nexora k3s — Operations Runbook

## 1. Restore MySQL from backup

Backups are created daily at 02:00 by the `mysql-backup` CronJob and stored in the `mysql-backup-data` PVC under `/backups/nexora-YYYY-MM-DD.sql.gz`.

```bash
# List available backups
kubectl exec -n nxr deploy/mysql -- ls /backups/

# Copy backup to local machine
kubectl cp nxr/$(kubectl get pod -n nxr -l app=mysql -o name | head -1 | cut -d/ -f2):/backups/nexora-2026-01-15.sql.gz ./nexora-2026-01-15.sql.gz

# Restore into a running MySQL pod
kubectl exec -i -n nxr statefulset/mysql -- bash -c \
  "gunzip -c /backups/nexora-2026-01-15.sql.gz | mysql -u nexora -p\$MYSQL_PASSWORD nexora"

# Verify row counts post-restore
kubectl exec -n nxr statefulset/mysql -- mysql -u nexora -p\$MYSQL_PASSWORD nexora \
  -e "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='nexora';"
```

## 2. Unseal Vault after pod restart

Vault starts sealed after every pod restart. The unseal key and root token were saved during initial setup.

```bash
# Check if sealed
kubectl exec -n nxr statefulset/vault -- vault status

# Unseal (run once per key share — default config uses 1 share)
UNSEAL_KEY=$(cat ~/.nexora/vault-keys.json | python3 -c "import sys,json; print(json.load(sys.stdin)['unseal_keys_b64'][0])")
kubectl exec -n nxr statefulset/vault -- vault operator unseal "$UNSEAL_KEY"

# Verify unsealed
kubectl exec -n nxr statefulset/vault -- vault status | grep Sealed
# Expected: Sealed  false

# If Kubernetes auth broke (e.g., after cluster re-init), re-run vault-init.sh:
bash scripts/k3s/vault-init.sh
```

## 3. Re-pairing a device after bootstrap token rotation

When `AGENT_BOOTSTRAP_TOKENS` is rotated, existing devices with cached tokens lose auth.

```bash
# Generate a new token entry
NEW_TOKEN="device-$(openssl rand -hex 8):$(openssl rand -hex 16):$(date -d '+365 days' +%s)"

# Patch the secret (adds to existing tokens)
EXISTING=$(kubectl get secret nexora-internal -n nxr -o jsonpath='{.data.AGENT_BOOTSTRAP_TOKENS}' | base64 -d)
kubectl patch secret nexora-internal -n nxr \
  --type='json' \
  -p="[{\"op\":\"replace\",\"path\":\"/data/AGENT_BOOTSTRAP_TOKENS\",\"value\":\"$(echo "${EXISTING},${NEW_TOKEN}" | base64 -w0)\"}]"

# Rolling restart so services pick up new token
kubectl rollout restart deployment/device-service -n nxr

# Distribute new token to device out-of-band (USB, SSH, MDM)
echo "New device bootstrap token: $NEW_TOKEN"
```

## 4. Rollback a service to a previous image

```bash
# Check rollout history
kubectl rollout history deployment/device-service -n nxr

# Rollback to previous revision
kubectl rollout undo deployment/device-service -n nxr

# Or rollback to a specific revision
kubectl rollout undo deployment/device-service -n nxr --to-revision=3

# Rollback to a specific image tag
kubectl set image deployment/device-service device-service=nexora/device-service:v0.2.1 -n nxr
kubectl rollout status deployment/device-service -n nxr
```

Use `scripts/k3s/upgrade.sh --service device-service --version v0.2.1` for the managed path.

## 5. Disaster recovery — PVC snapshot and restore on new node

### Snapshot (source node)

```bash
# Stop workloads to ensure consistent snapshot
kubectl scale deployment device-service execution-service plugin-service -n nxr --replicas=0
kubectl scale statefulset mysql -n nxr --replicas=0

# Copy PVC data off-node via a temporary pod
kubectl run pvc-backup --image=alpine --restart=Never -n nxr \
  --overrides='{"spec":{"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"mysql-data"}}],"containers":[{"name":"c","image":"alpine","command":["sleep","3600"],"volumeMounts":[{"mountPath":"/data","name":"data"}]}]}}' 
kubectl wait --for=condition=Ready pod/pvc-backup -n nxr
kubectl exec -n nxr pvc-backup -- tar czf - /data | gzip > mysql-pvc-backup.tar.gz
kubectl delete pod pvc-backup -n nxr

# Repeat for other PVCs: kafka-data, matter-data-pvc, mosquitto-data
```

### Restore (new node)

```bash
# 1. Install k3s and Nexora on new node (without starting services)
bash scripts/k3s/install.sh --domain nexora.local --no-tls

# 2. Scale down to stop services writing to PVCs
kubectl scale deployment --all -n nxr --replicas=0
kubectl scale statefulset --all -n nxr --replicas=0

# 3. Restore PVC contents
kubectl run pvc-restore --image=alpine --restart=Never -n nxr \
  --overrides='{"spec":{"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"mysql-data"}}],"containers":[{"name":"c","image":"alpine","command":["sleep","3600"],"volumeMounts":[{"mountPath":"/data","name":"data"}]}]}}'
kubectl wait --for=condition=Ready pod/pvc-restore -n nxr
cat mysql-pvc-backup.tar.gz | kubectl exec -i -n nxr pvc-restore -- tar xzf - -C /
kubectl delete pod pvc-restore -n nxr

# 4. Scale back up
kubectl scale statefulset mysql kafka -n nxr --replicas=1
kubectl scale deployment --all -n nxr --replicas=1

# 5. Verify
bash scripts/k3s/status.sh
```

## 6. Upgrade k3s binary

```bash
# 1. Cordon node to stop scheduling new pods
kubectl cordon $(kubectl get nodes -o name | head -1 | cut -d/ -f2)

# 2. Drain (evicts pods gracefully; PDB protects HA services)
kubectl drain $(kubectl get nodes -o name | head -1 | cut -d/ -f2) \
  --ignore-daemonsets --delete-emptydir-data --timeout=120s

# 3. Upgrade k3s binary on the node
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.29.3+k3s1" sh -

# 4. Verify new version
k3s --version

# 5. Uncordon to allow scheduling again
kubectl uncordon $(kubectl get nodes -o name | head -1 | cut -d/ -f2)

# 6. Wait for all pods to settle
kubectl wait --for=condition=Ready pod --all -n nxr --timeout=300s

# 7. Verify platform health
bash scripts/k3s/status.sh
```
