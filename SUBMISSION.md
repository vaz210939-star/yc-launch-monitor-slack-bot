# Pond submission — YC Launch Monitor Slack Bot

## Repository

GitHub URL: `ADD_AFTER_PUBLISHING`

## Working bot

YC Launch Monitor is a persistent, stateful Python service for a single Slack workspace. It monitors:

- the official Y Combinator company directory;
- the separate a16z Speedrun company directory;
- first-person founder announcements on X through TwitterAPI.io;
- public LinkedIn launch posts through TinyFish Search.

SQLite stores first-seen and content hashes, so unchanged alerts are delivered once. The service runs every eight hours and exposes `/healthz`, `/readyz`, and `/api/status` for health monitoring.

## Live evidence

Full-source Slack validation run:

- Run ID: `d2f387d7-56c1-4825-a753-30909c535b64`
- Completed: 2026-09-04 15:02:09 UTC
- Collected: 125
- Source health: YC Directory `ACTIVE`, a16z Speedrun `ACTIVE`, X `ACTIVE`, LinkedIn `ACTIVE`
- Failed Slack deliveries: 0

Final post-fix read-only validation run:

- Run ID: `e84b87db-6170-4c5f-9727-a998a1a3eacc`
- Completed: 2026-09-04 15:19:19 UTC
- Collected: 125
- Source health: all four collectors `ACTIVE`
- Slack deliveries: 0 (preview mode intentionally does not consume delivery state)
- Failed deliveries: 0

Real early signals delivered to Slack include:

- LinkedIn — Shepherd (YC S26): <https://www.linkedin.com/posts/elijahrenner_i-was-accepted-to-yc-s26-as-a-high-school-activity-7464730735350956033-tMjy>
- X — fresh YC founder announcement: <https://x.com/AniC_dev/status/2094889316098945330>
- X — a16z Speedrun SR007 founder announcement: <https://x.com/TadehTheRFGuy/status/2093023361454719225>

An immediate repeat run collected the same source state and delivered zero duplicates. Full details are in [`docs/VALIDATION_EVIDENCE.md`](docs/VALIDATION_EVIDENCE.md).

## Setup

1. Copy `.env.example` to `.env` and add the source API keys and Slack bot token/channel.
2. Install the Slack app with `slack-manifest.yaml` and invite it to the destination channel.
3. Run `docker compose up --build -d`, or set `PYTHONPATH=src` and run `python -m yc_launch_monitor serve --send-slack`.
4. Open `http://localhost:8080/api/status` to verify the latest run and per-source health.

Detailed setup, safety behavior, tests, and rollback steps are documented in `README.md` and `docs/OPERATIONS.md`.

## Demo

Screenshots or recording URL: `ADD_BEFORE_SUBMISSION`

The recommended 60–90 second recording sequence is in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

## Pond supervision

This implementation is a deterministic monitoring service, not an AI agent, so Pond Agent infrastructure is not required by the task's conditional rule. The repository nevertheless exposes a stable status endpoint suitable for optional Pond supervision; the manual setup procedure is documented in `docs/POND_AGENT_SETUP.md` and assumes no undocumented private Pond API.
