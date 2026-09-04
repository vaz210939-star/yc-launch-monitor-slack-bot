import unittest

from yc_launch_monitor.classification import classify_social_signal
from yc_launch_monitor.domain import Signal, SignalStatus, Source


def social(text: str, *, source: Source = Source.X) -> Signal:
    return Signal(
        source=source,
        source_id="quality-1",
        source_url="https://example.com/post/1",
        company_name="Unknown company",
        founder_name="Example Founder",
        text=text,
    )


class LaunchQualityTests(unittest.TestCase):
    def test_historical_recollection_is_not_an_early_signal(self):
        result = classify_social_signal(social(
            "I remember when we first got into YC; it changed how we chose customers."
        ))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)

    def test_before_yc_context_is_not_an_early_signal(self):
        result = classify_social_signal(social(
            "Our earliest hires backed us before we got into YC or had external validation."
        ))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)

    def test_meta_monitoring_post_is_not_an_early_signal(self):
        result = classify_social_signal(social(
            "Want to know which startup founders say 'we got into YC' before the list appears?"
        ))
        self.assertEqual(result.status, SignalStatus.NEEDS_REVIEW)

    def test_thought_as_a_verb_does_not_hide_a_fresh_announcement(self):
        result = classify_social_signal(social(
            "Since we just got into YC, everyone got curious about Box. "
            "I thought you would want to see our launch video."
        ))
        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)

    def test_company_is_inferred_from_yc_parenthetical(self):
        result = classify_social_signal(social(
            "I was accepted to YC S26 and went all-in on Shepherd (YC S26) with my cofounders.",
            source=Source.LINKEDIN,
        ))
        self.assertEqual(result.status, SignalStatus.EARLY_SIGNAL)
        self.assertEqual(result.company_name, "Shepherd")


if __name__ == "__main__":
    unittest.main()
