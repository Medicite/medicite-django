# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import PatientProfile, CustomUser, Appointment, Event
from .ml_utils import AGE_COLUMNS, SYMPTOM_COLUMNS, SEX_COLUMN
from .utils import generate_timeslots
from datetime import datetime, time, timedelta, date

# -----------------------------
# PATIENT PROFILE FORM
# -----------------------------
class PatientProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove blank option from dropdowns
        if 'gender' in self.fields:
            self.fields['gender'].empty_label = None

    class Meta:
        model = PatientProfile
        fields = [
            'fname', 'mname', 'lname',
            'gender', 'blood_type', 'phone_number',
            'email', 'address', 'birthdate'
        ]
        widgets = {
            'gender': forms.Select(),
            'blood_type': forms.Select(),
            'address': forms.Textarea(attrs={'rows': 2}),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '9123456789',
                'pattern': '[0-9]{10}',
                'title': 'Enter 10-digit phone number without +63',
            })
        }


# -----------------------------
# USER REGISTRATION FORM
# -----------------------------
class RegisterForm(UserCreationForm):
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password'}))

    class Meta:
        model = CustomUser
        fields = ['fname', 'mname', 'lname', 'email', 'number', 'password1', 'password2']


# -----------------------------
# APPOINTMENT FORM
# -----------------------------
class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["patient_profile", "appointment_type", "preferred_date"]
        widgets = {
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter patient profiles by logged-in user
        if user:
            self.fields['patient_profile'].queryset = PatientProfile.objects.filter(user=user)
            self.fields['patient_profile'].empty_label = None

        # Remove blank option for appointment_type
        if hasattr(self.fields['appointment_type'], 'empty_label'):
            self.fields['appointment_type'].empty_label = None
        else:
            choices = [(k, v) for k, v in self.fields['appointment_type'].choices if k != '']
            self.fields['appointment_type'].choices = choices

        # Default preferred_date
        self.fields['preferred_date'].initial = date.today()

    def clean(self):
        cleaned_data = super().clean()
        date_selected = cleaned_data.get('preferred_date')
        
        if date_selected:
            # Check if the selected date has any available slots
            from .utils import generate_timeslots
            slots = generate_timeslots(start_hour=8, end_hour=17, interval=30)  # 30-minute intervals
            used_slots = Appointment.objects.filter(preferred_date=date_selected).values_list('preferred_time', flat=True)
            available_slots = [s for s in slots if s not in used_slots]
            
            if not available_slots:
                raise forms.ValidationError("No available time slots for the selected date. Please choose another date.")
        
        return cleaned_data


# -----------------------------
# SYMPTOM FORM FOR ML PREDICTION
# -----------------------------
class SymptomForm(forms.Form):
    SEX_CHOICES = [(0, "Female"), (1, "Male")]
    AGE_CHOICES = [
        (col, col.replace('age_', '').capitalize())
        for col in AGE_COLUMNS if col != "age_all"
    ]

    sex = forms.ChoiceField(choices=SEX_CHOICES, widget=forms.RadioSelect, label="Sex")
    age_group = forms.ChoiceField(choices=AGE_CHOICES, widget=forms.Select, label="Age Group")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically create a field for each symptom
        for symptom in SYMPTOM_COLUMNS:
            self.fields[symptom] = forms.ChoiceField(
                choices=[("yes", "Yes"), ("no", "No")],
                widget=forms.RadioSelect,
                label=symptom.replace("_", " ").capitalize(),
                initial="no"
            )

# -----------------------------
# PATIENT REPORT FORM
# -----------------------------
from .models import PatientReport

class PatientReportForm(forms.ModelForm):
    class Meta:
        model = PatientReport
        fields = ['patient', 'appointment', 'staff', 'diagnosis', 'services_provided', 'barangay']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional: limit staff to doctors/nurses if needed
        self.fields['staff'].queryset = self.fields['staff'].queryset.filter(role__in=['doctor', 'nurse'])
        # Optional: remove empty labels for dropdowns
        for field_name, field in self.fields.items():
            if hasattr(field, 'empty_label'):
                field.empty_label = None


# -----------------------------
# EVENT FORM
# -----------------------------
class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'event_date', 'location', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Event Description'}),
            'event_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Location'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }