# website/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from website.models import PatientReport
from website.ml_PA import train_predictive_model, generate_analysis_data

@receiver(post_save, sender=PatientReport)
def retrain_model_on_new_report(sender, instance, created, **kwargs):
    if created:
        print(f"New report added for {instance.patient}. Retraining model...")
        train_predictive_model()
        print("Model retraining complete.")
        generate_analysis_data()
        print("Model retraining and analysis update complete.")