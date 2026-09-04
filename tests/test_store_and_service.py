import tempfile
import unittest
from pathlib import Path

from yc_launch_monitor.domain import (
    CollectorHealth,
    CollectorResult,
    Signal,
    SignalStatus,
    Source,
)
from yc_launch_monitor.service import MonitorService
from yc_launch_monitor.store import Store


def signal(text="We joined YC S26"):
    return Signal(
        source=Source.X,
        source_id="x-1",
        source_url="https://x.com/a/status/1",
        company_name="Rocket Labs",
        founder_name="Ada Li",
        text=text,
        status=SignalStatus.EARLY_SIGNAL,
        confidence=0.9,
    )


class StaticCollector:
    name = Source.X

    def __init__(self, item):
        self.item = item

    def collect(self):
        return CollectorResult(source=Source.X, health=CollectorHealth.ACTIVE, signals=[self.item])


class RecordingNotifier:
    def __init__(self, fail=False):
        self.fail = fail
        self.items = []

    def send(self, item):
        if self.fail:
            raise RuntimeError("Slack unavailable")
        self.items.append(item)


class StoreAndServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "state.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_same_signal_is_not_delivered_twice(self):
        notifier = RecordingNotifier()
        service = MonitorService(self.store, [StaticCollector(signal())], notifier)
        first = service.run_once()
        second = service.run_once()

        self.assertEqual(first.delivered, 1)
        self.assertEqual(second.delivered, 0)
        self.assertEqual(len(notifier.items), 1)

    def test_changed_signal_is_delivered_again(self):
        notifier = RecordingNotifier()
        collector = StaticCollector(signal())
        service = MonitorService(self.store, [collector], notifier)
        service.run_once()
        collector.item = signal("We joined YC S26 and launched Rocket Labs")
        result = service.run_once()

        self.assertEqual(result.delivered, 1)
        self.assertEqual(len(notifier.items), 2)

    def test_failed_delivery_remains_retryable(self):
        failing = MonitorService(self.store, [StaticCollector(signal())], RecordingNotifier(fail=True))
        failed = failing.run_once()
        notifier = RecordingNotifier()
        retried = MonitorService(self.store, [StaticCollector(signal())], notifier).run_once()

        self.assertEqual(failed.failed_deliveries, 1)
        self.assertEqual(retried.delivered, 1)
        self.assertEqual(len(notifier.items), 1)

    def test_bootstrap_baseline_stays_suppressed_until_content_changes(self):
        notifier = RecordingNotifier()
        collector = StaticCollector(signal())
        service = MonitorService(
            self.store, [collector], notifier, bootstrap_notify=False
        )
        first = service.run_once()
        second = service.run_once()
        collector.item = signal("We joined YC S26 and launched publicly")
        changed = service.run_once()

        self.assertEqual(first.delivered, 0)
        self.assertEqual(second.delivered, 0)
        self.assertEqual(changed.delivered, 1)
        self.assertEqual(len(notifier.items), 1)


if __name__ == "__main__":
    unittest.main()
