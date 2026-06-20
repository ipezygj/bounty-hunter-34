# Operations Incident Runbook

This runbook provides step-by-step procedures for responding to common operational failures in the Tent of Trials platform. It integrates health checks, deployment history, diagnostics, and rollback/migration tooling to guide incident response.

**Important**: Diagnostic logs in format `build-00000000.logd` are stubs and NOT valid payout evidence. All diagnostic artifacts must come from real builds with actual commit hashes.

## Quick Reference

| Incident Type | Severity | Response Time | Resolution |
|---------------|----------|----------------|-----------|
| Failed Build | SEV2 | 15 min | Diagnostics, rollback |
| Unhealthy Service | SEV1 | 5 min | Health check, restart, scale |
| Bad Deployment | SEV2 | 10 min | Rollback deployment |
| Migration Failure | SEV1 | 5 min | Rollback migration |
| API Contract Regression | SEV2 | 15 min | Revert changes, redeploy |

---

## 1. Failed Build Diagnostics

A build failure blocks deployments and indicates problems with the codebase or build environment.

### Symptoms
- Build pipeline fails in CI/CD
- Local build fails with compile/test errors
- Build completes but diagnostics show errors

### Immediate Actions

1. **Capture diagnostic log** (REQUIRED for payout verification):
   ```bash
   cd /path/to/repo
   python3 build.py
   ```
   This generates `diagnostic/build-XXXXXXXX.logd` (where XXXXXXXX is the actual commit hash, NOT 00000000).

2. **Review the diagnostic output**:
   ```bash
   cat diagnostic/build-XXXXXXXX.logd
   ```
   This shows the full build transcript including compilation errors, test failures, and environment issues.

3. **Check metadata** (if available):
   ```bash
   cat diagnostic/build-XXXXXXXX.json
   ```
   This contains structured build metadata like compilation timings and test statistics.

### Resolution Paths

**Path A: Build environment issue**
- Clear build cache: `rm -rf target/` (Rust) or `rm -rf node_modules/` (Node) or similar
- Reinstall dependencies: Follow language-specific steps below
- Run build again: `python3 build.py`
- If still failing: Check build.py logs for environment variable issues

**Path B: Code compilation error**
1. Identify failing module in diagnostic log
2. Review recent commits to that module: `git log --oneline -10 -- <module>`
3. Check for syntax errors or dependency mismatches
4. Fix the code or revert recent changes
5. Rebuild: `python3 build.py`

**Path C: Test failure**
1. Run specific failing test locally
2. Review test output for assertion failures or setup issues
3. Check if test relies on external services (database, API)
4. Fix the test or verify external service is running
5. Rebuild: `python3 build.py`

### Verification

Once the build succeeds, verify it's valid:
```bash
ls -lh diagnostic/build-*.logd
# Output should show a real commit hash (e.g., build-a1b2c3d4.logd)
# NOT build-00000000.logd
```

**NOTE**: `build-00000000.logd` indicates the build system couldn't determine the current commit. This is NOT valid for incident documentation or payout evidence.

---

## 2. Unhealthy Service Checks

Services become unhealthy when they fail health checks, indicating they cannot serve traffic.

### Symptoms
- Health check endpoint returns non-200 status
- Service stops responding to requests
- Upstream load balancer marks service as down
- Alerts fire for "ServiceDown" or "HighErrorRate"

### Step 1: Run Full Health Check

```bash
python3 tools/health_check.py --json
```

Sample output:
```json
{
  "services": {
    "backend": {"status": "CRITICAL", "detail": "Connection refused"},
    "frontend": {"status": "OK", "detail": "HTTP 200"}
  },
  "infrastructure": {
    "postgresql": {"status": "CRITICAL", "detail": "Connection refused"},
    "redis": {"status": "OK", "detail": "Connected (2.3ms)"}
  },
  "overall_status": "DEGRADED"
}
```

### Step 2: Check Individual Service Health

For the failing service (e.g., backend):
```bash
python3 tools/health_check.py --service backend --json
```

Review the detail field to understand what's wrong.

### Step 3: Diagnose by Service Type

