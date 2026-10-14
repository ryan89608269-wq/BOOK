"""Public, fixture-only review schedule harness derived from the local scheduler.

There is deliberately no Notion client, credential loader, write mode, or user data input.
"""
import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from errorbook.core import Question, Review, TZ, aware, due_today, replay_reviews

RUN_TIME = time(19, 7)
FIXTURE = Path(__file__).parent / "fixtures" / "actions-mock.json"


def business_date(now):
    local = aware(now)
    return local.date() if local.time() >= RUN_TIME else local.date() - timedelta(days=1)


def scheduled_at(day):
    local = datetime.combine(day, RUN_TIME, tzinfo=TZ)
    return {"taipei": local.isoformat(), "utc": local.astimezone(timezone.utc).isoformat()}


def _load_fixture():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1 or set(raw) != {"schema_version", "questions", "reviews"}:
        raise ValueError("Unexpected synthetic fixture format")
    questions = []
    for item in raw["questions"]:
        if not item["stable_id"].startswith("MOCK-"):
            raise ValueError("Only synthetic MOCK questions are allowed")
        fields = dict(item)
        fields["next_review_at"] = datetime.fromisoformat(fields["next_review_at"])
        questions.append(Question(**fields))
    reviews = []
    for item in raw["reviews"]:
        fields = dict(item)
        fields["reviewed_at"] = datetime.fromisoformat(fields["reviewed_at"])
        reviews.append(Review(**fields))
    return questions, reviews


def dry_run_days(now, *, target_date=None, since_date=None):
    questions, reviews = _load_fixture()
    latest = business_date(now)
    target = date.fromisoformat(target_date) if target_date else latest
    if target > latest:
        raise ValueError("Cannot plan a future scheduled run")
    start = date.fromisoformat(since_date) if since_date else target
    if start > target or (target - start).days > 30:
        raise ValueError("Backfill must be an ascending window of at most 31 days")
    rows = []
    for offset in range((target - start).days + 1):
        day = start + timedelta(days=offset)
        at = datetime.combine(day, RUN_TIME, tzinfo=TZ)
        projected = []
        count = 0
        for question in questions:
            history = sorted((r for r in reviews if r.question_id == question.stable_id and r.reviewed_at <= at),
                             key=lambda r: r.reviewed_at)
            identifiers = [(r.question_id, r.reviewed_at.isoformat()) for r in history]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError("Duplicate synthetic review event")
            projected.append(replay_reviews(question, history))
            count += len(history)
        rows.append({"date": day.isoformat(), "scheduled_at": scheduled_at(day),
                     "due_ids": [q.stable_id for q in due_today(projected, at)],
                     "review_events_counted": count})
    return {"status": "dry-run", "scope": "synthetic-public-fixture", "timezone": "Asia/Taipei",
            "remote_writes": 0, "days": rows, "backfill_requires_manual_dispatch": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-date")
    parser.add_argument("--since-date")
    args = parser.parse_args()
    report = dry_run_days(datetime.now(timezone.utc), target_date=args.business_date,
                          since_date=args.since_date)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
