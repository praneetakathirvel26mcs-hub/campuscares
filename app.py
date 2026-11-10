import os
import sqlite3
import csv
import io
import smtplib
import ssl
import re
import json
from pathlib import Path
from dataclasses import dataclass
import joblib
from email.message import EmailMessage
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, Response, session
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "CHANGE_THIS_SECRET_BEFORE_DEPLOYMENT")
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = os.environ.get("DATABASE_PATH", str(BASE_DIR / "complaints.db"))
MODEL_PATH = BASE_DIR / "complaint_classifier.joblib"
METRICS_PATH = BASE_DIR / "model_metrics.json"
REVIEW_CONFIDENCE_THRESHOLD = float(os.environ.get("REVIEW_CONFIDENCE_THRESHOLD", "0.55"))

# Configure a unique admin password using environment variables before deployment.
ADMIN_USERNAME = os.environ.get("CAMPUS_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("CAMPUS_ADMIN_PASSWORD", "")
MAINTENANCE_USERNAME = os.environ.get("MAINTENANCE_USERNAME", "maintenance")
MAINTENANCE_PASSWORD = os.environ.get("MAINTENANCE_PASSWORD", "")

# Set these environment variables to enable email notifications.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USERNAME)

# Replace each placeholder with the official inbox for that department.
DEPARTMENT_EMAILS = {
    "Maintenance": os.environ.get("EMAIL_MAINTENANCE", ""),
    "Electrical": os.environ.get("EMAIL_ELECTRICAL", ""),
    "IT": os.environ.get("EMAIL_IT", ""),
    "Sanitation": os.environ.get("EMAIL_SANITATION", ""),
    "Academic": os.environ.get("EMAIL_ACADEMIC", ""),
    "Hostel": os.environ.get("EMAIL_HOSTEL", ""),
    "Other": os.environ.get("EMAIL_GENERAL", "")
}

CATEGORY_DEPARTMENTS = {
    "Maintenance": "Maintenance Department",
    "Electrical": "Electrical Department",
    "IT": "IT Department",
    "Sanitation": "Sanitation Department",
    "Academic": "Academic Affairs",
    "Hostel": "Hostel Administration",
    "Other": "General Administration"
}
URGENT_WORDS = ["urgent", "emergency", "danger", "fire", "shock", "injury",
                "unsafe", "leak", "smoke", "short circuit"]

# Four ML categories required by G08. Existing user-selectable categories remain available.
ML_CATEGORIES = ("IT", "Electrical", "Maintenance", "Sanitation")

@dataclass
class Complaint:
    """Structured complaint submitted by a student."""
    student_name: str
    student_id: str
    title: str
    description: str
    category: str
    location: str

class RoutingRule:
    """Map categories to the responsible department."""
    @staticmethod
    def department_for(category):
        return CATEGORY_DEPARTMENTS.get(category, CATEGORY_DEPARTMENTS["Other"])

class ComplaintManager:
    """Coordinate classification, review flags, persistence and summaries."""
    def __init__(self, classifier=None, threshold=REVIEW_CONFIDENCE_THRESHOLD):
        self.classifier = classifier
        self.threshold = threshold

    def classify(self, title, description, selected_category):
        text = f"{title}. {description}"
        if self.classifier is None:
            return selected_category, None, None, True, "Classifier model is not available; manual review required."
        if selected_category not in ML_CATEGORIES:
            return selected_category, None, None, True, "Category is outside the four-category classifier; manual review required."
        probabilities = self.classifier.predict_proba([text])[0]
        classes = list(self.classifier.classes_)
        best_index = int(probabilities.argmax())
        predicted = str(classes[best_index])
        confidence = float(probabilities[best_index])
        reasons = []
        if confidence < self.threshold:
            reasons.append(f"Low classifier confidence ({confidence:.0%}).")
        if predicted != selected_category:
            reasons.append(f"Selected category '{selected_category}' differs from suggested category '{predicted}'.")
        manual_review = bool(reasons)
        # Preserve the category the student selected. The model provides a suggestion;
        # it never silently changes the user's selected category.
        return selected_category, predicted, confidence, manual_review, " ".join(reasons)

    @staticmethod
    def summary():
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
            review = db.execute("SELECT COUNT(*) FROM complaints WHERE manual_review=1").fetchone()[0]
            by_category = db.execute("SELECT category, COUNT(*) AS total FROM complaints GROUP BY category ORDER BY category").fetchall()
            by_status = db.execute("SELECT status, COUNT(*) AS total FROM complaints GROUP BY status ORDER BY status").fetchall()
        return {"total": total, "manual_review": review,
                "by_category": [dict(r) for r in by_category],
                "by_status": [dict(r) for r in by_status]}

try:
    CLASSIFIER = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None
except Exception:
    app.logger.exception("Could not load complaint classifier")
    CLASSIFIER = None
complaint_manager = ComplaintManager(CLASSIFIER)

def get_db():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                department TEXT NOT NULL,
                location TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL,
                suggested_category TEXT,
                model_confidence REAL,
                manual_review INTEGER NOT NULL DEFAULT 0,
                review_reason TEXT NOT NULL DEFAULT ''
            )
        """)
        # Safe migration: add new G08 columns to existing databases without deleting data.
        existing = {row[1] for row in db.execute("PRAGMA table_info(complaints)").fetchall()}
        additions = {
            "suggested_category": "TEXT",
            "model_confidence": "REAL",
            "manual_review": "INTEGER NOT NULL DEFAULT 0",
            "review_reason": "TEXT NOT NULL DEFAULT ''"
        }
        for column, definition in additions.items():
            if column not in existing:
                db.execute(f"ALTER TABLE complaints ADD COLUMN {column} {definition}")

def detect_priority(text):
    text = text.lower()
    return "High" if any(word in text for word in URGENT_WORDS) else "Normal"

def send_department_email(complaint):
    recipient = DEPARTMENT_EMAILS.get(complaint["category"], "")
    if not recipient:
        app.logger.warning("No department email configured for category %s", complaint["category"])
        return False, "Email not configured for this department."

    if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM]):
        app.logger.warning("SMTP environment variables are incomplete.")
        return False, "SMTP settings are incomplete."

    message = EmailMessage()
    message["Subject"] = f"Campus complaint #{complaint['id']}: {complaint['title']}"
    message["From"] = MAIL_FROM
    message["To"] = recipient
    message.set_content(
        f"""A new campus complaint has been submitted.

