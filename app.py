import os

from flask import Flask

import config
from db import init_db  # re-exported: tests and the startup check use it from app
from routes.books import bp as books_bp
from routes.loans import bp as loans_bp
from routes.members import bp as members_bp
from routes.reports import bp as reports_bp

app = Flask(__name__)
for blueprint in (books_bp, members_bp, loans_bp, reports_bp):
    app.register_blueprint(blueprint)

if not os.path.exists(config.DB_PATH):
    init_db()
