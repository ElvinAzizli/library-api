from rules import fine_for_due_date


def money(x):
    return round(float(x), 2)


def book_json(b):
    return {
        "id": b["id"],
        "title": b["title"],
        "author": b["author"],
        "isbn": b["isbn"],
        "available": bool(b["available"]),
    }


def member_json(m):
    return {"id": m["id"], "name": m["name"], "email": m["email"], "type": m["type"]}


def loan_json(loan):
    return {
        "id": loan["id"],
        "book_id": loan["book_id"],
        "member_id": loan["member_id"],
        "due_date": loan["due_date"],
        "returned": bool(loan["returned"]),
        "fine": money(loan["fine"]),
        "fine_paid": bool(loan["fine_paid"]),
        "renewals": loan["renewals"],
        "checked_out": loan["checked_out"],
    }


def loan_json_with_fine(loan):
    data = loan_json(loan)
    current = loan["fine"] if loan["returned"] else fine_for_due_date(loan["due_date"])
    data["current_fine"] = money(current)
    return data


def loan_summary_json(loan):
    return {
        "id": loan["id"],
        "book_id": loan["book_id"],
        "due_date": loan["due_date"],
        "returned": bool(loan["returned"]),
        "fine": money(loan["fine"]),
        "fine_paid": bool(loan["fine_paid"]),
    }
