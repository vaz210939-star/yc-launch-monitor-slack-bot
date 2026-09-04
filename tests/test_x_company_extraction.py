import unittest

from yc_launch_monitor.collectors import XCollector


class FakeTransport:
    def get_json(self, url, *, headers=None, params=None):
        return {
            "tweets": [{
                "id": "collaborator-handle",
                "text": (
                    "I got into @speedrun SR007! Building with @KaziFarabi "
                    "and Jose Serrano."
                ),
                "author": {"userName": "founder", "name": "Founder"},
            }]
        }


class XCompanyExtractionTests(unittest.TestCase):
    def test_collaborator_after_with_is_not_reported_as_company(self):
        result = XCollector(
            FakeTransport(),
            api_key="secret",
            queries=("one",),
            sleep=lambda _: None,
        ).collect()

        self.assertEqual(result.signals[0].company_name, "Unknown company")


if __name__ == "__main__":
    unittest.main()