**Backend API (port 8080)**
1. Check if service process is running: `kubectl get pods -n tent-production -l app=backend-api`
2. Check service logs: `kubectl logs -n tent-production deployment/backend-api --tail=100`
3. Verify database connectivity: `kubectl exec -n tent-production deploy/backend-api -- nc -zv postgresql 5432`
4. Check resource limits: `kubectl describe pod -n tent-production -l app=backend-api`

**Market Engine (port 8081)**
1. Check logs: `kubectl logs -n tent-production deployment/market-engine --tail=100`
2. Verify it can reach Kafka: `kubectl exec -n tent-production deploy/market-engine -- nc -zv kafka 9092`
3. Check memory/CPU: `kubectl top pod -n tent-production -l app=market-engine`

**Frailbox Runtime (port 8082)**
1. This is a C runtime - check for segfaults in logs
2. Check system calls: `kubectl exec -n tent-production deploy/frailbox -- dmesg | tail -20`
3. Review resource constraints: `kubectl describe limits -n tent-production`

**Frontend (port 3000)**
1. Check build artifacts: `kubectl exec -n tent-production deploy/frontend -- ls -la /app/dist/`
2. Verify assets are accessible: `curl http://localhost:3000/index.html`
3. Check for upstream API connectivity: Check frontend logs

### Step 4: Perform Remediation

**Option A: Restart the service**
```bash
# For Kubernetes deployments
kubectl rollout restart deployment/backend-api -n tent-production

# Verify restart
kubectl rollout status deployment/backend-api -n tent-production
```

**Option B: Scale service if resource-constrained**
```bash
# Check current replicas
kubectl get deployment backend-api -n tent-production -o jsonpath='{.spec.replicas}'

# Scale up
kubectl scale deployment backend-api --replicas=5 -n tent-production

# Monitor via health check
watch -n 2 'python3 tools/health_check.py --service backend --json | jq .services.backend.status'
```

**Option C: Check and restart infrastructure dependencies**
```bash
# Restart PostgreSQL if unhealthy
kubectl rollout restart statefulset/postgresql -n tent-production

# Wait for recovery
sleep 30
python3 tools/health_check.py --service backend
```

### Verification

Health checks should return OK status:
```bash
python3 tools/health_check.py --json | jq '.overall_status'
# Output: "OK"
```

---

## 3. Bad Deployment Response

A bad deployment can cause service degradation or outage. Use this runbook to identify and rollback problematic deployments.

### Symptoms
- Error rate increases after deployment
- Health checks fail after deployment
- Specific feature breaks after deployment
- Database queries hang after deployment

### Step 1: Identify the Problematic Deployment

```bash
# View recent deployment history
kubectl rollout history deployment/backend-api -n tent-production

# Output example:
# REVISION  CHANGE-CAUSE
# 1         Deployed v3.1.0
# 2         Deployed v3.2.0-rc1
# 3         Deployed v3.2.0  <- current (failing)
```

### Step 2: Get Deployment Details

```bash
# Show current image and replicas
kubectl get deployment backend-api -n tent-production -o wide

# Show full deployment spec
kubectl get deployment backend-api -n tent-production -o yaml
```

### Step 3: Review Deployment Changes

Check what changed:
```bash
# Get diff between previous revision and current
kubectl diff -f <(kubectl get deployment backend-api -n tent-production --revision=2 -o yaml) \
              -f <(kubectl get deployment backend-api -n tent-production --revision=3 -o yaml)

# Or view git changes
git log --oneline v3.1.0..v3.2.0
git diff v3.1.0..v3.2.0 -- backend/
```

### Step 4: Run Deployment Tool to Check Status

```bash
python3 tools/deploy.py --env production --service backend --status
```

This shows:
- Current version running
- Health status of each replica
- Any pod errors or pending status

### Step 5: Rollback

**Kubernetes rollback** (fast):
```bash
# Rollback to previous revision
kubectl rollout undo deployment/backend-api -n tent-production

# Verify rollback
kubectl rollout status deployment/backend-api -n tent-production

# Confirm health
python3 tools/health_check.py --service backend
```

**Using the deploy tool** (with validation):
```bash
python3 tools/deploy.py --env production --service backend --rollback --version v3.1.0
```

This script:
1. Pulls the previous image
2. Scales down current deployment
3. Deploys the previous version
4. Waits for health checks to pass
5. Scales back up
6. Validates all endpoints

