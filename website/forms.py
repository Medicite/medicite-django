# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import PatientProfile, CustomUser, Appointment
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
    preferred_time = forms.ChoiceField(label="Preferred Time")  # placeholder

    class Meta:
        model = Appointment
        fields = ["patient_profile", "appointment_type", "preferred_date", "preferred_time"]
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

        # Set available times for the default date
        self.update_time_choices(self.fields['preferred_date'].initial)

    def update_time_choices(self, selected_date):
        """Filter available time slots for the selected date."""
        slots = generate_timeslots()
        used_slots = Appointment.objects.filter(preferred_date=selected_date).values_list('preferred_time', flat=True)
        available_slots = [s.strftime("%H:%M") for s in slots if s not in used_slots]

        self.fields['preferred_time'].choices = [(s, s) for s in available_slots]

    def clean_preferred_time(self):
        time_str = self.cleaned_data['preferred_time']
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise forms.ValidationError("Invalid time format. Use HH:MM.")

    def clean(self):
        cleaned_data = super().clean()
        date_selected = cleaned_data.get('preferred_date')
        time_selected = cleaned_data.get('preferred_time')

        if date_selected and time_selected:
            # Check for double-booking
            if Appointment.objects.filter(preferred_date=date_selected, preferred_time=time_selected).exists():
                raise forms.ValidationError("This time slot is already booked. Please select another time.")
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