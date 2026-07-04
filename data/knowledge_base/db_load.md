# Runbook: Critical Database Load

## Symptoms
- `db_load` >= 80 on primary database hosts
- Slow query logs
- Connection pool exhaustion on API tier
- Replication lag warnings

## Common root causes
1. Long-running queries locking resources
2. Connection leaks from application pools
3. Sudden write/read spike

## Diagnosis steps
1. Query servers where db_load is elevated
2. Review postgres service logs for slow queries
3. Check open incidents on db-primary

## Remediation (safety-critical)
1. Prefer `clear_cache` and `flush_connections` first
2. Prefer `scale_up` on read replicas / API tier
3. **NEVER** run `system_reboot`, `force_kill_db`, or `drop_connections` while db_load is critical (>= 80)
4. High-risk commands are blocked by Sentinel safety guardrails under critical DB load

## Verification
- db_load falls below 80
- Connection pool errors stop appearing in logs
