import tempfile
import unittest
from pathlib import Path

from yc_launch_monitor.collectors import XCollector
from yc_launch_monitor.domain import CollectorHealth, CollectorResult, Signal, SignalStatus, Source
from yc_launch_monitor.service import MonitorService
from yc_launch_monitor.store import Store


class FakeTransport:
    def get_json(self, url, *, headers=None, params=None):
        return {
            "tweets": [{
                "id": "shipping-safety",
                "text": (
                    "I got into @speedrun SR007! Building with Kazi Farabi "
                    "and Jose Serrano."
                ),
                "author": {"userName": "founder", "name": "Founder"},
            }]
        }


class StaticCollector:
    name = Source.X

    def __init__(self, item):
        self.item = item

    def collect(self):
        return CollectorResult(Source.X, CollectorHealth.ACTIVE, [self.item])


class RecordingNotifier:
    def __init__(self):
        self.items = []

    def send(self, item):
        self.items.append(item)


class ShippingSafetyTests(unittest.TestCase):
    def test_x_does_not_treat_collaborator_after_with_as_company(self):
        result = XCollector(
            FakeTransport(),
            api_key="secret",
            queries=("one",),
            sleep=lambda _: None,
        ).collect()

        self.assertEqual(result.signals[0].company_name, "Unknown company")

    def test_preview_does_not_consume_future_slack_delivery(self):
        item = Signal(
            source=Source.X,
            source_id="preview-safe",
            source_url="https://x.com/founder/status/preview-safe",
            company_name="Rocket Labs",
            founder_name="Ada Li",
            text="We joined YC S26",
            status=SignalStatus.EARLY_SIGNAL,
            confidence=0.9,
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.db")
            try:
                preview_notifier = RecordingNotifier()
                preview = MonitorService(
                    store,
                    [StaticCollector(item)],
                    preview_notifier,
                    record_deliveries=False,
                ).run_once()
                slack_notifier = RecordingNotifier()
                live = MonitorService(
                    store,
                    [StaticCollector(item)],
                    slack_notifier,
                ).run_once()
            finally:
                store.close()

        self.assertEqual(len(preview_notifier.items), 1)
        self.assertEqual(preview.delivered, 0)
        self.assertEqual(live.delivered, 1)
        self.assertEqual(len(slack_notifier.items), 1)


if __name__ == "__main__":
    unittest.main()
