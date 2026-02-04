import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from website.models import PatientReport
import joblib

ANALYSIS_FILE = "website/static/analysis_data.pkl"
MODEL_FILE = "website/static/ml_model.pkl"

def train_predictive_model():
    reports = PatientReport.objects.all()
    if not reports.exists():
        print("No reports to train on.")
        return None

    data = pd.DataFrame(list(reports.values('diagnosis', 'services_provided', 'barangay')))

    # Features and target
    X = pd.get_dummies(data[['services_provided', 'barangay']])
    y = data['diagnosis']

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train Random Forest
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    print("Model Accuracy:", accuracy_score(y_test, y_pred))
    print("Classification Report:\n", classification_report(y_test, y_pred, zero_division=0))

    # Save model
    joblib.dump(model, MODEL_FILE)
    print("Model saved.")

    return model

def generate_analysis_data():
    """Regenerate predictive analysis and barangay stats from all PatientReports."""
    reports = PatientReport.objects.all()
    if not reports.exists():
        try:
            joblib.dump({}, ANALYSIS_FILE)
        except Exception:
            pass
        return {}

    rows = list(reports.values('diagnosis', 'services_provided', 'barangay'))
    df = pd.DataFrame(rows)
    # Drop rows with missing diagnosis or barangay so stats reflect only complete data
    df = df.dropna(subset=['diagnosis', 'barangay'])
    df['services_provided'] = df['services_provided'].fillna('')
    df['barangay'] = df['barangay'].astype(str)

    if df.empty:
        try:
            joblib.dump({}, ANALYSIS_FILE)
        except Exception:
            pass
        return {}

    # Overall top 5 illnesses (diagnosis)
    top_illnesses = df['diagnosis'].value_counts().head(5).to_dict()

    # Overall top 5 services
    top_services = df['services_provided'].value_counts().head(5).to_dict()

    # Barangay-level stats
    barangay_analysis = {}
    for barangay, group in df.groupby('barangay'):
        if not barangay or str(barangay) == 'nan':
            continue
        illness_counts = group['diagnosis'].value_counts().head(5).to_dict()
        service_counts = group['services_provided'].value_counts().head(5).to_dict()
        barangay_analysis[str(barangay)] = {
            'top_illnesses': illness_counts,
            'top_services': service_counts,
        }

    analysis = {
        'overall_top_illnesses': top_illnesses,
        'overall_services': top_services,
        'barangay_analysis': barangay_analysis
    }

    try:
        joblib.dump(analysis, ANALYSIS_FILE)
    except Exception:
        pass
    return analysis
