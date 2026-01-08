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
    reports = PatientReport.objects.all()
    if not reports.exists():
        return {}

    df = pd.DataFrame(list(reports.values('diagnosis', 'services_provided', 'barangay')))
    
    # Overall top 5 illnesses
    top_illnesses = df['diagnosis'].value_counts().head(5).to_dict()
    
    # Overall top 5 services
    top_services = df['services_provided'].value_counts().head(5).to_dict()

    # Barangay-level predictions
    barangay_analysis = {}
    for barangay, group in df.groupby('barangay'):
        illness_counts = group['diagnosis'].value_counts().head(5).to_dict()
        service_counts = group['services_provided'].value_counts().head(5).to_dict()
        barangay_analysis[barangay] = {
            'top_illnesses': illness_counts,
            'top_services': service_counts,
        }

    analysis = {
        'overall_top_illnesses': top_illnesses,
        'overall_services': top_services,
        'barangay_analysis': barangay_analysis
    }

    # Save to static file (for reading in views)
    joblib.dump(analysis, ANALYSIS_FILE)
    return analysis
