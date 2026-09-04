# Validation evidence

This file contains no API keys, Slack tokens, cookies, database contents, or account credentials.

## Automated tests

Command:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

Result on 2026-09-04: **42 tests passed**.

Coverage includes collector parsing, safe host validation, classification of recent vs. historical announcements, negative/rejection language, safe company-name extraction, provider rate-limit spacing, SQLite persistence, changed-content behavior, failed-delivery retry, non-consuming preview mode, bootstrap suppression, Slack escaping, and health endpoints.

## Full-source live run

Run ID: `d2f387d7-56c1-4825-a753-30909c535b64`

```json
{
  "collected": 125,
  "new_or_changed": 9,
  "delivered": 2,
  "failed_deliveries": 0,
  "source_health": {
    "yc_directory": "active",
    "speedrun": "active",
    "x": "active",
    "linkedin": "active"
  }
}
```

Per-source counts observed during the same configuration:

| Source | Records | Health |
| --- | ---: | --- |
| YC Directory | 50 | ACTIVE |
| a16z Speedrun | 15 | ACTIVE |
| X | 40 | ACTIVE |
| LinkedIn via TinyFish | 20 | ACTIVE |

The X collector spaces its two intent queries to respect the provider's short-window rate limit. A failed query is reported as `DEGRADED` while successful query results are preserved.

## Final post-fix source validation

Run ID: `e84b87db-6170-4c5f-9727-a998a1a3eacc`

```json
{
  "collected": 125,
  "new_or_changed": 13,
  "delivered": 0,
  "failed_deliveries": 0,
  "source_health": {
    "yc_directory": "active",
    "speedrun": "active",
    "x": "active",
    "linkedin": "active"
  }
}
```

This was deliberately run without `--send-slack`. Preview output is observable, but it no longer marks alerts as delivered, so a later real Slack run remains eligible to send them.

## Slack evidence

The following real alerts were delivered successfully:

| Source | Type | Link |
| --- | --- | --- |
| LinkedIn | early YC founder signal, Shepherd (YC S26) | <https://www.linkedin.com/posts/elijahrenner_i-was-accepted-to-yc-s26-as-a-high-school-activity-7464730735350956033-tMjy> |
| X | early YC founder signal | <https://x.com/AniC_dev/status/2094889316098945330> |
| X | a16z Speedrun SR007 founder signal | <https://x.com/TadehTheRFGuy/status/2093023361454719225> |
| YC Directory | confirmed new directory listing, Grocalo | <https://www.ycombinator.com/companies/grocalo> |

Slack messages contain a status header, company when available, founder, program, confidence, source text, and original link. External text is escaped so it cannot inject Slack-wide mentions.

## Deduplication evidence

Run ID `8569fba8-65a6-45a9-bff4-5b4df942f699` was executed immediately after a live delivery run:

```json
{
  "collected": 105,
  "new_or_changed": 0,
  "delivered": 0,
  "failed_deliveries": 0
}
```

The database primary key combines source and source ID. Delivery history additionally stores the content hash. Unchanged content is not delivered twice; a materially changed record can be delivered again.

## Persistent operation

- Default cadence: 28,800 seconds (eight hours).
- State: SQLite under the mounted `data` directory.
- Container restart policy: `unless-stopped`.
- Health endpoints: `/healthz`, `/readyz`, `/api/status`.
- Emergency delivery stop: set `SLACK_DELIVERY_ENABLED=false`; collection and state persistence continue.
