# Short demo script

Target length: 60–90 seconds.

1. Show the repository root and briefly open `README.md`.
2. Show `.env.example` only. Do **not** show the real `.env`, terminal environment, API keys, or Slack token.
3. Run:

   ```powershell
   $env:PYTHONPATH = "$PWD\src"
   python -m yc_launch_monitor health --json
   ```

4. Show that all four sources are present in the latest healthy run.
5. Open Slack and show one confirmed YC Directory alert and one `EARLY SIGNAL` alert from X or LinkedIn. Keep the original post link visible.
6. Run one additional scan or show the recorded repeat-run result with `new_or_changed: 0`, `delivered: 0`, and `failed_deliveries: 0`.
7. Open `http://localhost:8080/api/status` while `serve` is running and mention the eight-hour cadence and persistent SQLite state.
8. Finish by showing `docs/POND_AGENT_SETUP.md` and explain that Pond can supervise the public health endpoint after deployment.

Recommended voiceover:

> This is a persistent single-workspace Slack monitor for the official YC Directory, the separate a16z Speedrun directory, X, and public LinkedIn launch posts. It classifies first-person founder announcements as early signals, stores content hashes in SQLite, and sends only incremental alerts. The status endpoint exposes each collector's health for ongoing supervision.
