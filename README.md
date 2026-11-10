# G08 Campus Complaint Routing System

This update preserves the existing Flask complaint form, user-selected category workflow, admin-only reports, complaint tracking, status updates, email notifications, and CSV export. It adds the G08 classification features.

## G08 features added

- `Complaint`, `RoutingRule`, and `ComplaintManager` classes in `app.py`.
- 400 labelled synthetic complaint examples across four ML categories: IT, Electrical, Maintenance, and Sanitation.
- A reproducible stratified 75%/25% split: 300 training rows and 100 test rows.
- TF-IDF + Logistic Regression classifier (`complaint_classifier.joblib`).
- Classifier suggestion and confidence displayed after submission and in the admin report.
- Manual-review flag when confidence is below the configured threshold, the model disagrees with the student's selected category, the selected category is outside the four model categories, or the model file is unavailable.
- Admin filter for manual-review cases and a summary CSV export (`/admin/summary`).
- Existing database files are migrated by adding columns; the application does not drop existing complaint records.

**Important:** The user-selected category is retained. The model gives a suggestion rather than silently overriding the student's choice. A disagreement is flagged for an administrator to review. Synthetic-data test accuracy is not a guarantee of real-world performance.

## Run locally (Windows / VS Code PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python generate_synthetic_data.py
python train_classifier.py
$env:CAMPUS_ADMIN_USERNAME="campusadmin"
$env:CAMPUS_ADMIN_PASSWORD="choose-a-strong-password"
$env:FLASK_SECRET_KEY="replace-with-a-long-random-secret"
python app.py
```

Open `http://127.0.0.1:5000`. Admin login: `http://127.0.0.1:5000/admin/login`.

The classifier and metrics are already included in this project. The two generation/training commands can be rerun to reproduce the dataset and model.

## Dataset and evaluation

`synthetic_complaints.csv` contains 400 labelled records, balanced as 100 records per category. `train_classifier.py` uses `train_test_split(test_size=0.25, stratify=labels, random_state=42)` and writes `model_metrics.json` with the evaluation results.

## Deployment notes

- Add `CAMPUS_ADMIN_USERNAME`, `CAMPUS_ADMIN_PASSWORD`, and `FLASK_SECRET_KEY` as host environment variables. Never commit `.env`.
- Configure SMTP and the department email environment variables to enable email delivery.
- Use persistent database storage or a managed database for production; the local SQLite file can be lost on hosts with ephemeral filesystems.
- Use HTTPS, CSRF protection, secure cookies, rate limiting, and a production WSGI server before handling real student data.
- Do not upload `.env`, `complaints.db`, real student information, or credentials to GitHub.

## Main files

- `app.py` — Flask app, routing rules, complaint manager, admin and exports
- `templates/` — existing website pages updated to show classifier/manual-review information
- `static/style.css` — existing styling plus small review/status additions
- `generate_synthetic_data.py` — generates the 400 labelled synthetic examples
- `synthetic_complaints.csv` — generated labelled data
- `train_classifier.py` — stratified training/evaluation script
- `complaint_classifier.joblib` — trained model
- `model_metrics.json` — evaluation metrics

## Maintenance dashboard (new)

The maintenance dashboard lets authorized maintenance staff view all submitted complaints, filter by status/category, and update complaint status (Pending, In Progress, Resolved, Rejected). It has a separate login and session from the administrator dashboard.

Configure these environment variables before starting the application or in your hosting provider's Environment settings:

- `MAINTENANCE_USERNAME` — maintenance login username (defaults to `maintenance`)
- `MAINTENANCE_PASSWORD` — required password for maintenance login; choose a strong unique password

Local PowerShell example:

```powershell
$env:MAINTENANCE_USERNAME="maintenance"
$env:MAINTENANCE_PASSWORD="ChooseYourOwnStrongPassword!"
python app.py
```

Open `/maintenance/login` to sign in. After authentication, the dashboard is at `/maintenance/dashboard`. Do not put passwords in source code or commit `.env` files to GitHub.
