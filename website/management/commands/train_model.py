from django.core.management.base import BaseCommand
from website.ml_PA import train_predictive_model

class Command(BaseCommand):
    help = 'Train the Random Forest predictive model'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Training predictive model..."))
        model = train_predictive_model()
        if model:
            self.stdout.write(self.style.SUCCESS("Training complete!"))
        else:
            self.stdout.write(self.style.ERROR("No data found to train model."))
