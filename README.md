# Student Records Management System

A full-stack web application for managing student records, built for the
COM6301 Undergraduate Project.

## Features
- User registration and login (passwords hashed with Werkzeug, session-based auth)
- Role-based access control (RBAC) with three roles:
  - **Administrator** — manage user accounts and roles, plus full access to all records
  - **Moderator** — add/edit/delete any student record (cannot manage roles)
  - **User** — add records and edit/delete only the records they created
- Student records CRUD (add, view, edit, delete)
- Admin User Management page (assign roles, delete accounts)
- SQLite for local development, PostgreSQL in production (Render)

## Roles
The account that registers with the `ADMIN_EMAIL` address automatically becomes
Administrator. All other sign-ups are Users by default; an Administrator can
promote them to Moderator or Administrator from the Manage Users page.

## Tech stack
- Python (Flask, Flask-SQLAlchemy)
- HTML / CSS (Jinja2 templates)
- Gunicorn (production WSGI server)

## Run locally
```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

## Deploy on Render
1. Push this repository to GitHub.
2. In Render, create a new **Web Service** from this repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
3. Create a **PostgreSQL** database in Render and copy its Internal Connection String.
4. Add environment variables to the web service:
   - `DATABASE_URL` = the PostgreSQL connection string
   - `SECRET_KEY` = any long random string
5. Deploy. Tables are created automatically on first start.

Alternatively, use the included `render.yaml` (Blueprint) to provision the web
service and database automatically.
