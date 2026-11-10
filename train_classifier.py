"""Train and evaluate a complaint classifier using a stratified 75/25 split."""
import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

BASE = Path(__file__).resolve().parent
DATA = BASE / "synthetic_complaints.csv"
MODEL = BASE / "complaint_classifier.joblib"
METRICS = BASE / "model_metrics.json"

if not DATA.exists():
    raise SystemExit("synthetic_complaints.csv is missing. Run: python generate_synthetic_data.py")
df = pd.read_csv(DATA).dropna(subset=["text", "category"])
X_train, X_test, y_train, y_test = train_test_split(
    df["text"], df["category"], test_size=0.25, random_state=42, stratify=df["category"]
)
model = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True, strip_accents="unicode")),
    ("classifier", LogisticRegression(max_iter=1500, class_weight="balanced", random_state=42))
])
model.fit(X_train, y_train)
predictions = model.predict(X_test)
metrics = {
    "dataset_rows": int(len(df)),
    "training_rows": int(len(X_train)),
    "testing_rows": int(len(X_test)),
    "split": "stratified 75% train / 25% test",
    "accuracy": float(accuracy_score(y_test, predictions)),
    "classification_report": classification_report(y_test, predictions, output_dict=True, zero_division=0),
    "classes": sorted(df["category"].unique().tolist()),
    "note": "Metrics are based on synthetic data and do not guarantee real-world accuracy. Review flagged predictions manually."
}
joblib.dump(model, MODEL)
METRICS.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
print(f"Dataset: {len(df)} | train: {len(X_train)} | test: {len(X_test)}")
print(f"Stratified split accuracy: {metrics['accuracy']:.3f}")
print(classification_report(y_test, predictions, zero_division=0))
print(f"Saved model to {MODEL}")
