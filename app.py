import os

from flask import Flask, jsonify, request

import config
import notifier
import repository as repo
import rules
from db import init_db  # re-exported: the tests and the startup check use it from app
from serializers import book_json, member_json, loan_json, loan_json_with_fine, loan_summary_json, money
from validation import check

app = Flask(__name__)


# ---------- books ----------


@app.route("/books", methods=["GET"])
def list_books():
    books = repo.list_books(available_only=request.args.get("available") == "true")
    return jsonify([book_json(b) for b in books])


@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    book = repo.get_book(book_id)
    if book is None:
        return jsonify({"error": "book not found"}), 404
    return jsonify(book_json(book))


@app.route("/books", methods=["POST"])
def create_book():
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("author"):
        return jsonify({"error": "title and author are required"}), 400
    if not check(data.get("isbn"), "isbn"):
        return jsonify({"error": "invalid isbn"}), 400
    book = repo.add_book(data["title"], data["author"], data["isbn"])
    return jsonify(book_json(book)), 201


@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    book = repo.get_book(book_id)
    if book is None:
        return jsonify({"error": "book not found"}), 404
    if book["available"] == 0:
        return jsonify({"error": "book is on loan"}), 409
    repo.delete_book(book_id)
    return "", 204


# ---------- members ----------


@app.route("/members", methods=["GET"])
def list_members():
    return jsonify([member_json(m) for m in repo.list_members()])


@app.route("/members/<int:member_id>", methods=["GET"])
def get_member(member_id):
    member = repo.get_member(member_id)
    if member is None:
        return jsonify({"error": "member not found"}), 404
    return jsonify(member_json(member))


@app.route("/members", methods=["POST"])
def create_member():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    if not check(data.get("email"), "email"):
        return jsonify({"error": "invalid email"}), 400
    member_type = data.get("type", "student")
    if not check(member_type, "member_type"):
        return jsonify({"error": "type must be student or staff"}), 400
    if repo.get_member_by_email(data["email"]) is not None:
        return jsonify({"error": "email already registered"}), 409
    member = repo.add_member(data["name"], data["email"], member_type)
    return jsonify(member_json(member)), 201


@app.route("/members/<int:member_id>/loans", methods=["GET"])
def member_loans(member_id):
    member = repo.get_member(member_id)
    if member is None:
        return jsonify({"error": "member not found"}), 404
    loans = repo.loans_for_member(member_id)
    remaining = rules.loan_limit(member["type"]) - rules.open_loan_count(loans)
    return jsonify(
        {
            "loans": [loan_summary_json(loan) for loan in loans],
            "total_owed": money(rules.amount_owed(loans)),
            "loans_remaining": remaining,
        }
    )


# ---------- loans ----------


@app.route("/loans", methods=["GET"])
def list_loans():
    overdue_only = request.args.get("overdue") == "true"
    result = []
    for loan in repo.list_loans():
        if overdue_only and (loan["returned"] == 1 or rules.days_late(loan["due_date"]) <= 0):
            continue
        result.append(loan_json_with_fine(loan))
    return jsonify(result)


@app.route("/loans/<int:loan_id>", methods=["GET"])
def get_loan(loan_id):
    loan = repo.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    return jsonify(loan_json_with_fine(loan))


@app.route("/loans", methods=["POST"])
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


@app.route("/loans/<int:loan_id>/return", methods=["POST"])
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


@app.route("/loans/<int:loan_id>/renew", methods=["POST"])
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


@app.route("/loans/<int:loan_id>/pay-fine", methods=["POST"])
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


# ---------- reports ----------


@app.route("/reports/overdue", methods=["GET"])
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


@app.route("/reports/summary", methods=["GET"])
def report_summary():
    loans = repo.list_loans()
    return jsonify(
        {
            "total_books": repo.count_books(),
            "on_loan": rules.open_loan_count(loans),
            "fines_outstanding": money(rules.amount_owed(loans)),
        }
    )


if not os.path.exists(config.DB_PATH):
    init_db()