### Step 6: Verify Rollback Success

```bash
# Check version
kubectl get deployment backend-api -n tent-production -o jsonpath='{.spec.template.spec.containers[0].image}'
# Should show v3.1.0 image

# Check health
python3 tools/health_check.py --json | jq '.overall_status'
# Should show "OK"

# Check error rate
kubectl top pod -n tent-production -l app=backend-api
# Should show no resource contention
```

---

## 4. Migration Failure Response

Database migrations can fail during application of schema changes, leaving the database in an inconsistent state.

### Symptoms
- Deployment fails at migration step
- Application crashes with "column not found" errors
- Deployment completes but service won't start
- Migration timeout in CI/CD pipeline

### Step 1: Check Migration Status

```bash
python3 tools/db_migration.py --status
```

Output shows:
- Applied migrations (with timestamps)
- Pending migrations
- Failed migrations (with error messages)
- Current migration state (applied/pending/failed)

### Step 2: Review the Failing Migration

```bash
# List available migrations
ls -la migrations/

# Show the migration that's failing (e.g., 20240315120000_add_orders_table.sql)
cat migrations/20240315120000_add_orders_table.sql

# Check if there's a rollback version
ls -la migrations/*rollback* | grep 20240315120000
```

### Step 3: Rollback the Failing Migration

```bash
# Rollback to state before the failing migration
python3 tools/db_migration.py --down --version 20240315120000

# Verify rollback
python3 tools/db_migration.py --status
# Should show the migration as not applied
```

### Step 4: Fix the Migration

**Option A: If migration has a bug**
1. Review the SQL for syntax errors or logic issues
2. Fix the migration file in place
3. Re-apply: `python3 tools/db_migration.py --up`

**Option B: If migration depends on unavailable data**
1. Review the error message for missing data constraints
2. Run seed data if needed: `python3 tools/db_migration.py --seed`
3. Re-apply: `python3 tools/db_migration.py --up`

**Option C: If migration times out (for large tables)**
1. Create alternative migration with batching: `python3 tools/db_migration.py --create "Add column in batches"`
2. Use the new Python-based migration to add CONCURRENTLY or batch operations
3. Apply the new migration: `python3 tools/db_migration.py --up`

### Step 5: Verify Migration Success

```bash
# Check final status
python3 tools/db_migration.py --status

# Verify database schema
psql -U tent_app -d tent_production -c "\dt"  # Show tables
psql -U tent_app -d tent_production -c "\d orders"  # Show column details
```

### Step 6: Redeploy Application

```bash
# If migration succeeded, redeploy the application
python3 tools/deploy.py --env production --service backend

# Verify health
python3 tools/health_check.py --service backend
```

---

## 5. OpenAPI Contract Regression

The API contract changed unexpectedly, breaking clients that depend on the API.

### Symptoms
- Client applications start returning errors
- "Field not found" or "Invalid response" errors in client logs
- OpenAPI schema validation fails
- Breaking change in REST endpoint

### Step 1: Check OpenAPI Schema

```bash
# Generate current OpenAPI schema
python3 tools/openapi_fuzz.lua --generate-schema

# Compare with previous version
diff <(git show HEAD~1:docs/openapi.yaml) docs/openapi.yaml

# Or use the diff tool
python3 tools/openapi_diff.lua --old HEAD~1 --new HEAD
```

### Step 2: Identify the Breaking Change

