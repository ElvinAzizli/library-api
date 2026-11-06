from flask import Blueprint, jsonify, request

import config
import notifier
import repository as repo
import rules
from serializers import loan_json, loan_json_with_fine
from validation import check

bp = Blueprint("loans", __name__)


@bp.route("/loans", methods=["GET"])
def list_loans():
    overdue_only = request.args.get("overdue") == "true"
    result = []
    for loan in repo.list_loans():
        if overdue_only and (loan["returned"] == 1 or rules.days_late(loan["due_date"]) <= 0):
            continue
        result.append(loan_json_with_fine(loan))
    return jsonify(result)


@bp.route("/loans/<int:loan_id>", methods=["GET"])
def get_loan(loan_id):
    loan = repo.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    return jsonify(loan_json_with_fine(loan))


@bp.route("/loans", methods=["POST"])
def create_loan():
    data = request.get_json(silent=True) or {}
    if not data.get("book_id") or not data.get("member_id"):
        return jsonify({"error": "book_id and member_id are required"}), 400
    if data.get("due_date") and not check(data["due_date"], "date"):
        return jsonify({"error": "invalid due_date"}), 400

    book = repo.get_book(data["book_id"])
    if book is None:
        return jsonify({"error": "book not found"}), 404
    member = repo.get_member(data["member_id"])
    if member is None:
        return jsonify({"error": "member not found"}), 404
    if book["available"] == 0:
        return jsonify({"error": "book is not available"}), 409

    loans = repo.loans_for_member(data["member_id"])
    if rules.amount_owed(loans) > 0:
        return jsonify({"error": "member has unpaid fines"}), 409
    if rules.open_loan_count(loans) >= rules.loan_limit(member["type"]):
        return jsonify({"error": "loan limit reached"}), 409

    due_date = data.get("due_date") or rules.default_due_date()
    loan = repo.create_loan(data["book_id"], data["member_id"], due_date, rules.today_iso())
    notifier.checkout(member["email"], book["title"])
    return jsonify(loan_json(loan)), 201


@bp.route("/loans/<int:loan_id>/return", methods=["POST"])
def return_book(loan_id):
    loan = repo.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    if loan["returned"] == 1:
        return jsonify({"error": "loan already returned"}), 409

    fine = rules.fine_for_due_date(loan["due_date"])
    updated = repo.mark_returned(loan_id, loan["book_id"], fine)
    member = repo.get_member(loan["member_id"])
    book = repo.get_book(loan["book_id"])
    notifier.returned(member["email"], book["title"], fine)
    return jsonify(loan_json(updated))


@bp.route("/loans/<int:loan_id>/renew", methods=["POST"])
def renew_loan(loan_id):
    loan = repo.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    if loan["returned"] == 1:
        return jsonify({"error": "loan already returned"}), 409
    if rules.days_late(loan["due_date"]) > 0:
        return jsonify({"error": "overdue loans cannot be renewed"}), 409
    if loan["renewals"] >= config.MAX_RENEWALS:
        return jsonify({"error": "loan was already renewed"}), 409

    updated = repo.renew_loan(loan_id, rules.renewed_due_date(loan["due_date"]))
    member = repo.get_member(loan["member_id"])
    book = repo.get_book(loan["book_id"])
    notifier.renewed(member["email"], book["title"])
    return jsonify(loan_json(updated))


@bp.route("/loans/<int:loan_id>/pay-fine", methods=["POST"])
def pay_fine(loan_id):
    loan = repo.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    if loan["returned"] == 0:
        return jsonify({"error": "return the book before paying"}), 409
    if loan["fine"] <= 0 or loan["fine_paid"] == 1:
        return jsonify({"error": "no fine to pay"}), 409

    updated = repo.mark_fine_paid(loan_id)
    member = repo.get_member(loan["member_id"])
    notifier.fine_paid(member["email"], loan["fine"])
    return jsonify(loan_json(updated))
