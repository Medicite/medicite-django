# utils.py
from datetime import datetime, timedelta, time, date
from django.utils.timezone import localdate
from .models import Appointment

def generate_timeslots(start_hour=8, end_hour=17, interval=30):
    """Generates 30-minute interval time slots between start and end hour."""
    slots = []
    current = time(hour=start_hour, minute=0)
    while (current.hour * 60 + current.minute) < (end_hour * 60):
        slots.append(current)
        # Increment by interval
        current = (datetime.combine(date.today(), current) + timedelta(minutes=interval)).time()
    return slots

def get_next_available_slot():
    """
    Returns the next available appointment slot (date and time)
    skipping weekends and already booked slots.
    """
    slots = generate_timeslots()
    current_date = localdate()

    while True:
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue

        # Get already used slots for this date
        used_slots = Appointment.objects.filter(preferred_date=current_date).values_list('preferred_time', flat=True)
        available = [s for s in slots if s not in used_slots]

        if available:
            return current_date, available[0]

        # Move to next day
        current_date += timedelta(days=1)
