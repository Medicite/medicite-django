# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import RegisterForm, PatientProfileForm, AppointmentForm, SymptomForm
from .models import CustomUser, PatientProfile, Appointment
from django.contrib.auth.decorators import login_required
from django.utils.timezone import localdate
from django.views.decorators.cache import never_cache
from django.http import HttpResponse, HttpResponseForbidden
from io import BytesIO
from reportlab.pdfgen import canvas
import pickle, joblib, numpy as np
from .ml_utils import MODEL_PATH, ENCODER_PATH, FEATURE_ORDER_PATH, AGE_COLUMNS
from xgboost import XGBClassifier
from .utils import get_next_available_slot
from datetime import date
from functools import wraps
from website.models import PatientReport, Event, ReportMedication
from website.forms import PatientReportForm, EventForm
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
@never_cache
@login_required
def home(request):
    profiles = PatientProfile.objects.filter(user=request.user)
    form = AppointmentForm(user=request.user)

    if request.method == "POST":
        form = AppointmentForm(request.POST, user=request.user)
        if form.is_valid():
            appointment = form.save(commit=False)
            
            # Automatically assign the next available time slot for the selected date
            from .utils import generate_timeslots
            slots = generate_timeslots(start_hour=8, end_hour=17, interval=30)  # 30-minute intervals
            used_slots = Appointment.objects.filter(preferred_date=appointment.preferred_date).values_list('preferred_time', flat=True)
            available_slots = [s for s in slots if s not in used_slots]
            
            if available_slots:
                appointment.preferred_time = available_slots[0]
                appointment.save()
            else:
                messages.error(request, "No available time slots for the selected date. Please choose another date.")
                return render(request, 'home.html', {
                    'profiles': profiles,
                    'form': form,
                    'appointments': appointments,
                    'today': date.today(),
                })

            # Generate PDF separately
            from .pdf_generator import generate_appointment_forms
            pdf_file_path = generate_appointment_forms(appointment)

            # Optional: show a success message and provide download link
            messages.success(request, f"Appointment booked successfully for {appointment.preferred_time.strftime('%I:%M %p')}! Download your confirmation PDF: {pdf_file_path}")

            return redirect('medipal')  # Redirect to avoid POST resubmission

    # Upcoming appointments for the appointment tab
    appointments = Appointment.objects.filter(
        patient_profile__user=request.user, preferred_date__gte=date.today()
    ).order_by("preferred_date", "preferred_time")

    # All appointments (including past) for medical records, prefetch related reports
    from django.db.models import Prefetch
    all_appointments = Appointment.objects.filter(
        patient_profile__user=request.user
    ).prefetch_related(
        Prefetch('patientreport_set', queryset=PatientReport.objects.select_related('staff'))
    ).order_by("-preferred_date", "-preferred_time")

    # Load active upcoming events for patient panel
    from datetime import datetime
    upcoming_events = Event.objects.filter(
        is_active=True,
        event_date__gte=date.today()
    ).order_by('event_date')[:5]  # Show up to 5 upcoming events

    # Medications from doctor reports for this patient (for Medical Records tab)
    patient_medications = ReportMedication.objects.filter(
        report__patient__user=request.user
    ).select_related('report').order_by('-report__date_created')

    return render(request, 'home.html', {
        'profiles': profiles,
        'form': form,
        'appointments': appointments,
        'all_appointments': all_appointments,
        'today': date.today(),
        'events': upcoming_events,
        'patient_medications': patient_medications,
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


@never_cache
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
@never_cache
@login_required
def appointment_view(request):
    if request.method == "POST":
        form = AppointmentForm(request.POST, user=request.user)
        if form.is_valid():
            appointment = form.save(commit=False)
            
            # Automatically assign the next available time slot for the selected date
            from .utils import generate_timeslots
            slots = generate_timeslots(start_hour=8, end_hour=17, interval=30)  # 30-minute intervals
            used_slots = Appointment.objects.filter(preferred_date=appointment.preferred_date).values_list('preferred_time', flat=True)
            available_slots = [s for s in slots if s not in used_slots]
            
            if available_slots:
                appointment.preferred_time = available_slots[0]
                appointment.save()
            else:
                messages.error(request, "No available time slots for the selected date. Please choose another date.")
                form = AppointmentForm(user=request.user)
                appointments = Appointment.objects.filter(
                    patient_profile__user=request.user, preferred_date__gte=localdate()
                ).order_by("preferred_date", "preferred_time")
                return render(request, "website/appointment.html", {"form": form, "appointments": appointments})
            
            # Generate PDF using pdf_generator utility
            from .pdf_generator import generate_appointment_forms
            pdf_file = generate_appointment_forms(appointment)
            messages.success(request, f"Appointment successfully created for {appointment.preferred_time.strftime('%I:%M %p')}!")
            return redirect("medipal")
    else:
        form = AppointmentForm(user=request.user)

    appointments = Appointment.objects.filter(
        patient_profile__user=request.user, preferred_date__gte=localdate()
    ).order_by("preferred_date", "preferred_time")

    return render(request, "website/appointment.html", {"form": form, "appointments": appointments})


# -----------------------------
# SYMPTOM CHECKER / ML PREDICTION
# -----------------------------
@never_cache
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

@never_cache
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

@never_cache
@login_required
def staff_dashboard(request):
    if request.user.role == 'patient':
        return redirect('medipal')

    search_query = request.GET.get('search', '').strip()
    patient_reports = PatientReport.objects.none()  # default empty

    # Handle appointment creation by nurses
    if request.method == 'POST' and request.POST.get('create_appointment') == '1' and request.user.role == 'nurse':
        patient_id = request.POST.get('patient')
        appointment_type = request.POST.get('appointment_type')
        preferred_date = request.POST.get('preferred_date')
        reason = request.POST.get('reason', '')
        
        if patient_id and appointment_type and preferred_date:
            try:
                patient = PatientProfile.objects.get(id=patient_id)
                # Automatically assign the next available time slot
                from .utils import generate_timeslots
                slots = generate_timeslots(start_hour=8, end_hour=17, interval=30)
                used_slots = Appointment.objects.filter(preferred_date=preferred_date).values_list('preferred_time', flat=True)
                available_slots = [s for s in slots if s not in used_slots]
                
                if available_slots:
                    appointment = Appointment.objects.create(
                        patient_profile=patient,
                        appointment_type=appointment_type,
                        preferred_date=preferred_date,
                        preferred_time=available_slots[0],
                        reason=reason,
                        status='pending'
                    )
                    messages.success(request, f"Appointment scheduled successfully for {patient.fname} {patient.lname} at {available_slots[0].strftime('%I:%M %p')}.")
                else:
                    messages.error(request, "No available time slots for the selected date.")
            except PatientProfile.DoesNotExist:
                messages.error(request, "Patient not found.")
        
        return redirect('staff_dashboard')

    # Handle event creation by info officers
    if request.method == 'POST' and request.POST.get('create_event') == '1' and request.user.role == 'info_officer':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            messages.success(request, f"Event '{event.title}' created successfully.")
        else:
            messages.error(request, "Please correct the errors below.")
        return redirect('staff_dashboard')

    # Handle event deletion by info officers
    if request.method == 'POST' and request.POST.get('delete_event') and request.user.role == 'info_officer':
        event_id = request.POST.get('delete_event')
        try:
            event = Event.objects.get(id=event_id)
            event.delete()
            messages.success(request, f"Event '{event.title}' deleted successfully.")
        except Event.DoesNotExist:
            messages.error(request, "Event not found.")
        return redirect('staff_dashboard')

    # Handle event toggle (activate/deactivate) by info officers
    if request.method == 'POST' and request.POST.get('toggle_event') and request.user.role == 'info_officer':
        event_id = request.POST.get('toggle_event')
        try:
            event = Event.objects.get(id=event_id)
            event.is_active = not event.is_active
            event.save()
            status = "activated" if event.is_active else "deactivated"
            messages.success(request, f"Event '{event.title}' {status} successfully.")
        except Event.DoesNotExist:
            messages.error(request, "Event not found.")
        return redirect('staff_dashboard')

    # Handle event update by info officers
    if request.method == 'POST' and request.POST.get('edit_event') and request.user.role == 'info_officer':
        event_id = request.POST.get('edit_event')
        try:
            event = Event.objects.get(id=event_id)
            form = EventForm(request.POST, instance=event)
            if form.is_valid():
                event = form.save(commit=False)
                event.created_by = request.user
                event.save()
                messages.success(request, f"Event '{event.title}' updated successfully.")
            else:
                messages.error(request, "Please correct the errors below.")
        except Event.DoesNotExist:
            messages.error(request, "Event not found.")
        return redirect('staff_dashboard')

    # Handle appointment status update by nurses/doctors
    if request.method == 'POST' and request.POST.get('update_status') == '1' and request.user.role in ['nurse', 'doctor']:
        appointment_id = request.POST.get('appointment_id')
        new_status = request.POST.get('new_status')
        
        if appointment_id and new_status:
            try:
                appointment = Appointment.objects.get(id=appointment_id)
                old_status = appointment.status
                appointment.status = new_status
                appointment.save()
                status_display = dict(appointment.STATUS_CHOICES).get(new_status, new_status)
                messages.success(request, f"Appointment status updated to {status_display}.")
            except Appointment.DoesNotExist:
                messages.error(request, "Appointment not found.")
        
        return redirect('staff_dashboard')

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
                    report = PatientReport.objects.create(
                        patient=patient,
                        staff=request.user,
                        diagnosis=diagnosis,
                        barangay=barangay,
                        services_provided=services
                    )
                    # Save medications from form (medication_name_0, medication_quantity_0, medication_dosage_0, ...)
                    i = 0
                    while True:
                        name = (request.POST.get('medication_name_%s' % i) or '').strip()
                        if not name:
                            i += 1
                            if i > 50:
                                break
                            continue
                        qty = request.POST.get('medication_quantity_%s' % i)
                        freq = request.POST.get('medication_dosage_%s' % i)
                        try:
                            qty_val = int(qty) if qty else 1
                        except ValueError:
                            qty_val = 1
                        if freq in dict(ReportMedication.DOSAGE_FREQUENCY_CHOICES):
                            ReportMedication.objects.create(
                                report=report,
                                medication_name=name,
                                quantity=qty_val,
                                dosage_frequency=freq
                            )
                        i += 1
                        if i > 50:
                            break
                    # Update predictive analysis and barangay stats so new diagnosis/barangay show up
                    try:
                        from website.ml_PA import generate_analysis_data
                        generate_analysis_data()
                    except Exception:
                        pass
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
    appointments = Appointment.objects.filter(preferred_date__gte=date.today()).order_by('preferred_date', 'preferred_time')
    
    # Organize appointments by date and time slot for calendar view
    from .utils import generate_timeslots
    
    # Get all time slots (8 AM - 5 PM, 30-minute intervals)
    all_slots = generate_timeslots()
    
    # Create a mapping of (date, time) -> appointment for quick lookup
    appointment_map = {}
    for appointment in appointments:
        key = (appointment.preferred_date, appointment.preferred_time)
        appointment_map[key] = appointment
    
    # Get unique dates from appointments
    appointment_dates = set(appointments.values_list('preferred_date', flat=True))
    if not appointment_dates:
        # If no appointments, show today's date
        appointment_dates = {date.today()}
    
    # Build structured data for template: list of dates, each with list of time slots
    appointments_calendar = []
    for appt_date in sorted(appointment_dates):
        date_slots = []
        for slot in all_slots:
            appointment = appointment_map.get((appt_date, slot))
            date_slots.append({
                'time': slot,
                'appointment': appointment,
                'is_booked': appointment is not None
            })
        appointments_calendar.append({
            'date': appt_date,
            'slots': date_slots
        })

    try:
        analysis = joblib.load(ANALYSIS_FILE)
    except:
        analysis = {}

    # Load events for info officer
    events = Event.objects.filter(is_active=True).order_by('event_date') if request.user.role == 'info_officer' else None
    all_events = Event.objects.all().order_by('-event_date') if request.user.role == 'info_officer' else None

    return render(request, 'staff_dashboard.html', {
        'user_role': request.user.role,
        'patient_reports': patient_reports,
        'patient_profiles': patient_profiles,
        'appointments': appointments,
        'appointments_calendar': appointments_calendar,
        'analysis': analysis,
        'search_query': search_query,
        'events': events,
        'all_events': all_events,
    })


# -----------------------------
# EVENT MANAGEMENT (Info Officer)
# -----------------------------
@never_cache
@login_required
def manage_events(request):
    """View for info officers to manage events - handles POST requests from staff_dashboard"""
    if request.user.role != 'info_officer':
        return HttpResponseForbidden("You don't have access to this page.")

    if request.method == 'POST':
        if request.POST.get('delete_event'):
            event_id = request.POST.get('delete_event')
            try:
                event = Event.objects.get(id=event_id)
                event.delete()
                messages.success(request, f"Event '{event.title}' deleted successfully.")
            except Event.DoesNotExist:
                messages.error(request, "Event not found.")
        elif request.POST.get('toggle_event'):
            event_id = request.POST.get('toggle_event')
            try:
                event = Event.objects.get(id=event_id)
                event.is_active = not event.is_active
                event.save()
                status = "activated" if event.is_active else "deactivated"
                messages.success(request, f"Event '{event.title}' {status} successfully.")
            except Event.DoesNotExist:
                messages.error(request, "Event not found.")
        elif request.POST.get('edit_event'):
            event_id = request.POST.get('edit_event')
            try:
                event = Event.objects.get(id=event_id)
                form = EventForm(request.POST, instance=event)
                if form.is_valid():
                    event = form.save(commit=False)
                    event.created_by = request.user
                    event.save()
                    messages.success(request, f"Event '{event.title}' updated successfully.")
                else:
                    messages.error(request, "Please correct the errors below.")
            except Event.DoesNotExist:
                messages.error(request, "Event not found.")
        elif request.POST.get('create_event'):
            # Create new event
            form = EventForm(request.POST)
            if form.is_valid():
                event = form.save(commit=False)
                event.created_by = request.user
                event.save()
                messages.success(request, f"Event '{event.title}' created successfully.")
            else:
                messages.error(request, "Please correct the errors below.")
        
        return redirect('staff_dashboard')

    # For GET requests, this will be handled in staff_dashboard
    return redirect('staff_dashboard')