Complaint ID: {complaint['id']}
Category: {complaint['category']}
Department: {complaint['department']}
Priority: {complaint['priority']}
Student name: {complaint['student_name']}
Student ID: {complaint['student_id']}
Location: {complaint['location']}
Submitted at: {complaint['created_at']}

Title:
{complaint['title']}

Description:
{complaint['description']}

Please review this complaint and update its status in the Campus Complaint Management System.
"""
    )
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)
    return True, "Email notification sent."

def maintenance_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_maintenance"):
            flash("Maintenance staff login is required to access this dashboard.", "error")
            return redirect(url_for("maintenance_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_or_maintenance_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not (session.get("is_admin") or session.get("is_maintenance")):
            flash("Please log in to update complaint status.", "error")
            return redirect(url_for("maintenance_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Administrator login is required to access reports.", "error")
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORY_DEPARTMENTS)

@app.route("/submit", methods=["POST"])
def submit():
    fields = {
        "student_name": request.form.get("student_name", "").strip(),
        "student_id": request.form.get("student_id", "").strip(),
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "category": request.form.get("category", "").strip(),
        "location": request.form.get("location", "").strip()
    }
    if not all(fields.values()):
        flash("Please complete all fields and select a category.", "error")
        return redirect(url_for("index"))

    if fields["category"] not in CATEGORY_DEPARTMENTS:
        flash("Please select a valid complaint category.", "error")
        return redirect(url_for("index"))

    complaint_input = Complaint(**fields)

    # Keep the existing category-selection workflow, while providing an ML suggestion.
    if complaint_manager.classifier is None:
        assigned_category = fields["category"]
        suggested_category, confidence = None, None
        manual_review = True
        review_reason = "Classifier model is not available; manual review required."
    elif fields["category"] not in ML_CATEGORIES:
        assigned_category = fields["category"]
        suggested_category, confidence = None, None
        manual_review = True
        review_reason = "Selected category is outside the four-category ML model; manual review required."
    else:
        result = complaint_manager.classify(complaint_input.title, complaint_input.description, complaint_input.category)
        assigned_category, suggested_category, confidence, manual_review, review_reason = result
    department = RoutingRule.department_for(assigned_category)
    priority = detect_priority(fields["title"] + " " + fields["description"])
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO complaints
            (student_name, student_id, title, description, category, department,
             location, priority, status, created_at, suggested_category, model_confidence,
             manual_review, review_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?, ?, ?)
        """, (fields["student_name"], fields["student_id"], fields["title"],
              fields["description"], assigned_category, department, fields["location"],
              priority, created_at, suggested_category, confidence, int(manual_review), review_reason))
        complaint_id = cursor.lastrowid
        row = db.execute("SELECT * FROM complaints WHERE id=?", (complaint_id,)).fetchone()
        complaint = dict(row)

    # Email errors do not discard the saved complaint.
    try:
        email_sent, email_message = send_department_email(complaint)
    except Exception:
        app.logger.exception("Department email notification failed for complaint #%s", complaint_id)
        email_sent, email_message = False, "Complaint saved, but the email could not be sent. Check SMTP and department email settings."

    return render_template("submitted.html", complaint_id=complaint_id,
                           category=assigned_category, department=department,
                           priority=priority, email_sent=email_sent,
                           email_message=email_message, suggested_category=suggested_category,
                           model_confidence=confidence, manual_review=manual_review,
                           review_reason=review_reason)

