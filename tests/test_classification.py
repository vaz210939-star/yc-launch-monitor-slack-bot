import unittest

from yc_launch_monitor.classification import classify_social_signal
from yc_launch_monitor.domain import Signal, SignalStatus, Source


def social(text: str) -> Signal:
    return Signal(
        source=Source.X,
        source_id="post-1",
        source_url="https://x.com/a/status/1",
        company_name="Unknown company",
        founder_name="Ada Li",
        text=text,
    )


class ClassificationTests(unittest.TestCase):
    def test_first_person_acceptance_is_early_signal(self):
        result = classify_social_signal(social("We were accepted into Y Combinator S26 today!"))
        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_contracted_first_person_acceptance_is_early_signal(self):
        result = classify_social_signal(social("We've been accepted into YC and start next month!"))
        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)

    def test_discussion_is_not_misclassified_as_founder_announcement(self):
        result = classify_social_signal(social("Do YC founders get better fundraising terms? Discussing the trend."))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)
        self.assertLess(result.confidence, 0.5)

    def test_negated_acceptance_is_not_an_early_signal(self):
        result = classify_social_signal(social("We haven't been accepted into YC, but we will keep building."))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)
        self.assertLess(result.confidence, 0.5)

    def test_rejection_language_is_not_an_early_signal(self):
        result = classify_social_signal(social("YC F26 was our first application. We didn't make it through."))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)
        self.assertLess(result.confidence, 0.5)

    def test_friend_acceptance_is_not_an_early_signal(self):
        result = classify_social_signal(social("My friend recently got into YC. A crazy moment."))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)

    def test_competitor_acceptance_is_not_an_early_signal(self):
        result = classify_social_signal(social("I realized our direct competitor was accepted into YC."))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)

    def test_marketing_condition_is_not_an_early_signal(self):
        result = classify_social_signal(social("If you just got into Speedrun, come talk to us."))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)

    def test_explicit_company_announcement_is_an_early_signal(self):
        result = classify_social_signal(social(
            "Excited to announce that Space is joining @a16z @speedrun this summer. "
            "We are building a new file system."
        ))
        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)
        self.assertEqual(result.program, "a16z Speedrun")

    def test_speedrun_handle_announcement_is_an_early_signal(self):
        result = classify_social_signal(social("We got into @speedrun SR007 and start next week."))
        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)
        self.assertEqual(result.program, "a16z Speedrun")

    def test_reconcile_with_official_company_confirms_yc(self):
        item = social("We are joining YC S26 with Rocket Labs")
        item.company_name = "Rocket Labs"
        result = classify_social_signal(item, yc_company_names={"rocket labs"})
        self.assertEqual(result.status, SignalStatus.CONFIRMED_YC)


if __name__ == "__main__":
    unittest.main()
