import pandas as pd
from django.core.management.base import BaseCommand
from website.models import PatientProfile, PatientReport
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

# Define all barangays of Sta. Catalina, Ilocos Sur
BARANGAYS = [
    "Cabaroan", "Cabittaogan", "Cabuloan",
    "Pangada", "Paratong", "Poblacion",
    "Sinabaan", "Subec", "Tamorong"
]

class Command(BaseCommand):
    help = 'Predict likely illnesses for each barangay using patient reports'

    def handle(self, *args, **kwargs):
        self.stdout.write("Collecting patient report data...")

        data = []
        patients = PatientProfile.objects.all()

        for p in patients:
            reports = PatientReport.objects.filter(patient=p)
            for r in reports:
                data.append({
                    'uid': p.uid,
                    'barangay': r.barangay if r.barangay else (p.address.split(",")[0] if p.address else "Unknown"),
                    'age': (2025 - p.birthdate.year) if p.birthdate else None,
                    'gender': p.gender,
                    'illness': r.diagnosis if r.diagnosis else "Unknown",
                    'service': r.services_provided if r.services_provided else "Unknown",
                })

        if not data:
            self.stdout.write(self.style.WARNING("No patient report data found. Exiting."))
            return

        df = pd.DataFrame(data)
        df.dropna(subset=['age', 'illness'], inplace=True)

        # Encode categorical variables
        df['gender'] = df['gender'].astype('category')
        df['barangay'] = df['barangay'].astype('category')
        df['service'] = df['service'].astype('category')
        df['illness'] = df['illness'].astype('category')

        le_gender = LabelEncoder()
        df['gender_encoded'] = le_gender.fit_transform(df['gender'])
        le_barangay = LabelEncoder()
        df['barangay_encoded'] = le_barangay.fit_transform(df['barangay'])

        X = df[['age', 'gender_encoded', 'barangay_encoded']]
        y = df['illness']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf.fit(X_train, y_train)

        y_pred = rf.predict(X_test)

        self.stdout.write(f"Model Accuracy: {accuracy_score(y_test, y_pred):.2f}")
        self.stdout.write("Classification Report:")
        self.stdout.write(classification_report(y_test, y_pred))

        # Predict illness likelihood per barangay and top illnesses/services
        self.stdout.write("Barangay-wise predictions and top analyses:")
        for b in BARANGAYS:
            try:
                barangay_encoded = le_barangay.transform([b])[0]
            except ValueError:
                barangay_encoded = -1  # unknown barangay

            pred = rf.predict([[30, 0, barangay_encoded]])  # default age 30, gender encoded as 0
            self.stdout.write(f"\n{b}: Predicted illness -> {pred[0]}")

            # Top 5 illnesses in this barangay
            top_illnesses_b = df[df['barangay'] == b]['illness'].value_counts().head(5)
            self.stdout.write(f"Top 5 illnesses in {b}:\n{top_illnesses_b.to_string()}")

            # Top 5 services in this barangay
            top_services_b = df[df['barangay'] == b]['service'].value_counts().head(5)
            self.stdout.write(f"Top 5 services in {b}:\n{top_services_b.to_string()}")

        # Overall top 5 illnesses
        overall_top_illnesses = df['illness'].value_counts().head(5)
        self.stdout.write("\nOverall Top 5 Illnesses:")
        self.stdout.write(overall_top_illnesses.to_string())

        # Overall service counts
        service_counts = df['service'].value_counts()
        self.stdout.write("\nOverall Service Counts:")
        self.stdout.write(service_counts.to_string())

        self.stdout.write("\nPrediction complete!")
