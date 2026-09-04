import json
import unittest

from yc_launch_monitor.domain import Signal, SignalStatus, Source
from yc_launch_monitor.slack import SlackNotifier, format_slack_message


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post_json(self, url, payload, *, headers=None):
        self.calls.append((url, payload, headers))
        return {"ok": True, "ts": "1.2"}


class SlackTests(unittest.TestCase):
    def test_message_marks_unconfirmed_early_signal(self):
        item = Signal(
            source=Source.LINKEDIN,
            source_id="li-1",
            source_url="https://linkedin.com/posts/1",
            company_name="Rocket Labs",
            founder_name="Ada Li",
            text="We are joining YC S26",
            status=SignalStatus.EARLY_SIGNAL,
            confidence=0.88,
        )
        payload = format_slack_message(item)
        rendered = json.dumps(payload)
        self.assertIn("EARLY SIGNAL", rendered)
        self.assertIn("not yet confirmed", rendered)

    def test_notifier_uses_bot_token_and_channel(self):
        transport = FakeTransport()
        notifier = SlackNotifier(transport, token="xoxb-secret", channel="C123")
        item = Signal(
            source=Source.YC_DIRECTORY,
            source_id="yc-1",
            source_url="https://ycombinator.com/companies/a",
            company_name="A",
            text="New company",
            status=SignalStatus.CONFIRMED_YC,
            confidence=1.0,
        )
        notifier.send(item)
        _, payload, headers = transport.calls[0]
        self.assertEqual(payload["channel"], "C123")
        self.assertEqual(headers["Authorization"], "Bearer xoxb-secret")

    def test_external_text_cannot_inject_slack_special_mentions(self):
        item = Signal(
            source=Source.X,
            source_id="x-unsafe",
            source_url="https://x.com/a/status/1",
            company_name="A",
            text="Launch <!channel> & more",
            status=SignalStatus.EARLY_SIGNAL,
            confidence=0.8,
        )
        rendered = json.dumps(format_slack_message(item))
        self.assertNotIn("<!channel>", rendered)
        self.assertIn("&lt;!channel&gt;", rendered)


if __name__ == "__main__":
    unittest.main()
