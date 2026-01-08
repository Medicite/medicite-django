import random
from django.core.management.base import BaseCommand
from website.models import PatientProfile, Appointment, PatientReport, CustomUser
from django.contrib.auth import get_user_model
from website.signals import retrain_model_on_new_report
from django.db.models.signals import post_save

# Define barangays
BARANGAYS = [
    "Cabaroan", "Cabittaogan", "Cabuloan", 
    "Pangada", "Paratong", "Poblacion",
    "Sinabaan", "Subec", "Tamorong"
]

# Define diagnoses
DIAGNOSES = [
    "Dengue", "Common Cold", "Flu", "Hypertension", "Diabetes",
    "Constipation", "Gastroenteritis", "Urinary Tract Infection",
    "Skin Infection", "Asthma", "Pneumonia", "Chickenpox",
    "Ear Infection", "Fever", "Tuberculosis", "Headache",
    "Sore Throat", "Bronchitis", "Conjunctivitis", "Allergic Reaction"
]

# Assign likely diagnoses per barangay (weighted choices)
BARANGAY_ILLNESS_MAP = {
    "Cabaroan": ["Dengue", "Flu", "Common Cold"],
    "Cabittaogan": ["Dengue", "Flu", "Hypertension"],
    "Cabuloan": ["Common Cold", "Flu", "Constipation"],
    "Pangada": ["Flu", "Gastroenteritis", "Sore Throat"],
    "Paratong": ["Flu", "Gastroenteritis", "Skin Infection"],
    "Poblacion": ["Dengue", "Flu", "Ear Infection"],
    "Sinabaan": ["Hypertension", "Diabetes", "Skin Infection"],
    "Subec": ["Tuberculosis", "Dengue", "Constipation"],
    "Tamorong": ["Chickenpox", "Allergic Reaction", "Bronchitis"]
}

# Define services associated with diagnoses
DIAGNOSIS_SERVICE_MAP = {
    "Dengue": ["Lab Test", "Consultation"],
    "Flu": ["Medication", "Consultation"],
    "Common Cold": ["Consultation", "Medication"],
    "Hypertension": ["Medication", "Follow-up"],
    "Diabetes": ["Medication", "Lab Test"],
    "Constipation": ["Consultation", "Medication"],
    "Gastroenteritis": ["Medication", "Lab Test"],
    "Urinary Tract Infection": ["Medication", "Lab Test"],
    "Skin Infection": ["Medication", "Consultation"],
    "Asthma": ["Medication", "Follow-up"],
    "Pneumonia": ["Medication", "Lab Test"],
    "Chickenpox": ["Consultation", "Medication"],
    "Ear Infection": ["Medication", "Consultation"],
    "Fever": ["Consultation", "Lab Test"],
    "Tuberculosis": ["Medication", "Follow-up"],
    "Headache": ["Consultation", "Medication"],
    "Sore Throat": ["Medication", "Consultation"],
    "Bronchitis": ["Medication", "Lab Test"],
    "Conjunctivitis": ["Medication", "Consultation"],
    "Allergic Reaction": ["Consultation", "Medication"]
}

SERVICES = ["Consultation", "Medication", "Follow-up", "Lab Test"]

User = get_user_model()

class Command(BaseCommand):
    help = 'Generate smarter dummy PatientReport records for testing'

    def handle(self, *args, **kwargs):

        # -----------------------------------------
        # 1️⃣ Disconnect retraining signal
        # -----------------------------------------
        post_save.disconnect(retrain_model_on_new_report, sender=PatientReport)
        self.stdout.write(self.style.WARNING("📌 Retrain signal temporarily DISABLED."))

        # Clear existing reports
        PatientReport.objects.all().delete()
        self.stdout.write(self.style.WARNING("Existing PatientReports cleared."))

        patients = list(PatientProfile.objects.all())
        staff_users = CustomUser.objects.filter(role__in=['nurse', 'doctor', 'info_officer'])

        if not patients:
            self.stdout.write(self.style.ERROR("No patients found. Add patients first."))
            return
        if not staff_users:
            self.stdout.write(self.style.ERROR("No staff users found. Add staff first."))
            return

        reports_created = 0

        for _ in range(300):  # generate more reports for richer data
            patient = random.choice(patients)
            staff = random.choice(staff_users)
            barangay = random.choice(BARANGAYS)

            illness = random.choice(BARANGAY_ILLNESS_MAP.get(barangay, DIAGNOSES))
            service = random.choice(DIAGNOSIS_SERVICE_MAP.get(illness, SERVICES))

            # Random appointment if exists
            appointments = patient.appointment_set.all()
            appointment = random.choice(appointments) if appointments else None

            PatientReport.objects.create(
                patient=patient,
                appointment=appointment,
                staff=staff,
                diagnosis=illness,
                services_provided=service,
                barangay=barangay
            )
            reports_created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {reports_created} smarter dummy PatientReports."))

        # -----------------------------------------
        # 2️⃣ Reconnect retraining signal
        # -----------------------------------------
        post_save.connect(retrain_model_on_new_report, sender=PatientReport)
        self.stdout.write(self.style.SUCCESS("🔄 Retrain signal RE-ENABLED."))