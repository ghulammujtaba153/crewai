# Runbook: High CPU Utilization

## Symptoms
- Sustained CPU above 90%
- Elevated request latency
- WARN/ERROR logs about timeouts or queue depth

## Common root causes
1. Traffic spike without autoscaling
2. Inefficient request handlers or hot loops
3. Upstream dependency timeouts causing retries

## Diagnosis steps
1. Identify the affected hostname from telemetry
2. Check recent ERROR/CRITICAL logs for that server
3. Correlate with open incidents

## Remediation
1. Prefer `scale_up` to add capacity
2. Use `clear_cache` if cache miss storms are suspected
3. Use `restart_service` only if a single process is wedged
4. Avoid `system_reboot` during peak load or high database load

## Verification
- CPU should drop below 80%
- Error rate should decline in subsequent logs
