from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from website.models import PatientProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Create test patient users with UID'

    def add_arguments(self, parser):
        parser.add_argument(
            'count',
            type=int,
            help='Number of test patients to create'
        )

    def handle(self, *args, **options):
        count = options['count']
        starting_number = 25001

        # Find the last UID in the database
        last_profile = PatientProfile.objects.order_by('-uid').first()
        if last_profile and last_profile.uid:
            starting_number = int(last_profile.uid)

        for i in range(1, count + 1):
            number = starting_number + i
            email = f"test{number}@example.com"
            fname = f"Test{number}"
            lname = "Patient"

            # Create user
            user = User.objects.create_user(
                email=email,
                password="TestPassword123",
                fname=fname,
                lname=lname,
                role='patient'
            )

            # Create patient profile
            profile = PatientProfile.objects.create(
                user=user,
                fname=fname,
                lname=lname,
                gender='male',
                blood_type='N/A',
            )

            self.stdout.write(self.style.SUCCESS(f"Created {fname} {lname} with UID {profile.uid}"))
