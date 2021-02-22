import os
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ppmutils.ppm import PPM

from api.views import QualtricsView


class Command(BaseCommand):
    help = 'Create Qualtrics survey Questionnaire resources in FHIR'

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('survey', type=str)
        parser.add_argument('survey_id', type=str)
        parser.add_argument('questionnaire_id', type=str)

    def handle(self, *args, **options):

        # Ensure it exists
        if not os.path.exists(options['survey']):
            raise CommandError(f'Qualtrics survey "{options["survey"]}" does not exist')

        try:
            with open(options["survey"], "r") as f:
                # Load the survey
                survey = json.load(f)

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Error: Could not open survey file: {e}"
                ))
            raise CommandError(f'Qualtrics file "{options["survey"]}" could not be opened')

        try:
            # Convert it
            questionnaire = QualtricsView.questionnaire(
                survey, options['survey_id'], options['questionnaire_id'],
            )

            # Submit it
            QualtricsView.questionnaire_transaction(
                questionnaire, options['questionnaire_id']
            )

            self.stdout.write(self.style.SUCCESS(
                f"SUCCESS: Qualtrics survey '{options['survey_id']}' saved "
                f"to {options['questionnaire_id']}"
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Error: Questionnaire error: {e}"
            ))
