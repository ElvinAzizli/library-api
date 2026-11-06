from flask import Blueprint, jsonify

import repository as repo
import rules
from serializers import money

bp = Blueprint("reports", __name__)


@bp.route("/reports/overdue", methods=["GET"])
def report_overdue():
    items = []
    total = 0
    for row in repo.open_loans_with_details():
        late = rules.days_late(row["due_date"])
        if late > 0:
            fine = rules.fine_for_days(late)
            total += fine
            items.append(
                {
                    "loan_id": row["loan_id"],
                    "title": row["title"],
                    "member": row["member"],
                    "days_late": late,
                    "fine": money(fine),
                }
            )
    return jsonify({"items": items, "total_fines": money(total)})


@bp.route("/reports/summary", methods=["GET"])
def report_summary():
    loans = repo.list_loans()
    return jsonify(
        {
            "total_books": repo.count_books(),
            "on_loan": rules.open_loan_count(loans),
            "fines_outstanding": money(rules.amount_owed(loans)),
        }
    )
