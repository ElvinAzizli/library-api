import config


def _send(to_email, subject, body):
    with open(config.OUTBOX_PATH, "a") as f:
        f.write("TO: " + to_email + " | SUBJECT: " + subject + " | BODY: " + body + "\n")


def _amount(x):
    return str(round(float(x), 2))


def checkout(email, title):
    _send(email, "Book checked out", "You checked out " + title)


def renewed(email, title):
    _send(email, "Loan renewed", "You renewed " + title)


def returned(email, title, fine):
    _send(email, "Book returned", "You returned " + title + ". Fine: $" + _amount(fine))


def fine_paid(email, amount):
    _send(email, "Fine paid", "We received $" + _amount(amount))
