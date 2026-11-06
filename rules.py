from datetime import date, timedelta

import config


def days_late(due_date, today=None):
    today = today or date.today()
    return (today - date.fromisoformat(due_date)).days


def fine_for_days(days):
    return max(0, days) * config.FINE_PER_DAY


def fine_for_due_date(due_date, today=None):
    return fine_for_days(days_late(due_date, today))


def loan_limit(member_type):
    return config.LOAN_LIMITS.get(member_type, config.DEFAULT_LOAN_LIMIT)


def default_due_date(today=None):
    today = today or date.today()
    return (today + timedelta(days=config.LOAN_DAYS)).isoformat()


def renewed_due_date(due_date):
    return (date.fromisoformat(due_date) + timedelta(days=config.RENEWAL_DAYS)).isoformat()
