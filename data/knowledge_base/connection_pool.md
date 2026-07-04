# Runbook: Connection Pool Exhaustion

## Symptoms
- "Connection pool exhausted" errors
- API gateway timeouts
- Upstream failures from web tier

## Common root causes
1. Downstream database under load
2. Connection leaks
3. Pool size too small for concurrency

## Diagnosis steps
1. Check API gateway ERROR/CRITICAL logs
2. Correlate with db-primary db_load
3. Review open critical incidents

## Remediation
1. `flush_connections` to recycle idle connections
2. `clear_cache` to reduce DB pressure from cache misses
3. `scale_up` API or replica capacity
4. Do not reboot database hosts while db_load is critical

## Verification
- Connection pool errors cease
- API latency improves
- Related incident can be marked investigating/resolved
