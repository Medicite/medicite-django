# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import RegisterForm, PatientProfileForm, AppointmentForm, SymptomForm
from .models import CustomUser, PatientProfile, Appointment
from django.contrib.auth.decorators import login_required
from django.utils.timezone import localdate
from django.http import HttpResponse, HttpResponseForbidden
from io import BytesIO
from reportlab.pdfgen import canvas
import pickle, joblib, numpy as np
from .ml_utils import MODEL_PATH, ENCODER_PATH, FEATURE_ORDER_PATH, AGE_COLUMNS
from xgboost import XGBClassifier
from .utils import get_next_available_slot
from datetime import date
from functools import wraps
from website.models import PatientReport
from website.forms import PatientReportForm
from django.db.models import Q

ANALYSIS_FILE = "website/static/analysis_data.pkl"

def role_required(required_role):
    """
    Decorator to restrict access to users with a specific role.
    Usage: @role_required('nurse')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.role != required_role:
                return HttpResponseForbidden("You don't have access")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# -----------------------------
# HOME / DASHBOARD
# -----------------------------
@login_required
def home(request):
    profiles = PatientProfile.objects.filter(user=request.user)
    form = AppointmentForm(user=request.user)

    if request.method == "POST":
        form = AppointmentForm(request.POST, user=request.user)
        if form.is_valid():
            appointment = form.save()

            # Generate PDF separately
            from .pdf_generator import generate_appointment_forms
            pdf_file_path = generate_appointment_forms(appointment)

            # Optional: show a success message and provide download link
            messages.success(request, f"Appointment booked successfully! Download your confirmation PDF: {pdf_file_path}")

            return redirect('home')  # Redirect to avoid POST resubmission

    appointments = Appointment.objects.filter(
        patient_profile__user=request.user, preferred_date__gte=date.today()
    ).order_by("preferred_date", "preferred_time")

    return render(request, 'home.html', {
        'profiles': profiles,
        'form': form,
        'appointments': appointments,
        'today': date.today(),
    })


# -----------------------------
# USER REGISTRATION & AUTH
# -----------------------------
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password1'])
            user.save()
            messages.success(request, "Account created successfully! You can now log in.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, 'regis.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        password = request.POST.get('password')

        # Authenticate by email
        user = authenticate(request, email=identifier, password=password)

        # If not found, authenticate by number
        if not user:
            try:
                user_obj = CustomUser.objects.get(number=identifier)
                user = authenticate(request, email=user_obj.email, password=password)
            except CustomUser.DoesNotExist:
                user = None

        if user:
            login(request, user)
            if user.role == 'patient':
                return redirect('medipal')  # patient dashboard
            else:
                return redirect('staff_dashboard')  # all staff roles go here

        else:
            messages.error(request, "Invalid email/number or password")

    return render(request, 'login.html')



@login_required
def logout_view(request):
    logout(request)  # clears the session
    messages.info(request, "You have been logged out.")
    return redirect('login')  # redirect to login page


# -----------------------------
# PATIENT PROFILE MANAGEMENT
# -----------------------------

@login_required
def patient_profile_list(request):
    profiles = PatientProfile.objects.filter(user=request.user)
    return render(request, 'home.html', {'profiles': profiles})

# -----------------------------
# EDIT PATIENT PROFILE
# -----------------------------
@login_required
def edit_patient_profile(request):
    # Get or create the profile for the logged-in user
    profile, created = PatientProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'fname': request.user.fname if hasattr(request.user, 'fname') else '',
            'lname': request.user.lname if hasattr(request.user, 'lname') else '',
            'gender': 'male',  # default value
            # You can add other required fields here with defaults
        }
    )

    if request.method == 'POST':
        form = PatientProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('medipal')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PatientProfileForm(instance=profile)

    return render(request, 'edit_patient_profile.html', {'form': form})


# -----------------------------
# APPOINTMENTS
# -----------------------------
@login_required
def appointment_view(request):
    if request.method == "POST":
        form = AppointmentForm(request.POST, user=request.user)
        if form.is_valid():
            appointment = form.save()
            # Generate PDF using pdf_generator utility
            from .pdf_generator import generate_appointment_forms
            pdf_file = generate_appointment_forms(appointment)
            messages.success(request, "Appointment successfully created!")
            return redirect("home")
    else:
        form = AppointmentForm(user=request.user)

    appointments = Appointment.objects.filter(
        patient_profile__user=request.user, preferred_date__gte=localdate()
    ).order_by("preferred_date", "preferred_time")

    return render(request, "website/appointment.html", {"form": form, "appointments": appointments})


# -----------------------------
# SYMPTOM CHECKER / ML PREDICTION
# -----------------------------
@login_required
def checker(request):
    prediction_result = None
    top_diseases = []

    if request.method == "POST":
        form = SymptomForm(request.POST)
        if form.is_valid():
            # Load feature order
            with open(FEATURE_ORDER_PATH, "rb") as f:
                feature_order = pickle.load(f)

            # Load XGBoost model
            model = XGBClassifier()
            model.load_model(MODEL_PATH)

            # Load encoder
            encoder = joblib.load(ENCODER_PATH)

            # Build feature vector
            sex = int(form.cleaned_data["sex"])
            age_group = form.cleaned_data["age_group"]
            input_vector = []
            for feature in feature_order:
                if feature == "sex":
                    input_vector.append(sex)
                elif feature in AGE_COLUMNS:
                    input_vector.append(1 if feature == age_group else 0)
                else:
                    input_vector.append(1 if form.cleaned_data.get(feature) == "yes" else 0)

            # Predict probabilities
            probs = model.predict_proba([input_vector])[0]
            top_indices = np.argsort(probs)[::-1][:3]
            top_diseases = [
                (encoder.inverse_transform([i])[0], round(probs[i] * 100, 2))
                for i in top_indices
            ]

            top_disease = top_diseases[0][0]
            confidence = top_diseases[0][1]
            prediction_result = {
                "disease": top_disease,
                "confidence": confidence,
                "alert_type": "success" if confidence > 70 else "warning",
                "message": f"You most likely have {top_disease} ({confidence}%). "
                           "Please consult your doctor for an accurate diagnosis and appropriate medical advice."
            }
    else:
        form = SymptomForm()

    return render(request, "checker.html", {
        "form": form,
        "prediction_result": prediction_result,
        "top_diseases": top_diseases,
    })

@login_required
def add_patient_report(request):
    if request.user.role != 'doctor':
        return render(request, "403.html")  # or redirect with error message

    if request.method == "POST":
        form = PatientReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.staff = request.user  # assign the doctor
            report.save()  # triggers signal to retrain
            return redirect("staff_dashboard")
    else:
        form = PatientReportForm()

    return render(request, "add_report.html", {"form": form})

from django.http import JsonResponse

@login_required
def staff_dashboard(request):
    if request.user.role == 'patient':
        return redirect('home')

    search_query = request.GET.get('search', '').strip()
    patient_reports = PatientReport.objects.none()  # default empty

    # Allow DOCTORS and STAFF to create reports
    if request.user.role in ['doctor', 'staff']:

        # Handle report creation
        if request.method == 'POST' and request.POST.get('create_report') == '1':
            patient_id = request.POST.get('patient')
            diagnosis = request.POST.get('diagnosis')
            barangay = request.POST.get('barangay')
            services = request.POST.get('services_provided', '')

            if patient_id and diagnosis and barangay:
                try:
                    patient = PatientProfile.objects.get(id=patient_id)
                    PatientReport.objects.create(
                        patient=patient,
                        staff=request.user,
                        diagnosis=diagnosis,
                        barangay=barangay,
                        services_provided=services
                    )
                except PatientProfile.DoesNotExist:
                    pass

            return redirect('staff_dashboard')

        # Handle search
        if search_query:
            names = search_query.split()

            if len(names) == 1:
                patient_reports = PatientReport.objects.filter(
                    Q(patient__fname__icontains=names[0]) |
                    Q(patient__lname__icontains=names[0])
                ).order_by('-date_created')
            else:
                first_name = names[0]
                last_name = ' '.join(names[1:])
                patient_reports = PatientReport.objects.filter(
                    Q(patient__fname__icontains=first_name, patient__lname__icontains=last_name)
                ).order_by('-date_created')

            # AJAX response
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                data = [
                    {
                        "uid": r.patient.uid,
                        "name": f"{r.patient.fname} {r.patient.lname}",
                        "barangay": r.barangay,
                        "diagnosis": r.diagnosis,
                        "staff": f"{r.staff.fname} {r.staff.lname}" if r.staff else "N/A",
                        "date": r.date_created.strftime("%b %d, %Y %H:%M"),
                    } for r in patient_reports
                ]
                return JsonResponse({"reports": data})

    # Load other data (visible to all staff)
    patient_profiles = PatientProfile.objects.all()
    appointments = Appointment.objects.all()

    try:
        analysis = joblib.load(ANALYSIS_FILE)
    except:
        analysis = {}

    return render(request, 'staff_dashboard.html', {
        'user_role': request.user.role,
        'patient_reports': patient_reports,
        'patient_profiles': patient_profiles,
        'appointments': appointments,
        'analysis': analysis,
        'search_query': search_query,
    })
