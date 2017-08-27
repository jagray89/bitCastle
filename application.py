# 'places' in radio.db adapted from https://www.maxmind.com/en/free-world-cities-database

import os
import re
import string

from flask import Flask, jsonify, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_jsglue import JSGlue
from passlib.apps import custom_app_context as pwd_context

from tempfile import mkdtemp
from cs50 import SQL

from helpers import *

# configure application
app = Flask(__name__)
JSGlue(app)

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# connect to SQLite db
db = SQL("sqlite:///radio.db")

@app.route("/")
def index():
    """Default map rendered"""

    # check Google API key set
    if not os.environ.get("API_KEY"):
        raise RuntimeError("API_KEY not set")

    # check for user logged in
    if "user_id" in session:
        favourites = db.execute("""
                SELECT * FROM
                (SELECT * FROM favourites WHERE user_id = :uid) a
                JOIN
                (SELECT * FROM stations) b
                ON a.station_id = b.id""", uid=session["user_id"])
    else:
        favourites = []

    return render_template("index.html", key=os.environ.get("API_KEY"), username=get_username(db), favourites=favourites)


# *** this route draws from CS50 PSET8 distribution code *** #
@app.route("/search")
def search():
    """Search for places that match query."""

    # no search query retrieved
    if not request.args.get("q"):
        raise RuntimeError("missing search parameter q")

    # store search query
    q = request.args.get("q")

    # remove any punctuation
    for punc in string.punctuation:
        q = q.replace(punc, '')

    # prevents http 500 error when string started with punctuation
    if q == "":
        q = "xyz"

    # split multi-word query
    elements = []
    for word in q.split():
        # add to array, concat with SQL wildcard
        elements.append(word + '%')

    if len(elements) == 1:
        # assuming: city // state
        station_list = db.execute("""
                SELECT * FROM
                (SELECT * FROM places
                WHERE (city LIKE :q OR state LIKE :q)) a
                JOIN
                (SELECT * FROM stations) b
                ON a.city = b.city
                AND a.state = b.state""",
                q=elements[0])

        # assuming: name // call
        station_list += db.execute("""
                SELECT * FROM
                (SELECT * FROM stations
                WHERE (name LIKE :q OR call LIKE :q)) a
                JOIN
                (SELECT * FROM places) b
                ON a.city = b.city
                AND a.state = b.state""",
                q=elements[0])

    elif len(elements) == 2:
        # assuming: city city
        station_list = db.execute("""
                SELECT * FROM
                (SELECT * FROM places
                WHERE city LIKE :q) a
                JOIN
                (SELECT * FROM stations) b
                ON a.city = b.city
                AND a.state = b.state""",
                q=elements[0]+elements[1])

        # assuming: city, state
        station_list += db.execute("""
                SELECT * FROM
                (SELECT * FROM places
                WHERE (city LIKE :q1 AND state LIKE :q2)) a
                JOIN
                (SELECT * FROM stations) b
                ON a.city = b.city
                AND a.state = b.state""",
                q1=elements[0], q2=elements[1])

        # assuming: name / call, city / state
        station_list += db.execute("""
                SELECT * FROM
                (SELECT * FROM stations
                WHERE (name LIKE :q1 OR call LIKE :q1)
                AND (city LIKE :q2 OR state LIKE :q2)) a
                JOIN
                (SELECT * FROM places) b
                ON a.city = b.city
                AND a.state = b.state""",
                q1=elements[0], q2=elements[1])

    elif len(elements) == 3:
        # assuming: city city, state
        station_list = db.execute("""
                SELECT * FROM
                (SELECT * FROM places
                WHERE (city LIKE :q1 AND state LIKE :q2)) a
                JOIN
                (SELECT * FROM stations) b
                ON a.city = b.city
                AND a.state = b.state""",
                q1=elements[0]+elements[1], q2=elements[2])

        # assuming: name / call, city city
        station_list += db.execute("""
                SELECT * FROM
                (SELECT * FROM stations
                WHERE (name LIKE :q1 OR call LIKE :q1)
                AND city LIKE :q2) a
                JOIN
                (SELECT * FROM places) b
                ON a.city = b.city
                AND a.state = b.state""",
                q1=elements[0], q2=elements[1]+elements[2])

        # assuming: name / call, city, state
        station_list += db.execute("""
                SELECT * FROM
                (SELECT * FROM stations
                WHERE (name LIKE :q1 OR call LIKE :q1)
                AND (city LIKE :q2 AND state LIKE :q3)) a
                JOIN
                (SELECT * FROM places) b
                ON a.city = b.city
                AND a.state = b.state""",
                q1=elements[0], q2=elements[1], q3=elements[2])

    elif len(elements) == 4:
        # assuming: name / call, city city, state
        station_list = db.execute("""
                SELECT * FROM
                (SELECT * FROM stations
                WHERE (name LIKE :q1 OR call LIKE :q1)
                AND (city LIKE :q2 AND state LIKE :q3)) a
                JOIN
                (SELECT * FROM places) b
                ON a.city = b.city
                AND a.state = b.state""",
                q1=elements[0], q2=elements[1]+elements[2], q3=elements[3])

    return jsonify(station_list)


