from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import signal
import sys
import time

from .collectors import LinkedInCollector, SpeedrunCollector, XCollector, YCDirectoryCollector
from .config import Settings
from .domain import CollectorHealth, CollectorResult, Signal, SignalStatus, Source
from .health import start_health_server
from .http import UrlLibTransport
from .service import MonitorService
from .slack import SlackNotifier, StdoutNotifier
from .store import Store


class _StaticCollector:
    def __init__(self, result: CollectorResult):
        self.result = result
        self.name = result.source

    def collect(self):
        return self.result


def _real_collectors(settings: Settings, transport):
    return [
        YCDirectoryCollector(transport),
        SpeedrunCollector(transport),
        XCollector(transport, settings.twitter_api_key, settings.x_queries),
        LinkedInCollector(transport, settings.tinyfish_api_key, settings.linkedin_queries),
    ]


def _demo_collectors():
    return [
        _StaticCollector(CollectorResult(Source.YC_DIRECTORY, CollectorHealth.ACTIVE, [Signal(
            source=Source.YC_DIRECTORY,
            source_id="demo-confirmed-yc",
            source_url="https://www.ycombinator.com/companies/demo-ai",
            company_name="Demo AI",
            founder_name="Alex Kim",
            text="Automates operations for small teams",
            program="Y Combinator",
            batch_or_cohort="S26",
            status=SignalStatus.CONFIRMED_YC,
            confidence=1.0,
        )])),
        _StaticCollector(CollectorResult(Source.SPEEDRUN, CollectorHealth.ACTIVE, [Signal(
            source=Source.SPEEDRUN,
            source_id="demo-speedrun",
            source_url="https://speedrun.a16z.com/companies/demo-games",
            company_name="Demo Games",
            founder_name="Maya Singh",
            text="Multiplayer games infrastructure",
            program="a16z Speedrun",
            batch_or_cohort="SR006",
            status=SignalStatus.CONFIRMED_SPEEDRUN,
            confidence=1.0,
            metadata={"program_owner": "a16z"},
        )])),
        _StaticCollector(CollectorResult(Source.X, CollectorHealth.ACTIVE, [Signal(
            source=Source.X,
            source_id="demo-x-early",
            source_url="https://x.com/demo/status/1",
            company_name="Signal Labs",
            founder_name="Sam Lee",
            text="We were accepted into Y Combinator S26 with Signal Labs!",
        )])),
        _StaticCollector(CollectorResult(Source.LINKEDIN, CollectorHealth.ACTIVE, [Signal(
            source=Source.LINKEDIN,
            source_id="demo-linkedin-review",
            source_url="https://www.linkedin.com/posts/demo",
            company_name="Unknown company",
            founder_name="Taylor Chen",
            text="Thoughts about why YC founders build quickly",
        )])),
    ]


def _notifier(settings: Settings, transport, *, force_stdout: bool):
    if force_stdout or not settings.slack_delivery_enabled:
        return StdoutNotifier()
    if not settings.slack_bot_token or not settings.slack_channel_id:
        raise SystemExit("Slack delivery is enabled, but SLACK_BOT_TOKEN or SLACK_CHANNEL_ID is missing")
    return SlackNotifier(
        transport,
        token=settings.slack_bot_token,
        channel=settings.slack_channel_id,
    )


def _build_service(settings: Settings, *, demo: bool, force_stdout: bool, bootstrap_notify: bool | None = None):
    transport = UrlLibTransport()
    store = Store(settings.database_path)
    service = MonitorService(
        store,
        _demo_collectors() if demo else _real_collectors(settings, transport),
        _notifier(settings, transport, force_stdout=force_stdout),
        bootstrap_notify=settings.bootstrap_notify if bootstrap_notify is None else bootstrap_notify,
        notify_needs_review=settings.notify_needs_review,
        record_deliveries=not force_stdout,
    )
    return store, service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YC and a16z Speedrun launch monitor")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="Run one scan")
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--send-slack", action="store_true", help="Allow configured Slack delivery")
    demo = commands.add_parser("demo", help="Run an offline deterministic demo")
    demo.add_argument("--json", action="store_true")
    serve = commands.add_parser("serve", help="Run every MONITOR_INTERVAL_SECONDS")
    serve.add_argument("--send-slack", action="store_true", help="Allow configured Slack delivery")
    health = commands.add_parser("health", help="Print current state")
    health.add_argument("--json", action="store_true")
    listing = commands.add_parser("list", help="List stored signals")
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command == "demo":
        demo_settings = replace(settings, database_path=Path(":memory:"))
        store, service = _build_service(demo_settings, demo=True, force_stdout=True, bootstrap_notify=True)
        try:
            result = service.run_once()
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2 if args.json else None))
        finally:
            store.close()
        return 0

    store = Store(settings.database_path)
    try:
        if args.command == "health":
            print(json.dumps(store.latest_status(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "list":
            print(json.dumps(store.list_signals(args.limit), ensure_ascii=False, indent=2, default=str))
            return 0
    finally:
        if args.command in {"health", "list"}:
            store.close()

    # Re-opened through the builder so construction remains identical for scan and serve.
    store.close()
    force_stdout = not getattr(args, "send_slack", False)
    store, service = _build_service(settings, demo=False, force_stdout=force_stdout)
    try:
        if args.command == "scan":
            result = service.run_once()
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2 if args.json else None))
            return 0
        server = start_health_server(store, settings.health_host, settings.health_port)
        stop = False

        def request_stop(*_):
            nonlocal stop
            stop = True

        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)
        print(f"Health server: http://{settings.health_host}:{settings.health_port}/healthz")
        while not stop:
            print(json.dumps(service.run_once().to_dict(), ensure_ascii=False))
            end = time.monotonic() + settings.interval_seconds
            while not stop and time.monotonic() < end:
                time.sleep(min(1.0, end - time.monotonic()))
        server.shutdown()
        server.server_close()
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
