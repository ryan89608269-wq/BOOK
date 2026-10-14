# Smart Errorbook public review schedule test

This is a **synthetic, dry-run-only** subset of the local Smart Errorbook project. It copies the project's scheduling core and a mock fixture, then runs a standalone schedule preview. It does not contain the private Notion integration, a review ledger, credentials, or real learner data.

Run locally:

```sh
python -m pip install pytest tzdata
python -m pytest -q
python -m public_review --business-date 2026-10-15 --since-date 2026-10-14
```

The preview uses Asia/Taipei business dates. Daily 19:07 in Taiwan equals 11:07 UTC. The GitHub workflow is **manual only**. A delayed or missed run can be repeated with the same `business_date` and optional `since_date`; it creates the same read-only report and never contacts Notion.

The default branch contains a minimal `workflow_dispatch` bootstrap because GitHub requires the workflow to exist on the default branch before a test-branch manual dispatch. The `phase10-bc-test` branch contains the actual dry-run steps. Neither branch configures `schedule` or any Notion secret.
