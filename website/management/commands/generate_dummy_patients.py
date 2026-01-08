import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from website.models import PatientProfile

User = get_user_model()

# Sample data for dummy patients
FIRST_NAMES = ["Juan", "Maria", "Jose", "Ana", "Luis", "Carmen", "Pedro", "Lucia"]
LAST_NAMES = ["Santos", "Reyes", "Cruz", "Garcia", "De la Cruz", "Lopez"]
GENDERS = ["male", "female"]
BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
BARANGAYS = [
    "Cabaroan", "Cabittaogan", "Cabuloan", 
    "Pangada", "Paratong", "Poblacion",
    "Sinabaan", "Subec", "Tamorong"
]

class Command(BaseCommand):
    help = "Generate dummy PatientProfiles with CustomUser accounts"

    def handle(self, *args, **kwargs):
        num_patients = 20  # number of dummy patients
        created_count = 0

        for _ in range(num_patients):
            fname = random.choice(FIRST_NAMES)
            lname = random.choice(LAST_NAMES)
            mname = random.choice(FIRST_NAMES) if random.random() > 0.5 else ""
            gender = random.choice(GENDERS)
            blood_type = random.choice(BLOOD_TYPES)

            # Random birthdate between 1-80 years old
            age = random.randint(1, 80)
            birthdate = date.today() - timedelta(days=365*age)

            # Create linked CustomUser
            email = f"{fname.lower()}.{lname.lower()}{random.randint(1,1000)}@example.com"
            number = f"09{random.randint(100000000, 999999999)}"

            user = User.objects.create_user(
                email=email,
                number=number,
                password="Test1234",
                fname=fname,
                mname=mname,
                lname=lname,
                role="patient"
            )

            # Create PatientProfile
            PatientProfile.objects.create(
                user=user,
                fname=fname,
                mname=mname,
                lname=lname,
                gender=gender,
                blood_type=blood_type,
                birthdate=birthdate,
                address=random.choice(BARANGAYS)
            )

            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created_count} dummy patients and linked CustomUsers."))
