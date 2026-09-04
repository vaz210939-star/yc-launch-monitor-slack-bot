import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yc_launch_monitor.config import Settings


class ConfigTests(unittest.TestCase):
    def test_dotenv_is_loaded_without_overriding_process_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            dotenv = Path(directory) / ".env"
            dotenv.write_text(
                "\n".join([
                    "TWITTERAPIIO_API_KEY=file-twitter-key",
                    "TINYFISH_API_KEY='file-tinyfish-key'",
                    "SLACK_DELIVERY_ENABLED=true",
                    "MONITOR_INTERVAL_SECONDS=3600",
                ]),
                encoding="utf-8",
            )
            previous_cwd = Path.cwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ, {"TWITTERAPIIO_API_KEY": "process-twitter-key"}, clear=True):
                    settings = Settings.from_env()
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(settings.twitter_api_key, "process-twitter-key")
        self.assertEqual(settings.tinyfish_api_key, "file-tinyfish-key")
        self.assertTrue(settings.slack_delivery_enabled)
        self.assertEqual(settings.interval_seconds, 3600)


if __name__ == "__main__":
    unittest.main()
