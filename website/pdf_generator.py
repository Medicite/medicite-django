from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
import os
from django.conf import settings
from pathlib import Path

def generate_appointment_forms(appointment):
    # Create appointments directory in the project root if it doesn't exist
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    appointments_dir = BASE_DIR / 'appointments'
    appointments_dir.mkdir(exist_ok=True)
    
    # Create cross-platform file path
    filename = f"{appointment.patient_profile.fname}_{appointment.id}_forms.pdf"
    file_path = appointments_dir / filename
    
    doc = SimpleDocTemplate(str(file_path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("MediPal - Appointment Summary", styles["Title"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Patient: {appointment.patient_profile.fname} {appointment.patient_profile.lname}", styles["Normal"]))
    story.append(Paragraph(f"Type: {appointment.get_appointment_type_display()}", styles["Normal"]))
    story.append(Paragraph(f"Date: {appointment.preferred_date}", styles["Normal"]))
    story.append(Paragraph(f"Time: {appointment.preferred_time.strftime('%I:%M %p')}", styles["Normal"]))
    story.append(Spacer(1, 20))

    forms = []
    if appointment.consent_form:
        forms.append("Patient Consent Form")
    if appointment.lab_request_form:
        forms.append("Lab Request Form")
    if appointment.philhealth_form:
        forms.append("PhilHealth Form")

    story.append(Paragraph("Selected Forms:", styles["Heading2"]))
    for f in forms:
        story.append(Paragraph(f"• {f}", styles["Normal"]))

    doc.build(story)
    return str(file_path)
