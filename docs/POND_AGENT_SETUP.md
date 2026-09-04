# Pond Agent setup

This repository contains the persistent monitor itself. Pond should supervise it; Pond credentials are not required by the monitor and must not be committed.

1. Deploy the container or run `python -m yc_launch_monitor serve` on a persistent host.
2. Confirm `GET /healthz` returns `{"ok": true}` and `GET /api/status` shows the latest run and each source.
3. In Pond, create an agent manually and describe its job as: run and supervise the launch monitor every eight hours; report degraded sources; never send outreach automatically.
4. Point the Pond agent's health check at the deployed `/api/status` URL if the current Pond UI offers an HTTP health-check field. Pond's private integration API is deliberately not assumed.
5. Attach screenshots showing the scheduled runs, Slack messages, and `/api/status` to the submission.

The source collection is read-only. LinkedIn is queried through TinyFish's public web-search index; it does not use a LinkedIn password or session cookie.
