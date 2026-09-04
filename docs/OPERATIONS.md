# Post-Deploy Monitoring & Validation

Validation window: first 48 hours after deployment, then review weekly. Owner: the person operating the Pond submission and Slack workspace.

## Expected healthy signals

- `GET /healthz` returns HTTP 200 and `{"ok": true}`.
- `GET /api/status` shows a completed run at least once every eight hours.
- `yc_directory` and `speedrun` normally report `active` with non-zero counts.
- `x` and `linkedin` report `active` after their API keys are configured.
- `failed_deliveries` remains zero.
- A deliberately changed demo/test signal appears once in Slack, not on every run.

## Failure signals

- Search logs for `degraded`, `not_configured`, `failed_deliveries`, `HTTP 401`, `HTTP 403`, and `HTTP 429`.
- A run remains `running` past one full scan window.
- Either official directory reports zero records or stops updating.
- Slack delivery errors repeat for two cycles.
- Notification count spikes after restart, indicating that the persistent `data` volume was not mounted.

## Mitigation and rollback

1. Set `SLACK_DELIVERY_ENABLED=false` immediately if notifications are noisy or malformed; collection and SQLite state continue safely.
2. Check `/api/status`, API quotas, and source diagnostics.
3. Restore the previous container image if a new build changed parsing or deduplication.
4. Preserve the SQLite volume during rollback. Do not delete it unless intentionally rebuilding the baseline.
5. Re-enable Slack only after one stdout-only `scan --json` is healthy.
