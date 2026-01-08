from django.db import models
from django.conf import settings
from django.contrib.auth.models import User, AbstractBaseUser, BaseUserManager, PermissionsMixin
from datetime import datetime, timedelta, time
# Create your models here. aka database

#for patient profile storing
class PatientProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('N/A', 'N/A'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uid = models.CharField(max_length=5, unique=True, blank=True, null=True, editable=False)
    fname = models.CharField(max_length=50)
    mname = models.CharField(max_length=50, blank=True, null=True)
    lname = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=False)
    blood_type = models.CharField(max_length=5, choices=BLOOD_TYPE_CHOICES, default='N/A')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    birthdate = models.DateField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.uid:
            # Get last assigned uid
            last = PatientProfile.objects.order_by('-id').first()
            if last and last.uid:
                last_uid_num = int(last.uid)
                self.uid = str(last_uid_num + 1)
            else:
                self.uid = "25001"  # Start from 25001
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.fname} {self.lname} ({self.user.fname} {self.user.lname})"
    
# for registration/login purposes
#
class CustomUserManager(BaseUserManager):
    def create_user(self, email, number, password=None, **extra_fields):
        if not email and not number:
            raise ValueError("The Email or Phone Number must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, number=number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, number, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    fname = models.CharField(max_length=100)
    mname = models.CharField(max_length=100, blank=True, null=True)
    lname = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    number = models.CharField(max_length=15, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['number', 'fname', 'lname']

    ROLE_CHOICES = (
        ('patient', 'Patient'),
        ('nurse', 'Nurse'),
        ('doctor', 'Doctor'),
        ('info_officer', 'Information Officer'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')

    def __str__(self):
        return f"{self.fname} {self.lname}"
    

class Appointment(models.Model):
    APPOINTMENT_TYPES = [
        ('consultation', 'General Consultation'),
        ('follow-up', 'Follow-up Visit'),
        ('vaccination', 'Vaccination'),
        ('checkup', 'Routine Checkup'),
    ]

    patient_profile = models.ForeignKey('PatientProfile', on_delete=models.CASCADE)
    appointment_type = models.CharField(max_length=50, choices=APPOINTMENT_TYPES)
    preferred_date = models.DateField()
    preferred_time = models.TimeField()
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

        # Which forms were selected
    consent_form = models.BooleanField(default=False)
    lab_request_form = models.BooleanField(default=False)
    philhealth_form = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.patient_profile.fname} - {self.get_appointment_type_display()} on {self.preferred_date} {self.preferred_time.strftime('%I:%M %p')}"

class PatientReport(models.Model):
    # Link to patient
    patient = models.ForeignKey('PatientProfile', on_delete=models.CASCADE)
    # Link to appointment (optional)
    appointment = models.ForeignKey('Appointment', on_delete=models.SET_NULL, null=True, blank=True)
    # Staff who created the report
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, limit_choices_to={'role': 'staff'},
                              on_delete=models.SET_NULL, null=True, blank=True)
    
    # Report data
    diagnosis = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True)
    services_provided = models.CharField(max_length=200, blank=True, null=True)
    barangay = models.CharField(max_length=50, blank=True, null=True)  # patient barangay
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.id} - {self.patient.fname} {self.patient.lname}"