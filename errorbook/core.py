"""Local-only models, scheduling, and reporting. All dates are Asia/Taipei aware."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
INTERVALS = (1, 3, 7, 14, 30)

@dataclass(frozen=True)
class Question:
    stable_id: str
    subject: str
    chapter: str
    error_type: str
    next_review_at: datetime
    stage: int = 0
    mastery: float = 0.0
    source: str = ""
    difficulty: int = 3
    status: str = "active"
    image_reference: str = ""
    explanation: str = ""
    prompt: str = ""

@dataclass(frozen=True)
class Review:
    question_id: str
    reviewed_at: datetime
    correct: bool
    duration_seconds: int = 0
    confidence: int = 0

def aware(dt):
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timezone-aware datetime required")
    return dt.astimezone(TZ)

def unique_questions(questions):
    result = {}
    for q in questions:
        if q.stable_id in result:
            raise ValueError(f"Duplicate stable_id: {q.stable_id}")
        aware(q.next_review_at)
        if (not q.stable_id.strip() or not 1 <= q.difficulty <= 5 or
                not 0 <= q.mastery <= 1 or not 0 <= q.stage < len(INTERVALS) or
                q.status not in {"active", "mastered", "paused", "archived"}):
            raise ValueError(f"Invalid question: {q.stable_id!r}")
        result[q.stable_id] = q
    return result

def schedule(question, correct, reviewed_at):
    when = aware(reviewed_at)
    stage = min(question.stage + 1, len(INTERVALS) - 1) if correct else 0
    mastery = min(1.0, question.mastery + .2) if correct else max(0.0, question.mastery - .25)
    return replace(question, stage=stage, mastery=round(mastery, 2), next_review_at=when + timedelta(days=INTERVALS[stage]))


def schedule_review(question, review):
    """Correct but uncertain (confidence 1-2) repeats tomorrow; 0 means unspecified."""
    if question.stable_id != review.question_id:
        raise ValueError("Review question_id mismatch")
    if not 0 <= review.confidence <= 5:
        raise ValueError("Confidence must be 0..5")
    if review.duration_seconds < 0:
        raise ValueError("Review duration must be non-negative")
    if review.correct and review.confidence in (1, 2):
        when = aware(review.reviewed_at)
        return replace(question, stage=0, mastery=round(min(1.0, question.mastery + .05), 2),
                       next_review_at=when + timedelta(days=1))
    return schedule(question, review.correct, review.reviewed_at)


def replay_reviews(question, reviews):
    """Replay one question's events in input order; reject ambiguous history."""
    unique_questions([question])
    current = question
    previous = None
    for review in reviews:
        at = aware(review.reviewed_at)
        if review.question_id != question.stable_id:
            raise ValueError("Review question_id mismatch")
        if previous is not None and at <= previous:
            raise ValueError("Review events must be strictly chronological")
        current = schedule_review(current, review)
        previous = at
    return current

def due_today(questions, now):
    """The daily list includes any question due before the end of Taiwan's day."""
    today = aware(now)
    end = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    return due(questions, end)

def due(questions, now):
    today = aware(now)
    unique_questions(questions)
    return sorted((q for q in questions if q.status in {"active", "mastered"} and
                   aware(q.next_review_at) <= today), key=lambda q:(q.next_review_at, q.mastery, q.stable_id))

def statistics(questions, reviews, now):
    qs = unique_questions(questions)
    today = aware(now)
    by_subject = defaultdict(lambda: [0, 0])
    by_chapter = defaultdict(lambda: [0, 0])
    trends = {str(days): {"total": 0, "correct": 0} for days in (7, 30)}
    for r in reviews:
        if r.question_id not in qs:
            raise ValueError(f"Unknown question: {r.question_id}")
        at = aware(r.reviewed_at)
        if r.duration_seconds < 0 or not 0 <= r.confidence <= 5:
            raise ValueError("Invalid review duration or confidence")
        by_subject[qs[r.question_id].subject][0] += int(r.correct)
        by_subject[qs[r.question_id].subject][1] += 1
        by_chapter[f"{qs[r.question_id].subject} / {qs[r.question_id].chapter}"][0] += int(r.correct)
        by_chapter[f"{qs[r.question_id].subject} / {qs[r.question_id].chapter}"][1] += 1
        for days in (7,30):
            if today.date() - timedelta(days=days - 1) <= at.date() <= today.date():
                trends[str(days)]["total"] += 1
                trends[str(days)]["correct"] += int(r.correct)
    def rates(group):
        return {k: {"correct":v[0],"total":v[1],"accuracy":round(v[0]/v[1],3) if v[1] else None} for k,v in sorted(group.items())}
    return {"questions":len(qs), "reviews":len(reviews), "due":len(due(questions, today)), "by_subject":rates(by_subject), "by_chapter":rates(by_chapter), "error_types":dict(Counter(q.error_type for q in questions)), "trends":trends}
