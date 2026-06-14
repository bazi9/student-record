"""
Student Records Management System
COM6301 Undergraduate Project

A Flask web application with role-based access control (RBAC):
  - Administrator : manage user accounts and roles + full data access
  - Moderator     : add/edit/delete ANY student record (cannot manage roles)
  - User          : add records and edit/delete ONLY records they created

Auth is session-based with hashed passwords.
Works with SQLite locally and PostgreSQL on Render (via DATABASE_URL).
"""

import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Configuration -----------------------------------------------------------
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Whoever registers with this email automatically becomes Administrator.
# Configurable on Render via the ADMIN_EMAIL environment variable.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "infern91@gmail.com").strip().lower()

database_url = os.environ.get("DATABASE_URL", "sqlite:///records.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Role constants
ROLE_ADMIN = "Administrator"
ROLE_MODERATOR = "Moderator"
ROLE_USER = "User"
ALL_ROLES = [ROLE_ADMIN, ROLE_MODERATOR, ROLE_USER]


# --- Database models ---------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship("Student", backref="owner", lazy=True)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def can_manage_all_records(self):
        # Admins and Moderators can manage every record
        return self.role in (ROLE_ADMIN, ROLE_MODERATOR)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    score = db.Column(db.Float, default=0)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# --- Auth helpers ------------------------------------------------------------
def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return db.session.get(User, uid)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """Only Administrators may access (used for user management)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        if not user.is_admin:
            flash("Administrator access required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def can_edit_record(user, student):
    """User can edit own records; Admin/Moderator can edit any."""
    if user is None or student is None:
        return False
    return user.can_manage_all_records or student.owner_id == user.id


@app.context_processor
def inject_globals():
    return {"user": current_user(), "ROLE_ADMIN": ROLE_ADMIN,
            "ROLE_MODERATOR": ROLE_MODERATOR, "ROLE_USER": ROLE_USER}


# --- Routes: authentication --------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

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
            # Hardcoded admin email becomes Administrator; everyone else is User
            role = ROLE_ADMIN if email == ADMIN_EMAIL else ROLE_USER
            user = User(username=username, email=email, role=role)
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
    if user.can_manage_all_records:
        # Admin & Moderator see all records
        students = Student.query.order_by(Student.name.asc()).all()
    else:
        # Regular user sees only their own
        students = (Student.query.filter_by(owner_id=user.id)
                    .order_by(Student.name.asc()).all())
    return render_template("dashboard.html", students=students)


@app.route("/students/add", methods=["POST"])
@login_required
def add_student():
    user = current_user()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Student name is required.", "error")
        return redirect(url_for("dashboard"))
    student = Student(
        student_id=request.form.get("student_id", "").strip(),
        name=name,
        age=_to_int(request.form.get("age")),
        email=request.form.get("email", "").strip(),
        address=request.form.get("address", "").strip(),
        score=_to_float(request.form.get("score")),
        owner_id=user.id,
    )
    db.session.add(student)
    db.session.commit()
    flash("Student added.", "success")
    return redirect(url_for("dashboard"))


@app.route("/students/<int:student_pk>/edit", methods=["POST"])
@login_required
def edit_student(student_pk):
    user = current_user()
    student = db.session.get(Student, student_pk)
    if not student or not can_edit_record(user, student):
        abort(403)
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
    if not student or not can_edit_record(user, student):
        abort(403)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted.", "success")
    return redirect(url_for("dashboard"))


# --- Routes: user management (Admin only) -----------------------------------
@app.route("/users")
@admin_required
def manage_users():
    users = User.query.order_by(User.created_at.asc()).all()
    return render_template("users.html", users=users, roles=ALL_ROLES)


@app.route("/users/<int:user_pk>/role", methods=["POST"])
@admin_required
def change_role(user_pk):
    admin = current_user()
    target = db.session.get(User, user_pk)
    if not target:
        abort(404)
    new_role = request.form.get("role", "")
    if new_role not in ALL_ROLES:
        flash("Invalid role.", "error")
    elif target.id == admin.id:
        flash("You cannot change your own role.", "error")
    else:
        target.role = new_role
        db.session.commit()
        flash(f"{target.username} is now a {new_role}.", "success")
    return redirect(url_for("manage_users"))


@app.route("/users/<int:user_pk>/delete", methods=["POST"])
@admin_required
def delete_user(user_pk):
    admin = current_user()
    target = db.session.get(User, user_pk)
    if not target:
        abort(404)
    if target.id == admin.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("manage_users"))
    # Remove the user's records too
    Student.query.filter_by(owner_id=target.id).delete()
    db.session.delete(target)
    db.session.commit()
    flash(f"User {target.username} deleted.", "success")
    return redirect(url_for("manage_users"))


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


# --- Create tables / lightweight migration on startup ------------------------
def ensure_schema():
    """Create tables, and add the `role` column if upgrading an existing DB."""
    db.create_all()
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    cols = [c["name"] for c in inspector.get_columns("user")]
    if "role" not in cols:
        # Add the new column to a pre-existing users table (Postgres & SQLite)
        with db.engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE \"user\" ADD COLUMN role VARCHAR(20) "
                "NOT NULL DEFAULT 'User'"
            ))
        # Promote the configured admin email if that account already exists
        existing_admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        if existing_admin:
            existing_admin.role = ROLE_ADMIN
            db.session.commit()


with app.app_context():
    ensure_schema()


if __name__ == "__main__":
    app.run(debug=True)