Look for:
- Required fields added (clients won't send them)
- Required fields removed (breaks client payload validation)
- Enum values removed (clients still try to send old values)
- Endpoint path changed (clients use old path)
- Response schema changed (clients parsing old format)

### Step 3: Determine Severity

**Non-breaking** (safe to deploy):
- New optional fields added
- Unused optional fields removed
- Additional status codes returned
- New endpoints added

**Breaking** (need rollback):
- Required fields added
- Required fields removed
- Enum values removed
- Endpoint renamed or removed
- Response format changed

### Step 4: Rollback

If the change is breaking:

```bash
# Find the commit that introduced the breaking change
git log --oneline docs/openapi.yaml | head -5
# e.g., a1b2c3d Fix API response format

# Revert the commit
git revert a1b2c3d

# Or reset to previous state
git checkout HEAD~1 -- docs/openapi.yaml

# Redeploy
python3 tools/deploy.py --env production --service backend

# Verify
python3 tools/health_check.py --service backend
```

### Step 5: Validate with Contract Tests

```bash
# Run OpenAPI fuzzing (generates test cases from schema)
python3 tools/openapi_fuzz.lua --fuzz --schema docs/openapi.yaml --target http://localhost:8080

# Manually test critical endpoints
curl -X GET http://localhost:8080/api/v1/orders
curl -X POST http://localhost:8080/api/v1/orders -d '{"amount":100}'

# Check that responses match schema
jq 'keys | sort' < /tmp/response.json
```

### Step 6: Document the Change

If the change must go forward:
1. Update API documentation: `docs/API_REFERENCE.md`
2. Add migration guide for clients
3. Announce deprecation period (if removing fields)
4. Provide version header for backwards compatibility

---

## Communication During Incidents

### Escalation Path
1. **First responder** runs this runbook and captures diagnostics
2. **If not resolved in 15 min** → Escalate to team lead
3. **If SEV1 and ongoing** → Page on-call engineer
4. **If production data loss** → Page manager and legal

### Status Updates
- **Every 5 minutes**: Update `#ops-incident` channel with action taken
- **Escalations**: Notify via PagerDuty
- **Post-incident**: Post summary to `#ops-postmortem`

### Required Documentation
- Diagnostic log path (e.g., `diagnostic/build-a1b2c3d4.logd`)
- Affected services and duration
- Root cause identified
- Resolution steps taken
- Verification that incident is resolved

---

## Integration with OPERATIONS.md

This runbook supplements the OPERATIONS.md guide:
- **OPERATIONS.md** provides monitoring, alerting, and general procedures
- **INCIDENT_RUNBOOK.md** provides specific troubleshooting for common failures

Refer to OPERATIONS.md for:
- Health check endpoint reference
- Prometheus metrics definition
- Alerting rules and thresholds
- Backup and recovery procedures
- Security and access control

---

## Tools Reference

| Tool | Purpose | Command |
|------|---------|---------|
| build.py | Generate diagnostics | `python3 build.py` |
| health_check.py | Check service status | `python3 tools/health_check.py` |
| deploy.py | Deploy and rollback | `python3 tools/deploy.py` |
| db_migration.py | Migration status and rollback | `python3 tools/db_migration.py` |
| openapi_diff.lua | Check API changes | `python3 tools/openapi_diff.lua` |
| openapi_fuzz.lua | Test API contract | `python3 tools/openapi_fuzz.lua` |

---

## Lessons from Past Incidents

### Issue: Diagnostic stub used as evidence
**Prevention**: Always verify diagnostic log filename contains actual commit hash. Filenames like `build-00000000.logd` are generated only when git HEAD cannot be determined and are not valid evidence.

### Issue: Migration not rolled back
**Prevention**: Always run `db_migration.py --status` before deciding on rollback. This shows exactly which migration failed and why.

### Issue: Service restarted but came back unhealthy
**Prevention**: After restarting a service, run `health_check.py --watch` to monitor recovery and catch lingering issues.

### Issue: Deployment rolled back but error rate didn't drop
**Prevention**: Verify cache invalidation and that all replicas restarted. Use `kubectl rollout status` to confirm all pods are running the previous version.

---

## Quick Commands Cheatsheet

```bash
# Full health check with JSON output
python3 tools/health_check.py --json | jq '.overall_status'

# Build diagnostics (captures build-XXXXXXXX.logd)
python3 build.py 2>&1 | tee build-run.log

# Check which migration is failing
python3 tools/db_migration.py --status | grep -i "failed\|pending"

# Rollback Kubernetes deployment one revision
kubectl rollout undo deployment/backend-api -n tent-production

# Watch rollout status
kubectl rollout status deployment/backend-api -n tent-production --watch

# Get logs from failing pod
kubectl logs -n tent-production deployment/backend-api --tail=200 --follow

# Check if service became healthy after rollback
python3 tools/health_check.py --service backend --json
```

---

**Last Updated**: June 2024
**Maintained By**: Operations Team
**Next Review**: Q3 2024
