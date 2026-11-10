CAMPUS COMPLAINT MANAGEMENT SYSTEM - V3
=======================================

RUN IN VS CODE / WINDOWS
1. Extract this ZIP and open its folder in VS Code.
2. Terminal > New Terminal.
3. Install packages:
   python -m pip install -r requirements.txt

4. In PowerShell, configure admin credentials (choose your own values):
   $env:CAMPUS_ADMIN_USERNAME="campusadmin"
   $env:CAMPUS_ADMIN_PASSWORD="REPLACE_WITH_A_LONG_UNIQUE_PASSWORD"
   $env:FLASK_SECRET_KEY="REPLACE_WITH_A_LONG_RANDOM_SECRET"
   python app.py

5. Open http://127.0.0.1:5000

IMPORTANT: Set your own password before running. Admin login is disabled if CAMPUS_ADMIN_PASSWORD is blank.
For the current terminal session, the environment variables must be set before `python app.py`.

PUBLIC USER PAGES
- Home page with category dropdown and complaint form
- Track complaint using complaint ID + student ID

ADMIN ONLY
- /admin/login
- /admin
- /export
All report/export/status-update routes require an admin session.

EMAIL NOTIFICATIONS
This version sends an email to the selected department after saving a complaint.
Configure SMTP and each department mailbox in PowerShell before running app.py.
Example for Gmail SMTP (use a Gmail App Password, not your normal Gmail password):
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USERNAME="your-sender@gmail.com"
$env:SMTP_PASSWORD="your-16-character-google-app-password"
$env:MAIL_FROM="your-sender@gmail.com"
$env:EMAIL_MAINTENANCE="maintenance@your-college.edu"
$env:EMAIL_ELECTRICAL="electrical@your-college.edu"
$env:EMAIL_IT="it@your-college.edu"
$env:EMAIL_SANITATION="sanitation@your-college.edu"
$env:EMAIL_ACADEMIC="academic@your-college.edu"
$env:EMAIL_HOSTEL="hostel@your-college.edu"
$env:EMAIL_GENERAL="admin-office@your-college.edu"
python app.py

Replace all sample email addresses with real authorized department inboxes.
If email configuration is missing, complaint data is still saved but notification will not be sent.
Never share or commit your SMTP app password or Flask secret key.

PUBLIC INTERNET ACCESS
http://127.0.0.1:5000 is only local. To let everyone access the website, deploy it to a hosting provider,
use HTTPS, configure persistent database storage, and set environment variables on the hosting platform.
Do not use Flask debug mode or the built-in development server for public production deployment.

SECURITY NOTE
This is a college-project starter, not a production security audit. Before public deployment add CSRF
protection, rate limiting, secure cookie settings, robust authentication/password hashing, backups,
privacy policy/data retention controls, and a production WSGI server.

MAINTENANCE DASHBOARD (ADDED)
- Configure MAINTENANCE_USERNAME and MAINTENANCE_PASSWORD in environment variables.
- Open /maintenance/login to sign in.
- The dashboard at /maintenance/dashboard lists all complaints, filters by status/category, and lets staff update status.
- Keep credentials private; never upload .env or complaints.db to GitHub.
