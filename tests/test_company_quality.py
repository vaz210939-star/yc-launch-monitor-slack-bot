import unittest

from yc_launch_monitor.classification import classify_social_signal
from yc_launch_monitor.domain import Signal, SignalStatus, Source


class CompanyQualityTests(unittest.TestCase):
    def test_teammate_after_with_is_not_reported_as_company(self):
        item = Signal(
            source=Source.X,
            source_id="speedrun-team",
            source_url="https://x.com/founder/status/1",
            company_name="Unknown company",
            founder_name="Founder",
            text=(
                "I got into @speedrun SR007! I left to build an intelligence node in space. "
                "Building with Kazi Farabi and Jose Serrano."
            ),
        )

        result = classify_social_signal(item)

        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)
        self.assertEqual(result.company_name, "Unknown company")

    def test_generic_with_my_friends_is_not_reported_as_company(self):
        item = Signal(
            source=Source.X,
            source_id="speedrun-friends",
            source_url="https://x.com/founder/status/2",
            company_name="Unknown company",
            founder_name="Founder",
            text="We're thrilled to share that we've been accepted into @speedrun SR007 to build with my friends.",
        )

        result = classify_social_signal(item)

        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)
        self.assertEqual(result.company_name, "Unknown company")


if __name__ == "__main__":
    unittest.main()