# *** this route draws heavily from CS50 PSET8 distribution code *** #
@app.route("/update")
def update():
    """Get stations within map window view """

    # ensure parameters are present
    if not request.args.get("sw"):
        raise RuntimeError("missing sw")
    if not request.args.get("ne"):
        raise RuntimeError("missing ne")

    # ensure parameters are in lat,lng format
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("sw")):
        raise RuntimeError("invalid sw")
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("ne")):
        raise RuntimeError("invalid ne")

    # explode southwest corner into two variables
    (sw_lat, sw_lng) = [float(s) for s in request.args.get("sw").split(",")]

    # explode northeast corner into two variables
    (ne_lat, ne_lng) = [float(s) for s in request.args.get("ne").split(",")]

    # find 10 cities within view, pseudorandomly chosen if more within view
    if (sw_lng <= ne_lng):

        # doesn't cross the antimeridian
        station_list = db.execute("""SELECT * FROM
                                (SELECT * FROM places
                                WHERE :sw_lat <= lat
                                AND lat <= :ne_lat
                                AND (:sw_lng <= lng AND lng <= :ne_lng)) a
                                JOIN
                                (SELECT * FROM stations) b
                                ON a.city = b.city
                                AND a.state = b.state""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    else:

        # crosses the antimeridian
        station_list = db.execute("""SELECT * FROM
                                (SELECT * FROM places
                                WHERE :sw_lat <= lat
                                AND lat <= :ne_lat
                                AND (:sw_lng <= lng OR lng <= :ne_lng)) a
                                JOIN
                                (SELECT * FROM stations) b
                                ON a.city = b.city
                                AND a.state = b.state""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    return jsonify(station_list)


@app.route("/lookup")
def lookup():
    """Return list of stations for marker clicked"""
    """ OR station info for current selection"""

    # get arguments present, ignore missing arguments
    if request.args.get("city"):
        city = request.args.get("city")
    else:
        city = ""

    if request.args.get("state"):
        state = request.args.get("state")
    else:
        state = ""

    if request.args.get("stream"):
        url = request.args.get("stream")
    else:
        url = ""

    # get stations based on location OR stream url
    stations = db.execute("""
            SELECT * FROM stations
            WHERE city = :c AND state = :s
            OR url_stream = :u""",
            c=city, s=state, u=url)

    return jsonify(stations)


@app.route("/stations")
def stations():

    # sort parameter present
    if request.args.get("sort"):

        sort = request.args.get("sort")

        if sort == "name":
            station_list = db.execute("SELECT * FROM stations ORDER BY name")
        elif sort == "call":
            station_list = db.execute("SELECT * FROM stations ORDER BY call")
        elif sort == "place":
            station_list = db.execute("SELECT * FROM stations ORDER BY state, city")
        elif sort == "freq":
            station_list = db.execute("SELECT * FROM stations ORDER BY freq")
        elif sort == "power":
            station_list = db.execute("SELECT * FROM stations ORDER BY power")

    # default sort by place
    else:
        station_list = db.execute("SELECT * FROM stations ORDER BY state, city")

    return render_template("stations.html", username=get_username(db), stations=station_list)


@app.route("/favourite", methods=["GET", "POST"])
@login_required
def favourite():
    """Add, delete, or view favourites"""

    # user is adding or deleting a favourite
    if request.method == "POST":

        # user is adding a station from 'stations.html'
        if request.form.get("add"):

            # max limit of 5 favourites per user
            if len(db.execute(
                    "SELECT * FROM favourites WHERE user_id = :uid",
                    uid=session["user_id"])) > 4:

                return redirect(url_for("stations", error="limit"))

            # remember id of station to add
            station_id = request.form.get("add")

            # check user hasn't already favourited station
            if db.execute("""
                    SELECT * FROM favourites
                    WHERE user_id = :uid AND station_id = :sid""",
                    uid=session["user_id"], sid=station_id):

                return redirect(url_for("stations", error="taken"))

            # add favourite to db for user
            db.execute("""
                    INSERT INTO favourites (user_id, station_id)
                    VALUES (:uid, :sid)""",
                    uid=session["user_id"], sid=station_id)

            return redirect(url_for("stations", success=True))

        # user is deleting a station from 'favourites.html'
        elif request.form.get("delete"):

            station_id = request.form.get("delete")

            db.execute("""
                    DELETE FROM favourites
                    WHERE user_id = :uid AND station_id = :sid""",
                    uid=session["user_id"], sid=station_id)

            return redirect(url_for("favourite", deleted=True))

    # user is viewing favourites via GET
    else:
        favourites = db.execute("""
                SELECT * FROM
                (SELECT * FROM favourites WHERE user_id = :uid) a
                JOIN
                (SELECT * FROM stations) b
                ON a.station_id = b.id""", uid=session["user_id"])

        return render_template("favourites.html", username=get_username(db), favourites=favourites)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # page accessed via POST
    if request.method == "POST":

        # safety checks if browser doesn't support JS checks
        if not request.form.get("username"):
            return redirect(url_for("register", error="username"))
        if not request.form.get("password"):
            return redirect(url_for("register", error="password"))
        if not request.form.get("confirmation"):
            return redirect(url_for("register", error="confirmation"))
        if request.form.get("password") != request.form.get("confirmation"):
            return redirect(url_for("register", error="mismatch"))

        # username taken check
        if db.execute(
                "SELECT id FROM users WHERE username = :username",
                username=request.form.get("username")):
            return redirect(url_for("register", error="taken"))

        # INSERT new user into db
        hash = pwd_context.encrypt(request.form.get("password"))
        session["user_id"] = db.execute("""
                INSERT INTO users (username, password)
                VALUES (:username, :hash)""",
                username=request.form.get("username"), hash=hash)

        # redirect user to home page
        return redirect(url_for("index"))

    # page accessed via GET
    else:
        return render_template("register.html")


@app.route("/login", methods=["POST"])
def login():
    """Log user in"""

    # forget any user_id
    session.clear()

    # ensure username was submitted
    if not request.form.get("username"):
        return redirect(url_for("index", error=True))
    # ensure password was submitted
    elif not request.form.get("password"):
        return redirect(url_for("index", error=True))

    # query database for username
    rows = db.execute(
            "SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"))

    # ensure username exists and password is correct
    if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["password"]):
        return redirect(url_for("index", error=True))

    # remember which user has logged in
    session["user_id"] = rows[0]["id"]

    # redirect user to the page from which they submitted the login form
    if request.form.get("submit") == "/":
        return redirect(url_for("index"))
    else:
        return redirect(url_for(request.form.get("submit").strip('/')))


@app.route("/logout")
def logout():
    """Log user out"""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("index"))


@app.route("/about", methods=["GET"])
def about():
    """About page"""

    return render_template("about.html", username=get_username(db))
