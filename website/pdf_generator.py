from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
import os

def generate_appointment_forms(appointment):
    file_path = f"/tmp/{appointment.patient.fname}_{appointment.id}_forms.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("MediPal - Appointment Summary", styles["Title"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Patient: {appointment.patient.fname} {appointment.patient.lname}", styles["Normal"]))
    story.append(Paragraph(f"Type: {appointment.get_appointment_type_display()}", styles["Normal"]))
    story.append(Paragraph(f"Date: {appointment.scheduled_date}", styles["Normal"]))
    story.append(Paragraph(f"Time: {appointment.scheduled_time.strftime('%I:%M %p')}", styles["Normal"]))
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
    return file_path
