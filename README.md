# YC Launch Monitor Slack Bot

A persistent, read-only monitor for newly visible startup launches and founder announcements. It checks:

- the official YC Directory;
- the public a16z Speedrun company directory;
- X announcements through TwitterAPI.io;
- public LinkedIn post search through TinyFish Search;
- Slack delivery through an OAuth bot token.

Important naming note: **Speedrun is an a16z program, not a Y Combinator program.** The source is deliberately labeled `a16z Speedrun` in stored data and alerts.

## What makes a signal actionable

The social collectors search for first-person announcement language such as “we were accepted into YC” and “joining a16z Speedrun.” A generic discussion about YC is stored as `needs_review` and is not sent to Slack by default. An announcement can be:

- `early_signal`: first-person social evidence, not yet confirmed in a directory;
- `confirmed_yc`: present in the official YC Directory;
- `confirmed_speedrun`: present in the official a16z Speedrun directory;
- `needs_review`: ambiguous or discussion-like content.

SQLite stores source IDs, content hashes, first/last seen times and successful deliveries. Identical content is not sent twice; changed content is sent again. A failed Slack call is not marked delivered and is retried later.

## Safe offline demo

No credentials, network calls, or Slack messages are used:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m yc_launch_monitor demo --json
```

## Configuration

Copy `.env.example` to `.env` and set environment variables in the deployment platform. Do not commit `.env`.

- `TWITTERAPIIO_API_KEY`: read-only TwitterAPI.io key.
- `TINYFISH_API_KEY`: TinyFish Search key; no LinkedIn credentials or cookies.
- `X_QUERIES_JSON` and `LINKEDIN_QUERIES_JSON`: optional JSON arrays for changing search criteria without editing code.
- `SLACK_BOT_TOKEN`: Slack `xoxb-...` OAuth bot token.
- `SLACK_CHANNEL_ID`: destination channel ID.
- `SLACK_DELIVERY_ENABLED=false`: global delivery guard.
- `BOOTSTRAP_NOTIFY=false`: first live run creates a baseline without flooding Slack.
- `MONITOR_INTERVAL_SECONDS=28800`: eight-hour interval.

Create the Slack app from [slack-manifest.yaml](slack-manifest.yaml), install it to the workspace, invite the bot into the destination channel, and keep the token only in environment variables.

## Commands

```powershell
python -m yc_launch_monitor scan --json                 # live read-only scan, stdout only
python -m yc_launch_monitor scan --json --send-slack    # send only if the env guard is also true
python -m yc_launch_monitor serve --send-slack          # scheduler plus health server
python -m yc_launch_monitor health --json
python -m yc_launch_monitor list --json
```

Health endpoints while `serve` runs:

- `GET /healthz`
- `GET /readyz`
- `GET /api/status`

## Docker

```bash
docker compose up --build -d
```

The `data` directory is mounted so deduplication survives restarts. See [Pond Agent setup](docs/POND_AGENT_SETUP.md) for a conservative integration that does not invent undocumented Pond APIs.
Production checks and rollback triggers are listed in [Operations](docs/OPERATIONS.md).

## Tests

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

The bot never posts outreach, logs into LinkedIn, uses browser cookies, or stores source/API tokens in SQLite.
