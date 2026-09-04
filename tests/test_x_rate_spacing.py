import unittest

from yc_launch_monitor.collectors import XCollector


class EmptyTransport:
    def get_json(self, url, *, headers=None, params=None):
        return {"tweets": []}


class XRateSpacingTests(unittest.TestCase):
    def test_queries_are_spaced_to_avoid_provider_rate_limit(self):
        waits = []
        result = XCollector(
            EmptyTransport(),
            api_key="secret",
            queries=("yc", "speedrun"),
            sleep=waits.append,
        ).collect()

        self.assertEqual(result.health.value, "active")
        self.assertEqual(waits, [6.0])


if __name__ == "__main__":
    unittest.main()