@app.route("/track", methods=["GET", "POST"])
def track():
    complaint = None
    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", "").strip()
        student_id = request.form.get("student_id", "").strip()
        with get_db() as db:
            complaint = db.execute(
                "SELECT id, student_id, title, category, department, location, priority, status, created_at "
                "FROM complaints WHERE id=? AND student_id=?",
                (complaint_id, student_id)
            ).fetchone()
        if not complaint:
            flash("Complaint not found. Check the complaint ID and student ID.", "error")
    return render_template("track.html", complaint=complaint)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if not ADMIN_PASSWORD:
            flash("Admin password is not configured. Set CAMPUS_ADMIN_PASSWORD in the terminal, then restart the app.", "error")
        elif username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            session["admin_username"] = username
            flash("Administrator login successful.", "success")
            destination = request.args.get("next", "")
            if not destination.startswith("/") or destination.startswith("//"):
                destination = url_for("admin")
            return redirect(destination)
        else:
            flash("Incorrect administrator username or password.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/maintenance/login", methods=["GET", "POST"])
def maintenance_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if not MAINTENANCE_PASSWORD:
            flash("Maintenance password is not configured. Set MAINTENANCE_PASSWORD in your environment variables.", "error")
        elif username == MAINTENANCE_USERNAME and password == MAINTENANCE_PASSWORD:
            session.clear()
            session["is_maintenance"] = True
            session["maintenance_username"] = username
            flash("Maintenance login successful.", "success")
            destination = request.args.get("next", "")
            if not destination.startswith("/") or destination.startswith("//"):
                destination = url_for("maintenance_dashboard")
            return redirect(destination)
        else:
            flash("Incorrect maintenance username or password.", "error")
    return render_template("maintenance_login.html")

@app.route("/maintenance/logout")
def maintenance_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/maintenance/dashboard")
@maintenance_required
def maintenance_dashboard():
    status = request.args.get("status", "All")
    category = request.args.get("category", "All")
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    if status != "All":
        query += " AND status=?"
        params.append(status)
    if category != "All":
        query += " AND category=?"
        params.append(category)
    query += " ORDER BY CASE priority WHEN 'High' THEN 0 ELSE 1 END, id DESC"
    with get_db() as db:
        complaints = db.execute(query, params).fetchall()
        counts = {
            "total": db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
            "pending": db.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0],
            "progress": db.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0],
            "resolved": db.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0],
            "review": db.execute("SELECT COUNT(*) FROM complaints WHERE manual_review=1").fetchone()[0]
        }
    return render_template("maintenance_dashboard.html", complaints=complaints,
                           status=status, category=category,
                           categories=list(CATEGORY_DEPARTMENTS.keys()), counts=counts)

