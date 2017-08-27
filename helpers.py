from flask import redirect, render_template, request, session, url_for
from functools import wraps
from cs50 import SQL

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


def get_username(db):
    """Returns username from userid """

    if session.get("user_id") is None:
        username = ""
    else:
        username = db.execute(
                "SELECT username FROM users WHERE id = :id",
                id=session.get("user_id"))

        username = username[0]["username"]

    return username
