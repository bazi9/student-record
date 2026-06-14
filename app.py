"""
Student Records Management System
COM6301 Undergraduate Project

A Flask web application with:
  - User registration & login (passwords hashed, session-based auth)
  - Student records CRUD (add / view / edit / delete)
  - A rankings / leaderboard page based on student scores

Works with SQLite locally and PostgreSQL on Render (set via DATABASE_URL).
"""

import os
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Configuration -----------------------------------------------------------
# SECRET_KEY signs the session cookie. On Render, set it as an environment
# variable. Locally it falls back to a dev value.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# DATABASE_URL is provided by Render's PostgreSQL add-on. Locally we use SQLite.
database_url = os.environ.get("DATABASE_URL", "sqlite:///records.db")
# Render gives "postgres://..."; SQLAlchemy needs "postgresql://..."
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# --- Database models ---------------------------------------------------------
class User(db.Model):
    """An account that can log in and manage records."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Student(db.Model):
    """A student record. `score` is used for the rankings page."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    score = db.Column(db.Float, default=0)          # used for rankings
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# --- Auth helpers ------------------------------------------------------------
def current_user():
    """Return the logged-in User object, or None."""
    uid = session.get("user_id")
    if uid is None:
        return None
    return db.session.get(User, uid)


def login_required(view):
    """Decorator: redirect to login if no user in session."""
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    """Make `user` available in every template."""
    return {"user": current_user()}


# --- Routes: authentication --------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        # Validation
        if not username or not email or not password:
            flash("All fields are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            flash(f"Welcome back, {user.username}.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# --- Routes: student records (CRUD) -----------------------------------------
@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    students = (
        Student.query.filter_by(owner_id=user.id)
        .order_by(Student.name.asc())
        .all()
    )
    return render_template("dashboard.html", students=students)


@app.route("/students/add", methods=["POST"])
@login_required
def add_student():
    user = current_user()
    student = Student(
        student_id=request.form.get("student_id", "").strip(),
        name=request.form.get("name", "").strip(),
        age=_to_int(request.form.get("age")),
        email=request.form.get("email", "").strip(),
        address=request.form.get("address", "").strip(),
        score=_to_float(request.form.get("score")),
        owner_id=user.id,
    )
    if not student.name:
        flash("Student name is required.", "error")
    else:
        db.session.add(student)
        db.session.commit()
        flash("Student added.", "success")
    return redirect(url_for("dashboard"))


@app.route("/students/<int:student_pk>/edit", methods=["POST"])
@login_required
def edit_student(student_pk):
    user = current_user()
    student = db.session.get(Student, student_pk)
    if not student or student.owner_id != user.id:
        abort(404)
    student.student_id = request.form.get("student_id", "").strip()
    student.name = request.form.get("name", "").strip()
    student.age = _to_int(request.form.get("age"))
    student.email = request.form.get("email", "").strip()
    student.address = request.form.get("address", "").strip()
    student.score = _to_float(request.form.get("score"))
    db.session.commit()
    flash("Student updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/students/<int:student_pk>/delete", methods=["POST"])
@login_required
def delete_student(student_pk):
    user = current_user()
    student = db.session.get(Student, student_pk)
    if not student or student.owner_id != user.id:
        abort(404)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted.", "success")
    return redirect(url_for("dashboard"))


# --- Routes: rankings / leaderboard -----------------------------------------
@app.route("/rankings")
@login_required
def rankings():
    user = current_user()
    ranked = (
        Student.query.filter_by(owner_id=user.id)
        .order_by(Student.score.desc(), Student.name.asc())
        .all()
    )
    return render_template("rankings.html", students=ranked)


# --- Small helpers -----------------------------------------------------------
def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


# --- Create tables on startup ------------------------------------------------
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
