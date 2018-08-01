import os
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from consent.apps import ConsentConfig
from fhirquestionnaire.fhir import FHIR


class Command(BaseCommand):
    help = 'Updated contained FHIR resources in the current server'

    def handle(self, *args, **options):

        # Get the app
        app = ConsentConfig.name

        # Load FHIR resources and update the FHIR server
        fhir_dir = os.path.join(settings.BASE_DIR, app, 'fhir')

        # Ensure it exists
        if not os.path.exists(fhir_dir):
            raise CommandError('App {} does not have a "fhir" directory'.format(app))

        # Collect resources
        for file_path in [os.path.join(fhir_dir, f) for f in os.listdir(fhir_dir) if os.path.isfile(os.path.join(fhir_dir, f))]:
            with open(file_path) as f:

                try:
                    # Read the resource JSON
                    resource = json.loads(f.read())

                    # Set the resource name
                    name = '{}/{}'.format(resource['resourceType'], resource['id'])

                    # Do the update
                    if FHIR.update_resource(resource):
                        self.stdout.write(self.style.SUCCESS('Successfully updated FHIR resource: {}'.format(name)))

                    else:
                        raise CommandError('Resource could not be updated: {}'.format(name))

                except ValueError:
                    raise CommandError('Resource could not be read: {}'.format(file_path))

                except KeyError:
                    raise CommandError('FHIR Resource does not contain ID and/or ResourceType: {}'.format(file_path))
