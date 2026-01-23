---
title: Aether Core
emoji: 🏢
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 6.3.0
app_file: app.py
pinned: false
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

## How to test Adaptive Throttling (Level 47)

- Simulate an error burst: temporarily inject log events via the UI by enqueuing tasks that will fail (e.g., invalid plugin name) multiple times within ~30 seconds, or manually call `log_event("WORKER_ERROR", {"error": "simulated"})` in a local run to exceed the burst threshold.
- Verify throttle state changes: open the UI Status JSON and confirm the new `throttle` section updates (`mode`, `score`, `effective_budget`, `effective_sched_sleep_sec`, `last_change`, `reasons`) and watch for `THROTTLE_DOWN` / `THROTTLE_UP` entries in the tail logs.
