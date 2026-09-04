from __future__ import annotations

import json

from .domain import Signal, SignalStatus


def _escape_mrkdwn(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_slack_message(item: Signal) -> dict:
    if item.status == SignalStatus.EARLY_SIGNAL:
        heading = "⚡ EARLY SIGNAL — not yet confirmed"
    elif item.status == SignalStatus.CONFIRMED_YC:
        heading = "✅ CONFIRMED — YC Directory"
    elif item.status == SignalStatus.CONFIRMED_SPEEDRUN:
        heading = "✅ CONFIRMED — a16z Speedrun"
    else:
        heading = "🔎 NEEDS REVIEW"
    details = [
        f"*Company:* {_escape_mrkdwn(item.company_name)}",
        f"*Founder:* {_escape_mrkdwn(item.founder_name or 'Unknown')}",
        f"*Program:* {_escape_mrkdwn(item.program or 'Unclear')}",
        f"*Confidence:* {item.confidence:.0%}",
        f"*Signal:* {_escape_mrkdwn(item.text[:700])}",
        f"<{item.source_url.replace('|', '%7C').replace('>', '%3E')}|Open source>",
    ]
    return {
        "text": f"{heading}: {item.company_name}"[:3000],
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": heading}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(details)}},
        ],
    }


class SlackNotifier:
    endpoint = "https://slack.com/api/chat.postMessage"

    def __init__(self, transport, *, token: str, channel: str):
        if not token or not channel:
            raise ValueError("Slack token and channel are required")
        self.transport = transport
        self.token = token
        self.channel = channel

    def send(self, item: Signal) -> None:
        payload = {"channel": self.channel, **format_slack_message(item)}
        response = self.transport.post_json(
            self.endpoint,
            payload,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        if not response.get("ok"):
            raise RuntimeError(f"Slack rejected message: {response.get('error', 'unknown_error')}")


class StdoutNotifier:
    def send(self, item: Signal) -> None:
        print(json.dumps(format_slack_message(item), ensure_ascii=False))