@app.route("/maintenance/update/<int:complaint_id>", methods=["POST"])
@maintenance_required
def maintenance_update(complaint_id):
    new_status = request.form.get("status", "")
    if new_status not in {"Pending", "In Progress", "Resolved", "Rejected"}:
        flash("Invalid status.", "error")
    else:
        with get_db() as db:
            exists = db.execute("SELECT id FROM complaints WHERE id=?", (complaint_id,)).fetchone()
            if not exists:
                flash("Complaint not found.", "error")
                return redirect(url_for("maintenance_dashboard"))
            db.execute("UPDATE complaints SET status=? WHERE id=?", (new_status, complaint_id))
        flash(f"Complaint #{complaint_id} updated to {new_status}.", "success")
    return redirect(url_for("maintenance_dashboard"))

@app.route("/admin")
@admin_required
def admin():
    status = request.args.get("status", "All")
    category = request.args.get("category", "All")
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    review_filter = request.args.get("review", "All")
    if review_filter == "Review":
        query += " AND manual_review=1"
    elif review_filter == "Clear":
        query += " AND manual_review=0"
    if status != "All":
        query += " AND status=?"
        params.append(status)
    if category != "All":
        query += " AND category=?"
        params.append(category)
    query += " ORDER BY CASE priority WHEN 'High' THEN 0 ELSE 1 END, id DESC"
    with get_db() as db:
        complaints = db.execute(query, params).fetchall()
        counts = {
            "total": db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
            "pending": db.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0],
            "progress": db.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0],
            "resolved": db.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0],
            "manual_review": db.execute("SELECT COUNT(*) FROM complaints WHERE manual_review=1").fetchone()[0]
        }
    model_metrics = {}
    if METRICS_PATH.exists():
        try:
            model_metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            model_metrics = {}
    return render_template("admin.html", complaints=complaints, status=status,
                           category=category, categories=list(CATEGORY_DEPARTMENTS.keys()),
                           counts=counts, model_metrics=model_metrics, review_filter=review_filter,
                           summary=ComplaintManager.summary())

@app.route("/update/<int:complaint_id>", methods=["POST"])
@admin_required
def update(complaint_id):
    new_status = request.form.get("status", "")
    if new_status not in {"Pending", "In Progress", "Resolved", "Rejected"}:
        flash("Invalid status.", "error")
    else:
        with get_db() as db:
            db.execute("UPDATE complaints SET status=? WHERE id=?", (new_status, complaint_id))
        flash(f"Complaint #{complaint_id} updated to {new_status}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/summary")
@admin_required
def summary():
    report = ComplaintManager.summary()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Summary Type", "Name", "Count"])
    writer.writerow(["Overall", "Total complaints", report["total"]])
    writer.writerow(["Review", "Flagged for manual review", report["manual_review"]])
    for row in report["by_category"]:
        writer.writerow(["Category", row["category"], row["total"]])
    for row in report["by_status"]:
        writer.writerow(["Status", row["status"], row["total"]])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=campus_complaint_summary.csv"})

@app.route("/export")
@admin_required
def export():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Complaint ID", "Student Name", "Student ID", "Title", "Description",
                     "Category", "Suggested Category", "Model Confidence", "Manual Review",
                     "Review Reason", "Department", "Location", "Priority", "Status", "Created At"])
    with get_db() as db:
        rows = db.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()
    for row in rows:
        writer.writerow([row["id"], row["student_name"], row["student_id"], row["title"],
                         row["description"], row["category"], row["suggested_category"],
                         row["model_confidence"], "Yes" if row["manual_review"] else "No",
                         row["review_reason"], row["department"], row["location"],
                         row["priority"], row["status"], row["created_at"]])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=campus_complaint_report.csv"})

init_db()

if __name__ == "__main__":
    app.run(debug=True)
