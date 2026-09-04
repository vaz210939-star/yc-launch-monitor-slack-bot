import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from yc_launch_monitor.health import start_health_server
from yc_launch_monitor.store import Store


class HealthServerTests(unittest.TestCase):
    def test_health_and_status_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "state.db")
            server = start_health_server(store, "127.0.0.1", 0)
            try:
                port = server.server_address[1]
                with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
                    self.assertEqual(json.load(response), {"ok": True})
                with urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
                    self.assertTrue(json.load(response)["ready"])
            finally:
                server.shutdown()
                server.server_close()
                store.close()


if __name__ == "__main__":
    unittest.main()
