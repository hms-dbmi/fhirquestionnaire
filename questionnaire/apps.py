from os.path import isfile, join
from os import listdir
import json

from django.apps import AppConfig
from django.conf import settings

from questionnaire.fhir import FHIR


class QuestionnaireConfig(AppConfig):
    name = 'questionnaire'

    def ready(self):

        import logging
        logger = logging.getLogger(__name__)

        # Load FHIR resources and update the FHIR server
        fhir_dir = join(settings.STATIC_ROOT, 'questionnaire/fhir')
        for file in [f for f in listdir(fhir_dir) if isfile(join(fhir_dir, f))]:
            with open(join(fhir_dir, file)) as f:
                logger.debug('Loading {}'.format(file))

                # Create it in FHIR
                resource = json.loads(f.read())
                FHIR.update_resource(resource)
