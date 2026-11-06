import sqlite3

from db import connect


def _connect():
    conn = connect()
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_one(sql, params=()):
    conn = _connect()
    try:
        row = conn.execute(sql, params).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def _fetch_all(sql, params=()):
    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _transaction(work):
    conn = _connect()
    try:
        result = work(conn)
        conn.commit()
        return result
    finally:
        conn.close()


# ---------- books ----------


def list_books(available_only=False):
    if available_only:
        return _fetch_all("SELECT * FROM books WHERE available = 1")
    return _fetch_all("SELECT * FROM books")


def get_book(book_id):
    return _fetch_one("SELECT * FROM books WHERE id = ?", (book_id,))


def count_books():
    return _fetch_one("SELECT COUNT(*) AS n FROM books")["n"]


def add_book(title, author, isbn):
    def work(conn):
        cur = conn.execute(
            "INSERT INTO books (title, author, isbn, available) VALUES (?, ?, ?, 1)",
            (title, author, isbn),
        )
        return dict(conn.execute("SELECT * FROM books WHERE id = ?", (cur.lastrowid,)).fetchone())

    return _transaction(work)


def delete_book(book_id):
    _transaction(lambda conn: conn.execute("DELETE FROM books WHERE id = ?", (book_id,)))


# ---------- members ----------


def list_members():
    return _fetch_all("SELECT * FROM members")


def get_member(member_id):
    return _fetch_one("SELECT * FROM members WHERE id = ?", (member_id,))


def get_member_by_email(email):
    return _fetch_one("SELECT * FROM members WHERE email = ?", (email,))


def add_member(name, email, member_type):
    def work(conn):
        cur = conn.execute(
            "INSERT INTO members (name, email, type) VALUES (?, ?, ?)",
            (name, email, member_type),
        )
        return dict(conn.execute("SELECT * FROM members WHERE id = ?", (cur.lastrowid,)).fetchone())

    return _transaction(work)


# ---------- loans ----------


def list_loans():
    return _fetch_all("SELECT * FROM loans")


def get_loan(loan_id):
    return _fetch_one("SELECT * FROM loans WHERE id = ?", (loan_id,))


def loans_for_member(member_id):
    return _fetch_all("SELECT * FROM loans WHERE member_id = ?", (member_id,))


def create_loan(book_id, member_id, due_date, checked_out):
    def work(conn):
        cur = conn.execute(
            "INSERT INTO loans (book_id, member_id, due_date, checked_out) VALUES (?, ?, ?, ?)",
            (book_id, member_id, due_date, checked_out),
        )
        conn.execute("UPDATE books SET available = 0 WHERE id = ?", (book_id,))
        return dict(conn.execute("SELECT * FROM loans WHERE id = ?", (cur.lastrowid,)).fetchone())

    return _transaction(work)


def mark_returned(loan_id, book_id, fine):
    def work(conn):
        conn.execute("UPDATE loans SET returned = 1, fine = ? WHERE id = ?", (fine, loan_id))
        conn.execute("UPDATE books SET available = 1 WHERE id = ?", (book_id,))
        return dict(conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone())

    return _transaction(work)


def renew_loan(loan_id, new_due_date):
    def work(conn):
        conn.execute(
            "UPDATE loans SET due_date = ?, renewals = renewals + 1 WHERE id = ?",
            (new_due_date, loan_id),
        )
        return dict(conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone())

    return _transaction(work)


def mark_fine_paid(loan_id):
    def work(conn):
        conn.execute("UPDATE loans SET fine_paid = 1 WHERE id = ?", (loan_id,))
        return dict(conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone())

    return _transaction(work)


def open_loans_with_details():
    return _fetch_all(
        """
        SELECT loans.id AS loan_id, books.title AS title, members.name AS member,
               loans.due_date AS due_date
        FROM loans
        JOIN books ON books.id = loans.book_id
        JOIN members ON members.id = loans.member_id
        WHERE loans.returned = 0
        """
    )
