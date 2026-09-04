import json
import unittest

from yc_launch_monitor.collectors import (
    LinkedInCollector,
    SpeedrunCollector,
    XCollector,
    YCDirectoryCollector,
)
from yc_launch_monitor.domain import CollectorHealth, SignalStatus, Source
from yc_launch_monitor.http import HttpError


class FakeTransport:
    def __init__(self, *, text="", json_data=None):
        self.text = text
        self.json_data = json_data or {}
        self.calls = []

    def get_text(self, url, *, headers=None, params=None):
        self.calls.append(("GET_TEXT", url, headers, params))
        return self.text

    def get_json(self, url, *, headers=None, params=None):
        self.calls.append(("GET_JSON", url, headers, params))
        return self.json_data

    def post_json(self, url, payload, *, headers=None):
        self.calls.append(("POST_JSON", url, headers, payload))
        return self.json_data


class SequencedTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get_json(self, url, *, headers=None, params=None):
        self.calls.append(("GET_JSON", url, headers, params))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class CollectorTests(unittest.TestCase):
    def test_yc_directory_extracts_public_algolia_settings_and_company(self):
        html = """<script>window.AlgoliaOpts = {"appId":"APP","apiKey":"KEY"};</script>"""
        payload = {
            "hits": [{
                "id": 42,
                "name": "Example AI",
                "slug": "example-ai",
                "one_liner": "AI operations",
                "batch": "S26",
                "launched_at": 1785542400,
                "website": "https://example.ai",
            }]
        }
        transport = FakeTransport(text=html, json_data=payload)
        result = YCDirectoryCollector(transport).collect()

        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        self.assertEqual(result.signals[0].company_name, "Example AI")
        self.assertEqual(result.signals[0].source, Source.YC_DIRECTORY)
        self.assertEqual(result.signals[0].status, SignalStatus.CONFIRMED_YC)
        self.assertIn("YCCompany_By_Launch_Date_production", transport.calls[1][1])

    def test_speedrun_parses_next_data_and_labels_a16z(self):
        next_data = {
            "props": {"pageProps": {"companies": [{
                "id": "sr-1",
                "slug": "rocket-labs",
                "name": "Rocket Labs",
                "cohort": "SR006",
                "preamble": "Games infrastructure",
                "website_url": "https://rocket.test",
                "founder_set": [{"first_name": "Ada", "last_name": "Li"}],
            }]}}
        }
        html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(next_data) + "</script>"
        result = SpeedrunCollector(FakeTransport(text=html)).collect()

        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        self.assertEqual(result.signals[0].company_name, "Rocket Labs")
        self.assertEqual(result.signals[0].founder_name, "Ada Li")
        self.assertEqual(result.signals[0].status, SignalStatus.CONFIRMED_SPEEDRUN)
        self.assertEqual(result.signals[0].metadata["program_owner"], "a16z")

    def test_speedrun_supports_current_paginated_next_data_shape(self):
        company = {"id": "sr-2", "slug": "second", "name": "Second", "cohort": "SR006"}
        next_data = {"props": {"pageProps": {"companies": {"count": 1, "results": [company]}}}}
        html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(next_data) + "</script>"
        result = SpeedrunCollector(FakeTransport(text=html)).collect()
        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        self.assertEqual(result.signals[0].company_name, "Second")

    def test_x_without_key_is_not_configured(self):
        result = XCollector(FakeTransport(), api_key="").collect()
        self.assertEqual(result.health, CollectorHealth.NOT_CONFIGURED)
        self.assertEqual(result.signals, [])

    def test_x_uses_announcement_intent_not_generic_discussion(self):
        payload = {"tweets": [{
            "id": "123",
            "text": "We were accepted into Y Combinator S26!",
            "url": "https://x.com/founder/status/123",
            "createdAt": "2026-08-30T08:00:00Z",
            "author": {"userName": "founder", "name": "Ada Li"},
        }]}
        transport = FakeTransport(json_data=payload)
        result = XCollector(transport, api_key="secret").collect()

        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        params = transport.calls[0][3]
        self.assertIn("accepted into YC", params["query"])
        self.assertIn("-filter:retweets", params["query"])
        self.assertEqual(result.signals[0].source, Source.X)

    def test_x_skips_malformed_rows_without_losing_valid_posts(self):
        payload = {"tweets": [
            None,
            {"id": ""},
            {
                "id": "124",
                "text": "We got into YC and are building @signalworks.",
                "author": {"userName": "founder", "name": "Ada Li"},
            },
        ]}
        result = XCollector(FakeTransport(json_data=payload), api_key="secret", queries=("one",)).collect()

        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        self.assertEqual(len(result.signals), 1)
        self.assertEqual(result.signals[0].company_name, "@signalworks")

    def test_x_keeps_successful_query_when_another_query_fails(self):
        valid = {"tweets": [{
            "id": "125",
            "text": "We were accepted into Y Combinator.",
            "author": {"userName": "founder", "name": "Ada Li"},
        }]}
        transport = SequencedTransport([RuntimeError("request failed with a secret"), valid])
        result = XCollector(transport, api_key="secret", queries=("one", "two")).collect()

        self.assertEqual(result.health, CollectorHealth.DEGRADED)
        self.assertEqual(len(result.signals), 1)
        self.assertIn("1 of 2", result.diagnostic)
        self.assertNotIn("secret", result.diagnostic)

    def test_x_sends_accept_header(self):
        transport = FakeTransport(json_data={"tweets": []})
        XCollector(transport, api_key="secret", queries=("one",)).collect()
        self.assertEqual(transport.calls[0][2]["Accept"], "application/json")

    def test_x_retries_rate_limit_once_and_keeps_result(self):
        valid = {"tweets": [{
            "id": "126",
            "text": "We got into @speedrun.",
            "author": {"userName": "founder"},
        }]}
        waits = []
        transport = SequencedTransport([
            HttpError("rate limited", status_code=429, retry_after=0.01),
            valid,
        ])
        result = XCollector(
            transport,
            api_key="secret",
            queries=("one",),
            sleep=waits.append,
        ).collect()

        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        self.assertEqual(len(result.signals), 1)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(waits, [2.0])

    def test_linkedin_uses_public_tinyfish_search_without_session_cookie(self):
        payload = {"results": [{
            "title": "Ada Li on LinkedIn",
            "snippet": "We are joining YC S26 with Rocket Labs.",
            "url": "https://www.linkedin.com/posts/ada_launch-123",
        }]}
        transport = FakeTransport(json_data=payload)
        result = LinkedInCollector(transport, api_key="tiny-secret").collect()

        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        headers = transport.calls[0][2]
        params = transport.calls[0][3]
        self.assertEqual(headers, {"X-API-Key": "tiny-secret"})
        self.assertIn("site:linkedin.com/posts", params["query"])
        self.assertNotIn("Cookie", headers)

    def test_linkedin_rejects_non_linkedin_search_result(self):
        payload = {"results": [{
            "title": "Impostor",
            "snippet": "We are joining YC",
            "url": "https://example.com/not-linkedin",
        }]}
        result = LinkedInCollector(FakeTransport(json_data=payload), api_key="key").collect()
        self.assertEqual(result.health, CollectorHealth.ACTIVE)
        self.assertEqual(result.signals, [])


if __name__ == "__main__":
    unittest.main()
