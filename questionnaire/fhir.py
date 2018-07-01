import requests
import datetime
from furl import furl

from django.conf import settings
from fhirclient import client
from fhirclient.models.bundle import Bundle, BundleEntry
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.patient import Patient
from fhirclient.models.questionnaire import Questionnaire, QuestionnaireItem
from fhirclient.models.questionnaireresponse import QuestionnaireResponse, QuestionnaireResponseItem, QuestionnaireResponseItemAnswer

import logging
logger = logging.getLogger(__name__)


class FHIR:

    @staticmethod
    def update_resource(questionnaire_json):

        try:
            # Prepare the client
            fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

            # Build the questionnaire
            questionnaire = Questionnaire(questionnaire_json)

            # Save it
            questionnaire.update(fhir.server)

            logger.debug('Updated FHIR resource: {}'.format(questionnaire.id))

        except Exception as e:
            logger.exception(e)

    @staticmethod
    def get_resources(questionnaire_id, patient_email):

        # Build the transaction
        transaction = {
            'resourceType': 'Bundle',
            'type': 'transaction',
            'entry': []
        }

        # Get the questionnaire
        transaction['entry'].append({
            'request': {
                'url': 'Questionnaire?_id={}'.format(questionnaire_id),
                'method': 'GET'
            }
        })

        # Add the request for the patient
        transaction['entry'].append({
            'request': {
                'url': 'Patient?identifier=http://schema.org/email|{}'.format(patient_email),
                'method': 'GET'
            }
        })

        # Query for a response

        # Execute the search
        response = requests.post(settings.FHIR_URL, headers={'content-type': 'application/json'}, json=transaction)
        response.raise_for_status()

        # Build the objects
        bundle = Bundle(response.json())

        # Check for the questionnaire
        if not bundle.entry[0].resource.entry or bundle.entry[0].resource.entry[0].resource.resource_type != 'Questionnaire':
            raise FHIR.QuestionnaireDoesNotExist()

        # Instantiate it
        questionnaire = bundle.entry[0].resource.entry[0].resource

        # Check for the patient
        if not bundle.entry[1].resource.entry or bundle.entry[1].resource.entry[0].resource.resource_type != 'Patient':
            raise FHIR.PatientDoesNotExist()

        # Get it
        patient = bundle.entry[1].resource.entry[0].resource

        return questionnaire, patient

    @staticmethod
    def check_patient(patient_email):

        # Prepare the client
        fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

        # Set the search parameters
        struct = {'identifier': 'http://schema.org/email|{}'.format(patient_email)}

        # Get the questionnaire
        search = Patient.where(struct=struct)
        resources = search.perform_resources(fhir.server)
        if not resources:
            raise FHIR.PatientDoesNotExist

    @staticmethod
    def check_response(questionnaire_id, patient_email):

        # Prepare the client
        fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

        # Set the search parameters
        struct = {'questionnaire': questionnaire_id,
                  'source:Patient.identifier': 'http://schema.org/email|{}'.format(patient_email)}

        # Get the questionnaire
        search = QuestionnaireResponse.where(struct=struct)
        resources = search.perform_resources(fhir.server)
        if resources:
            raise FHIR.QuestionnaireResponseAlreadyExists

    @staticmethod
    def submit(fhir_url, questionnaire_id, patient_email, form):

        # Prepare the client
        fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': fhir_url})

        # Get the questionnaire
        questionnaire, patient = FHIR.get_resources(questionnaire_id, patient_email)

        # Build the response
        response = QuestionnaireResponse()
        response.questionnaire = FHIR._reference_to(questionnaire)
        response.source = FHIR._reference_to(patient)
        response.status = 'completed'
        response.authored = FHIRDate(datetime.datetime.utcnow().isoformat())
        response.author = FHIR._reference_to(patient)

        # Collect all questions
        question_items = FHIR._get_questions(questionnaire.item)

        # Build the items
        answers = []
        for question in question_items:

            # Create the response item
            item = QuestionnaireResponseItem()
            item.linkId = question.linkId

            # Create the answer
            answer = QuestionnaireResponseItemAnswer()

            # Check type
            if question.type in ['text', 'date', 'datetime']:
                answer.valueString = form[question.linkId]

            elif question.type == 'boolean':
                answer.valueBoolean = form[question.linkId]

            elif question.type == 'date':
                answer.valueDate = form[question.linkId]

            # Set it on the item
            item.answer = [answer]

            # Set it on the response
            answers.append(item)

        # Set them on the response
        response.item = answers

        # Save it
        response.create(fhir.server)

    @staticmethod
    def _get_questions(items):

        # Collect them
        questions_items = []

        # Get all the not groups
        questions_items.extend([item for item in items if item.type != 'group'])

        # Recurse into groups to get all question items
        for group in [item for item in items if item.type == 'group']:
            questions_items.extend(FHIR._get_questions(group.item))

        return questions_items

    @staticmethod
    def _reference_to(resource):
        """
        Used to create a FHIR reference object based on a FHIRClient.models object
        :param resource: FHIRClient.models class object (i.e. Patient())
        :returns: FHIRReference object
        """
        reference = FHIRReference()
        reference.reference = '{}/{}'.format(resource.resource_type, resource.id)
        return reference

    class QuestionnaireDoesNotExist(Exception):
        pass

    class PatientDoesNotExist(Exception):
        pass

    class QuestionnaireResponseAlreadyExists(Exception):
        pass
