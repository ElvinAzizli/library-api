from flask import Blueprint, jsonify, request

import repository as repo
from serializers import book_json
from validation import check

bp = Blueprint("books", __name__)


@bp.route("/books", methods=["GET"])
def list_books():
    books = repo.list_books(available_only=request.args.get("available") == "true")
    return jsonify([book_json(b) for b in books])


@bp.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    book = repo.get_book(book_id)
    if book is None:
        return jsonify({"error": "book not found"}), 404
    return jsonify(book_json(book))


@bp.route("/books", methods=["POST"])
def create_book():
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("author"):
        return jsonify({"error": "title and author are required"}), 400
    if not check(data.get("isbn"), "isbn"):
        return jsonify({"error": "invalid isbn"}), 400
    book = repo.add_book(data["title"], data["author"], data["isbn"])
    return jsonify(book_json(book)), 201


@bp.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    book = repo.get_book(book_id)
    if book is None:
        return jsonify({"error": "book not found"}), 404
    if book["available"] == 0:
        return jsonify({"error": "book is on loan"}), 409
    repo.delete_book(book_id)
    return "", 204
