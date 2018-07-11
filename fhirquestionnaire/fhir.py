import requests
import datetime
from dateutil.parser import parser
import uuid
import base64
from urllib.parse import quote
from furl import furl

from django.template.loader import render_to_string
from django.conf import settings

from fhirclient import client
from fhirclient.models.bundle import Bundle, BundleEntry
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.patient import Patient
from fhirclient.models.coding import Coding
from fhirclient.models.fhirelementfactory import FHIRElementFactory
from fhirclient.models.narrative import Narrative
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.period import Period
from fhirclient.models.consent import Consent, ConsentExcept, ConsentPolicy
from fhirclient.models.contract import Contract, ContractSigner
from fhirclient.models.signature import Signature
from fhirclient.models.composition import Composition, CompositionSection
from fhirclient.models.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhirclient.models.questionnaire import Questionnaire, QuestionnaireItem
from fhirclient.models.questionnaireresponse import QuestionnaireResponse, QuestionnaireResponseItem, QuestionnaireResponseItemAnswer

import logging
logger = logging.getLogger(__name__)


class FHIR:

    @staticmethod
    def update_resource(json):

        try:
            # Prepare the client
            fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

            # Get the resource type
            resource_type = json['resourceType']

            # Create the resource
            resource = FHIRElementFactory.instantiate(resource_type, json)

            # Save it
            resource.update(fhir.server)

            logger.debug('Updated FHIR resource: {}/{}'.format(resource.resource_type, resource.id))

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
                'url': 'Patient?identifier=http://schema.org/email|{}'.format(quote(patient_email)),
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

        # Check questionnaire id
        if questionnaire_id == 'ppm-neer-registration-questionnaire':

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
                if question.type in ['text', 'date', 'datetime', 'string']:
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

        elif questionnaire_id == 'neer-signature':

            # Get the exception codes from the form
            data = dict(form)
            codes = data.get('except', [])
            name = data['name-of-participant'][0]
            signature = data['signature-of-participant'][0]

            # Parse the date
            try:
                date = datetime.datetime.strptime(data['date'][0], '%Y-%m-%d')
            except ValueError as e:
                logger.exception(e)

                # Default to now
                date = datetime.datetime.utcnow()

            # Create needed resources
            questionnaire_response = FHIR._questionnaire_response(questionnaire, patient, date, codes)
            contract = FHIR._contract(patient, date, name, signature, questionnaire_response)
            exceptions = FHIR._consent_exceptions(codes)
            consent = FHIR._consent(patient, date, exceptions)

            # Get the signature HTML
            text = '<div>{}</div>'.format(render_to_string('consent/neer-signature/_consent.html'))

            # Generate composition
            composition = FHIR._composition(patient, date, text, consent, contract)

            # Bundle it into a transaction
            bundle = FHIR._bundle([questionnaire_response, consent, contract, composition])

            # Save it
            FHIR._post_bundle(bundle)

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

    @staticmethod
    def _reference(resource_type, resource_id):
        """
        Used to create a FHIR reference object based on a FHIRClient.models object
        :param resource: FHIRClient.models class object (i.e. Patient())
        :returns: FHIRReference object
        """
        reference = FHIRReference({'reference': '{}/{}'.format(resource_type, resource_id)})

        return reference

    class QuestionnaireDoesNotExist(Exception):
        pass

    class PatientDoesNotExist(Exception):
        pass

    class QuestionnaireResponseAlreadyExists(Exception):
        pass

    @staticmethod
    def _consent_questionnaire_response(questionnaire, patient, date, exceptions=[]):

        # Build the response
        response = QuestionnaireResponse()
        response.questionnaire = FHIR._reference_to(questionnaire)
        response.source = FHIR._reference_to(patient)
        response.status = 'completed'
        response.authored = FHIRDate(date.isoformat())
        response.author = FHIR._reference_to(patient)

        # Map exception codes to linkId
        codes = {
            'question-1': '82078001',
            'question-2': '165334004',
            'question-3': '258435002',
            'question-4': '284036006',
            'question-5': '702475000',
        }

        # Check for exceptions
        response.item = []
        for linkId, code in codes.items():

            # Add the items
            item = QuestionnaireResponseItem()
            item.linkId = linkId

            # Add the answer
            answer = QuestionnaireResponseItemAnswer()
            answer.valueBoolean = code in exceptions
            item.answer = [answer]

            # Set it on the questionnaire
            response.item.append(item)

        # Set it on the questionnaire
        return response

    @staticmethod
    def _questionnaire_response(questionnaire, patient, date, exceptions):

        # Build the response
        response = QuestionnaireResponse()
        response.id = uuid.uuid4().urn
        response.questionnaire = FHIR._reference_to(questionnaire)
        response.source = FHIR._reference_to(patient)
        response.status = 'completed'
        response.authored = FHIRDate(date.isoformat())
        response.author = FHIR._reference_to(patient)

        # Map exception codes to linkId
        codes = {
            'question-1': '82078001',
            'question-2': '165334004',
            'question-3': '258435002',
            'question-4': '284036006',
            'question-5': '702475000',
        }

        # Check for exceptions
        answers = []
        for linkId, code in codes.items():

            # Add the items
            item = QuestionnaireResponseItem()
            item.linkId = linkId

            # Add the answer
            answer = QuestionnaireResponseItemAnswer()
            answer.valueBoolean = code in exceptions
            item.answer = [answer]

            # Set it on the questionnaire
            answers.append(item)

        # Set it on the questionnaire
        response.item = answers

        return response

    @staticmethod
    def _consent_exceptions(codes):

        # Map codes to displays
        displays = {
            '284036006': 'Equipment monitoring',
            '702475000': 'Referral to clinical trial',
            '82078001': 'Taking blood sample',
            '165334004': 'Stool sample sent to lab',
            '258435002': 'Tumor tissue sample',
        }

        # Collect exceptions
        exceptions = []
        for code in codes:

            # Create the exception
            exception = ConsentExcept()
            exception.type = "deny"
            exception.code = [FHIR._coding("http://snomed.info/sct", code, displays[code])]

            # Add it
            exceptions.append(exception)

        return exceptions

    @staticmethod
    def _consent(patient, date, exceptions=[]):

        # Make it
        consent = Consent()
        consent.status = 'proposed'
        consent.id = uuid.uuid4().urn
        consent.dateTime = FHIRDate(date.isoformat())
        consent.patient = FHIR._reference_to(patient)

        # Policy
        policy = ConsentPolicy()
        policy.authority = 'HMS-DBMI'
        policy.uri = 'https://hms.harvard.edu'
        consent.policy = [policy]

        # Period
        period = Period()
        period.start = FHIRDate(date.isoformat())

        # Add items
        consent.period = period
        consent.purpose = [FHIR._coding('http://hl7.org/fhir/v3/ActReason', 'HRESCH', 'healthcare research')]

        # Add exceptions
        consent.except_fhir = exceptions

        return consent

    @staticmethod
    def _contract(patient, date, patient_name, patient_signature, questionnaire_response):

        # Build it
        contract = Contract()
        contract.status = 'executed'
        contract.issued = FHIRDate(date.isoformat())
        contract.id = uuid.uuid4().urn

        # Signer
        signer = ContractSigner()
        signer.type = FHIR._coding('http://hl7.org/fhir/ValueSet/contract-signer-type', 'CONSENTER', 'Consenter')
        signer.party = FHIR._reference_to(patient)

        # Signature
        signature = Signature()
        signature.type = [FHIR._coding('http://hl7.org/fhir/ValueSet/signature-type', '1.2.840.10065.1.12.1.7', 'Consent Signature')]
        signature.when = FHIRDate(date.isoformat())
        signature.contentType = 'text/plain'
        signature.blob = FHIR._blob(patient_signature)
        signature.whoReference = FHIR._reference_to(patient)
        signature.whoReference.display = patient_name

        # Add references
        signer.signature = [signature]
        contract.signer = [signer]
        contract.bindingReference = FHIR._reference_to(questionnaire_response)

        return contract

    @staticmethod
    def _composition(patient, date, text, consent, contract):

        # Build it
        composition = Composition()
        composition.id = uuid.uuid4().urn
        composition.status = 'final'
        composition.subject = FHIR._reference_to(patient)
        composition.date = FHIRDate(date.isoformat())
        composition.title = 'Signature'
        composition.author = [FHIRReference({'reference': 'Device/hms-dbmi-ppm-consent'})]

        # Composition type
        coding = Coding()
        coding.system = 'http://loinc.org'
        coding.code = '83930-8'
        coding.display = 'Research Consent'

        # Convoluted code property
        code = CodeableConcept()
        code.coding = [coding]

        # Combine
        composition.type = code

        # Add sections
        composition.section = []

        # Add text
        narrative = Narrative()
        narrative.div = text
        narrative.status = 'additional'
        text_section = CompositionSection()
        text_section.text = narrative
        composition.section.append(text_section)

        # Add consent
        consent_section = CompositionSection()
        consent_section.entry = [FHIR._reference_to(consent)]
        composition.section.append(consent_section)

        # Add contract
        contract_section = CompositionSection()
        contract_section.entry = [FHIR._reference_to(contract)]
        composition.section.append(contract_section)

        return composition

    @staticmethod
    def _code(system, code, display):

        # Build it
        coding = Coding()
        coding.system = system
        coding.code = code
        coding.display = display

        # Convoluted code property
        codeable = CodeableConcept()
        codeable.coding = [coding]

        return codeable

    @staticmethod
    def _coding(system, code, display):

        # Build it
        coding = Coding()
        coding.system = system
        coding.code = code
        coding.display = display

        return coding

    @staticmethod
    def _blob(value):

        # Base64 encode it
        return base64.b64encode(str(value).encode('utf-8')).decode('utf-8')

    @staticmethod
    def _bundle(resources):

        # Build the bundle
        bundle = Bundle()
        bundle.type = 'transaction'
        bundle.entry = []

        for resource in resources:

            # Build the entry request
            bundle_entry_request = BundleEntryRequest()
            bundle_entry_request.method = 'POST'
            bundle_entry_request.url = resource.resource_type

            # Add it to the entry
            bundle_entry = BundleEntry()
            bundle_entry.resource = resource
            bundle_entry.fullUrl = resource.id
            bundle_entry.request = bundle_entry_request

            # Add it
            bundle.entry.append(bundle_entry)

        return bundle

    @staticmethod
    def _post_bundle(bundle):

        try:
            # Post it
            response = requests.post(settings.FHIR_URL,
                                     headers={'content-type': 'application/json'},
                                     json=bundle.as_json())
            response.raise_for_status()

        except Exception as e:
            logger.exception(e)