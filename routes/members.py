from flask import Blueprint, jsonify, request

import repository as repo
import rules
from serializers import member_json, loan_summary_json, money
from validation import check

bp = Blueprint("members", __name__)


@bp.route("/members", methods=["GET"])
def list_members():
    return jsonify([member_json(m) for m in repo.list_members()])


@bp.route("/members/<int:member_id>", methods=["GET"])
def get_member(member_id):
    member = repo.get_member(member_id)
    if member is None:
        return jsonify({"error": "member not found"}), 404
    return jsonify(member_json(member))


@bp.route("/members", methods=["POST"])
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


@bp.route("/members/<int:member_id>/loans", methods=["GET"])
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
