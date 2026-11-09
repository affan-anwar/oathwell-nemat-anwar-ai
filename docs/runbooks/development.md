# Runbook: Development
1. One phase at a time. One branch per small change: `phase-N/short-name`.
2. Write the test first for rules (policy, guard, state machine).
3. Run `pytest` in `apps/api` before every commit.
4. A pull request needs tests, a docs update, and no secrets (check `.env` is not staged).
5. Never claim a feature works without a test run or a real-account check. Record results in the PR.
6. Update `docs/FEATURES.md` when a feature changes.
