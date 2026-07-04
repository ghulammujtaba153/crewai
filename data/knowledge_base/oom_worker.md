# Runbook: Worker Out-of-Memory (OOM)

## Symptoms
- OutOfMemoryError in worker logs
- Growing job backlog
- Worker host status critical, high memory percentage

## Common root causes
1. Memory leak in job processor
2. Oversized batch jobs
3. Insufficient heap limits under load

## Diagnosis steps
1. Confirm OOM messages in worker service logs
2. Check incidents titled with OOM or backlog
3. Compare mem_pct on worker hosts

## Remediation
1. `restart_service` to reclaim memory
2. `scale_up` to distribute backlog
3. `clear_cache` if shared cache pressure contributes
4. Avoid cluster-wide reboot unless all safer options fail and DB load is not critical

## Verification
- No new OOM errors in recent logs
- Job backlog stabilizes or decreases
- Worker status returns to healthy/degraded (not critical)
