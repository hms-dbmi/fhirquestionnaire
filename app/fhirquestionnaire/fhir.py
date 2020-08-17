import requests
import datetime
import uuid
import hashlib
import base64
from urllib.parse import quote, urlencode

from django.template.loader import render_to_string
from django.conf import settings

from fhirclient import client
from fhirclient.models.bundle import Bundle, BundleEntry
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.patient import Patient
from fhirclient.models.humanname import HumanName
from fhirclient.models.relatedperson import RelatedPerson
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
from ppmutils.ppm import PPM
from ppmutils.fhir import FHIR as PPMFHIR

import logging
logger = logging.getLogger(__name__)


class FHIR:

    @staticmethod
    def client():
        return client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

    @staticmethod
    def submit_consent(study, patient_email, form, pdf=None):
        """
        Accepts the filled out form for the given study and submits the data to FHIR for retaining
        :param study: The study for which the consent was completed
        :type study: str
        :param patient_email: The current user's email
        :type patient_email: str
        :param form: The form filled out for the consent
        :type form: Form
        :param pdf: The generated PDF of the consent as raw data
        :type pdf: bytearray
        :return: Whether the operation succeeded or not
        :rtype: bool
        """

        # Get the questionnaire
        questionnaire, patient = FHIR.get_resources(PPM.Questionnaire.consent_questionnaire_for_study(study), patient_email)

        # Get the exception codes from the form
        data = dict(form)
        codes = data.get('exceptions', [])
        name = data['name']
        signature = data['signature']
        date = data['date'].isoformat()

        # Map exception codes to linkId
        # TODO: Figure out how to generalize the handling of exceptions per consent
        exception_codes = PPM.Questionnaire.exceptions(PPM.Questionnaire.consent_questionnaire_for_study(study))

        # Build answers
        answers = {linkId: code in codes for linkId, code in exception_codes.items()}

        # Create needed resources
        questionnaire_response = FHIR._questionnaire_response(questionnaire, patient, date, answers)
        contract = FHIR._contract(patient, date, name, signature, questionnaire_response)
        exceptions = FHIR._consent_exceptions(codes)
        consent = FHIR._consent(patient, date, exceptions)

        # Get the signature HTML
        text = '<div>{}</div>'.format(render_to_string('consent/{}/_consent.html'.format(study)))

        # Generate composition
        composition = FHIR._composition(patient, date, text, [consent, contract])

        # Bundle it into a transaction
        bundle = FHIR._bundle([questionnaire_response, consent, contract, composition])

        # Save it
        FHIR._post_bundle(bundle)

    @staticmethod
    def submit_questionnaire(study, patient_email, form):
        """
        Accepts the filled out form for the given study and submits the data to FHIR for retaining
        :param study: The study for which the questionnaire was completed
        :type study: str
        :param patient_email: The current user's email
        :type patient_email: str
        :param form: The form filled out for the questionnaire
        :type form: Form
        :return: Whether the operation succeeded or not
        :rtype: bool
        """
        # Get the questionnaire
        questionnaire, patient = FHIR.get_resources(PPM.Questionnaire.questionnaire_for_study(study), patient_email)

        # Just use now
        date = datetime.datetime.utcnow().isoformat()

        # Build the response
        questionnaire_response = FHIR._questionnaire_response(questionnaire, patient, date, form)

        # Bundle it into a transaction
        bundle = FHIR._bundle([questionnaire_response])

        # Save it
        FHIR._post_bundle(bundle)

    @staticmethod
    def submit_asd_individual(patient_email, forms):

        # Get the questionnaires and patient
        bundle = FHIR._query_resources([
            'Questionnaire?_id={}'.format(','.join([
                'ppm-asd-consent-individual-quiz',
                'individual-signature-part-1'
            ])),
            'Patient?identifier=http://schema.org/email|{}'.format(quote(patient_email)),
        ])

        # Get resources
        try:
            quiz_questionnaire = next(entry.resource for entry in bundle.entry[0].resource.entry
                                      if entry.resource.id == 'ppm-asd-consent-individual-quiz')
            signature_questionnaire = next(entry.resource for entry in bundle.entry[0].resource.entry
                                           if entry.resource.id == 'individual-signature-part-1')
        except (IndexError, KeyError, StopIteration):
            logger.error("Questionnaire could not be fetched", exc_info=True, extra={
                'questionnaires': ['ppm-asd-consent-individual-quiz', 'individual-signature-part-1'],
            })
            raise FHIR.QuestionnaireDoesNotExist

        try:
            patient = next(entry.resource for entry in bundle.entry[1].resource.entry)
        except (IndexError, KeyError):
            logger.error("Patient could not be fetched", exc_info=True, extra={
                'patient': FHIR._obfuscate_email(patient_email),
            })
            raise FHIR.PatientDoesNotExist

        # Get the exception codes from the form
        individual_form = forms['individual']
        codes = individual_form.get('exceptions', [])
        name = individual_form['name']
        signature = individual_form['signature']
        date = individual_form['date'].isoformat()

        # Map exception codes to linkId
        exception_codes = {
            'question-1': '225098009',
            'question-2': '284036006',
            'question-3': '702475000',
        }

        # Build answers
        answers = {linkId: code in codes for linkId, code in exception_codes.items()}

        # Create needed resources
        quiz_questionnaire_response = FHIR._questionnaire_response(quiz_questionnaire, patient, date, forms['quiz'])
        questionnaire_response = FHIR._questionnaire_response(signature_questionnaire, patient, date, answers)
        contract = FHIR._contract(patient, date, name, signature, questionnaire_response)
        exceptions = FHIR._consent_exceptions(codes)
        consent = FHIR._consent(patient, date, exceptions)

        # Get the signature HTML
        text = '<div>{}</div>'.format(render_to_string('consent/asd/_individual_consent.html'))

        # Generate composition
        composition = FHIR._composition(patient, date, text, [consent, contract])

        # Bundle it into a transaction
        bundle = FHIR._bundle([questionnaire_response, consent, contract, composition, quiz_questionnaire_response])

        # Save it
        FHIR._post_bundle(bundle)

    @staticmethod
    def submit_asd_guardian(patient_email, forms):

        # Get the questionnaires and patient
        bundle = FHIR._query_resources([
            'Questionnaire?_id={}'.format(','.join([
                'ppm-asd-consent-guardian-quiz',
                'guardian-signature-part-1',
                'guardian-signature-part-2',
                'guardian-signature-part-3'
            ])),
            'Patient?identifier=http://schema.org/email|{}'.format(quote(patient_email)),
        ])

        # Get resources
        try:
            quiz_questionnaire = next(entry.resource for entry in bundle.entry[0].resource.entry
                                      if entry.resource.id == 'ppm-asd-consent-guardian-quiz')
            guardian_signature_questionnaire = next(entry.resource for entry in bundle.entry[0].resource.entry
                                           if entry.resource.id == 'guardian-signature-part-1')
            guardian_reason_questionnaire = next(entry.resource for entry in bundle.entry[0].resource.entry
                                           if entry.resource.id == 'guardian-signature-part-2')
            ward_signature_questionnaire = next(entry.resource for entry in bundle.entry[0].resource.entry
                                           if entry.resource.id == 'guardian-signature-part-3')
        except (IndexError, KeyError, StopIteration):
            logger.error("Questionnaire could not be fetched", exc_info=True, extra={
                'questionnaires': ['ppm-asd-consent-guardian-quiz', 'guardian-signature-part-x'],
            })
            raise FHIR.QuestionnaireDoesNotExist

        try:
            patient = next(entry.resource for entry in bundle.entry[1].resource.entry)
        except (IndexError, KeyError, StopIteration):
            logger.error("Patient could not be fetched", exc_info=True, extra={
                'patient': FHIR._obfuscate_email(patient_email),
            })
            raise FHIR.PatientDoesNotExist

        # Process the guardian's resources first

        # Get the forms
        quiz = forms['quiz']
        ward_form = forms['ward']
        guardian_form = forms['guardian']

        # Get guardian values from form
        guardian_codes = guardian_form.get('exceptions', [])
        name = guardian_form['name']
        guardian = guardian_form['guardian']
        relationship = guardian_form['relationship']
        signature = guardian_form['signature']
        explained_signature = guardian_form['explained_signature']
        explained = guardian_form['explained']
        reason = guardian_form.get('reason', '')
        date = guardian_form['date']

        # Get ward values from form
        ward_codes = ward_form['exceptions']
        ward_signature = ward_form['signature']
        ward_date = ward_form['date'].isoformat()

        # Map exception codes to linkId
        guardian_exception_codes = {
            'question-1': '225098009',
            'question-2': '284036006',
            'question-3': '702475000',
        }

        # Build answers
        exception_answers = {linkId: code in guardian_codes for linkId, code in guardian_exception_codes.items()}
        reason_answers = {'question-1': explained, 'question-1-1': reason}

        # Create the related person resource
        related_person = FHIR._related_person(patient, guardian, relationship)

        # Create all questionnaire response resources
        quiz_questionnaire_response = FHIR._questionnaire_response(quiz_questionnaire, patient, date, quiz,
                                                                   related_person)
        guardian_signature_questionnaire_response = FHIR._questionnaire_response(guardian_signature_questionnaire,
                                                                                 patient, date, exception_answers,
                                                                                 related_person)
        guardian_explained_questionnaire_response = FHIR._questionnaire_response(guardian_reason_questionnaire,
                                                                                 patient, date, reason_answers,
                                                                                 related_person)

        # Create contract resources
        signature_contract = FHIR._related_contract(patient, date, name, related_person, guardian,
                                                    signature, guardian_signature_questionnaire_response)
        explained_contract = FHIR._related_contract(patient, date, name, related_person, guardian,
                                                    explained_signature, guardian_explained_questionnaire_response)

        # Create the guardian's consent
        exceptions = FHIR._consent_exceptions(guardian_codes)
        consent = FHIR._consent(patient, date, exceptions, related_person)

        # Get the signature HTML
        text = '<div>{}</div>'.format(render_to_string('consent/asd/_guardian_consent.html'))

        # Generate composition
        composition = FHIR._composition(patient, date, text, [consent, signature_contract, explained_contract])

        # Map exception codes to linkId
        ward_exception_codes = {
            'question-1': '225098009',
            'question-2': '284036006',
        }

        # Get the ward signature HTML
        ward_text = '<div>{}</div>'.format(render_to_string('consent/asd/_ward_assent.html'))

        # Create participant resources
        ward_exceptions = {linkId: code in ward_codes for linkId, code in ward_exception_codes.items()}
        ward_signature_questionnaire_response = FHIR._questionnaire_response(ward_signature_questionnaire,
                                                                             patient, date, ward_exceptions)

        # Create the contract and composition
        ward_contract = FHIR._contract(patient, ward_date, name, ward_signature, ward_signature_questionnaire_response)
        ward_composition = FHIR._composition(patient, ward_date, ward_text, [ward_contract])

        # Bundle it into a transaction
        bundle = FHIR._bundle([related_person,
                               quiz_questionnaire_response,
                               guardian_signature_questionnaire_response,
                               guardian_explained_questionnaire_response,
                               signature_contract,
                               explained_contract,
                               consent,
                               composition,
                               ward_signature_questionnaire_response,
                               ward_contract,
                               ward_composition])

        # Save it
        FHIR._post_bundle(bundle)

    @staticmethod
    def update_resource(json):
        '''
        Builds a FHIR resource from the passed JSON and updates the current server. Can be any valid
        FHIR resource that already exists in the server.
        :param json: JSON FHIR Resource
        :return: True if updated successfully, False otherwise
        '''

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

            return True

        except Exception as e:
            logger.error("Could not update resources: {}".format(e), exc_info=True, extra={
                'resource': json,
            })
            return False

    @staticmethod
    def _query_resources(queries=[]):

        # Build the transaction
        transaction = {
            'resourceType': 'Bundle',
            'type': 'transaction',
            'entry': []
        }

        # Get the questionnaire
        for query in queries:
            transaction['entry'].append({
                'request': {
                    'url': query,
                    'method': 'GET'
                }
            })

        # Query for a response

        # Execute the search
        response = requests.post(settings.FHIR_URL, headers={'content-type': 'application/json'}, json=transaction)
        response.raise_for_status()

        # Build the objects
        bundle = Bundle(response.json())

        return bundle

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
            logger.error("Questionnaire could not be fetched", exc_info=True, extra={
                'questionnaires': questionnaire_id,
            })
            raise FHIR.QuestionnaireDoesNotExist()

        # Instantiate it
        questionnaire = bundle.entry[0].resource.entry[0].resource

        # Check for the patient
        if not bundle.entry[1].resource.entry or bundle.entry[1].resource.entry[0].resource.resource_type != 'Patient':
            logger.error("Patient could not be fetched", exc_info=True, extra={
                'patient': FHIR._obfuscate_email(patient_email),
                'questionnaires': questionnaire_id,
                'bundle': bundle.as_json(),
            })
            raise FHIR.PatientDoesNotExist()

        # Get it
        patient = bundle.entry[1].resource.entry[0].resource

        return questionnaire, patient

    @staticmethod
    def get_patient(patient_email):

        # Build the transaction
        transaction = {
            'resourceType': 'Bundle',
            'type': 'transaction',
            'entry': []
        }

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
        if not bundle.entry[0].resource.entry or bundle.entry[0].resource.entry[0].resource.resource_type != 'Patient':
            logger.error("Patient could not be fetched", exc_info=True, extra={
                'patient': patient_email,
            })
            raise FHIR.QuestionnaireDoesNotExist()

        # Instantiate it
        patient = bundle.entry[0].resource.entry[0].resource

        return patient

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
            logger.warning('Patient not found: {}'.format(FHIR._obfuscate_email(patient_email)))
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
            logger.warning('Questionnaire not found: {}'.format(questionnaire_id))
            raise FHIR.QuestionnaireResponseAlreadyExists

    @staticmethod
    def check_responses(questionnaire_ids, patient_email):

        # Prepare the client
        fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

        for questionnaire_id in questionnaire_ids:

            # Set the search parameters
            struct = {'questionnaire': questionnaire_id,
                      'source:Patient.identifier': 'http://schema.org/email|{}'.format(patient_email)}

            # Get the questionnaire
            search = QuestionnaireResponse.where(struct=struct)
            resources = search.perform_resources(fhir.server)
            if resources:
                raise FHIR.QuestionnaireResponseAlreadyExists

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
    def _questionnaire_response(questionnaire, patient, date=datetime.datetime.utcnow().isoformat(), answers={}, author=None):

        # Build the response
        response = QuestionnaireResponse()
        response.id = uuid.uuid4().urn
        response.questionnaire = FHIR._reference_to(questionnaire)
        response.source = FHIR._reference_to(patient)
        response.status = 'completed'
        response.authored = FHIRDate(date)
        response.author = FHIR._reference_to(author if author else patient)

        # Collect response items flattened
        response.item = FHIR._questionnaire_response_items(questionnaire.item, answers)

        # Set it on the questionnaire
        return response

    @staticmethod
    def _questionnaire_response_items(questions, form):

        # Collect items
        items = []

        # Iterate through questions
        for question in questions:

            # Disregard invalid question types
            if not question.linkId or not question.type or question.type == 'display':
                continue

            # If a group, process subelements and append them to current level
            elif question.type == 'group':

                # We don't respect heirarchy for groupings
                group_items = FHIR._questionnaire_response_items(question.item, form)
                if group_items:
                    items.extend(group_items)
                continue

            # Get the value
            value = form.get(question.linkId, form.get(question.linkId, None))

            # Add the item
            if value is None or not str(value):
                logger.debug('No answer for {}'.format(question.linkId))
                continue

            # Check for an empty list
            elif type(value) is list and len(value) == 0:
                logger.debug('Empty answer set for {}, skipping'.format(question.linkId))
                continue

            # Create the item
            item = FHIR._questionnaire_response_item(question.linkId, value)

            # Check for subitems
            if question.item:

                # Get the items
                question_items = FHIR._questionnaire_response_items(question.item, form)
                if question_items:
                    # TODO: Uncomment the following line after QuestionnaireResponse parsing is updated to
                    # TODO: look for subanswers in subitems as opposed to one flat list
                    #item.item = question_items

                    # Save all answers flat for now
                    items.extend(question_items)

            # Add the item
            items.append(item)

        return items

    @staticmethod
    def _questionnaire_response_item(link_id, cleaned_data):

        # Create the response item
        item = QuestionnaireResponseItem()
        item.linkId = link_id

        # Create the answer items list
        item.answer = []

        # Check the value type
        if type(cleaned_data) is list:

            # Add each item in the list
            for value in cleaned_data:
                item.answer.append(FHIR._questionnaire_response_item_answer(value))

        else:

            # Add the single item
            item.answer.append(FHIR._questionnaire_response_item_answer(cleaned_data))

        return item

    @staticmethod
    def _questionnaire_response_item_answer(value):

        # Create the item
        answer = QuestionnaireResponseItemAnswer()

        # Check type
        if type(value) is str:
            answer.valueString = str(value)

        elif type(value) is bool:
            answer.valueBoolean = value

        elif type(value) is int:
            answer.valueInteger = value

        elif type(value) is datetime.datetime:
            answer.valueDateTime = FHIRDate(value.isoformat())

        else:
            logger.warning('Unhandled answer type: {} - {}'.format(type(value), value))

            # Cast it as string
            answer.valueString = str(value)

        return answer

    @staticmethod
    def _consent_exceptions(codes):

        # Map codes to displays
        displays = {
            '284036006': 'Equipment monitoring',
            '702475000': 'Referral to clinical trial',
            '82078001': 'Taking blood sample',
            '165334004': 'Stool sample sent to lab',
            '258435002': 'Tumor tissue sample',
            '225098009': 'Collection of sample of saliva',
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
    def _related_person(patient, name, relationship):

        # Make it
        person = RelatedPerson()
        person.id = uuid.uuid4().urn
        person.patient = FHIR._reference_to(patient)

        # Set the relationship
        code = CodeableConcept()
        code.text = relationship
        person.relationship = code

        # Set the name
        human_name = HumanName()
        human_name.text = name
        person.name = [human_name]

        return person

    @staticmethod
    def _consent(patient, date, exceptions=[], related_person=None):

        # Make it
        consent = Consent()
        consent.status = 'proposed'
        consent.id = uuid.uuid4().urn
        consent.dateTime = FHIRDate(date)
        consent.patient = FHIR._reference_to(patient)

        # Policy
        policy = ConsentPolicy()
        policy.authority = 'HMS-DBMI'
        policy.uri = 'https://hms.harvard.edu'
        consent.policy = [policy]

        # Check for a related person consenting
        if related_person:

            # Add them
            consent.consentingParty = [FHIR._reference_to(related_person)]

        # Period
        period = Period()
        period.start = FHIRDate(date)

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
        contract.issued = FHIRDate(date)
        contract.id = uuid.uuid4().urn

        # Signer
        signer = ContractSigner()
        signer.type = FHIR._coding('http://hl7.org/fhir/ValueSet/contract-signer-type', 'CONSENTER', 'Consenter')
        signer.party = FHIR._reference_to(patient)

        # Signature
        signature = Signature()
        signature.type = [FHIR._coding('http://hl7.org/fhir/ValueSet/signature-type', '1.2.840.10065.1.12.1.7', 'Consent Signature')]
        signature.when = FHIRDate(date)
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
    def _related_contract(patient, date, patient_name, related_person, related_person_name,
                          related_person_signature, questionnaire_response):

        # Build it
        contract = Contract()
        contract.status = 'executed'
        contract.issued = FHIRDate(date)
        contract.id = uuid.uuid4().urn

        # Signer
        contract_signer = ContractSigner()
        contract_signer.type = FHIR._coding('http://hl7.org/fhir/ValueSet/contract-signer-type', 'CONSENTER', 'Consenter')
        contract_signer.party = FHIR._reference_to(related_person)

        # Signature
        signature = Signature()
        signature.type = [FHIR._coding('http://hl7.org/fhir/ValueSet/signature-type', '1.2.840.10065.1.12.1.7', 'Consent Signature')]
        signature.when = FHIRDate(date)
        signature.contentType = 'text/plain'
        signature.blob = FHIR._blob(related_person_signature)
        signature.whoReference = FHIR._reference_to(related_person)
        signature.whoReference.display = related_person_name

        # Refer to the patient
        patient_reference = FHIRReference({'reference': '{}/{}'.format(patient.resource_type, patient.id),
                                           'display': patient_name})
        signature.onBehalfOfReference = patient_reference

        # Add references
        contract_signer.signature = [signature]
        contract.signer = [contract_signer]
        contract.bindingReference = FHIR._reference_to(questionnaire_response)

        return contract

    @staticmethod
    def _composition(patient, date, text, resources=[]):

        # Build it
        composition = Composition()
        composition.id = uuid.uuid4().urn
        composition.status = 'final'
        composition.subject = FHIR._reference_to(patient)
        composition.date = FHIRDate(date)
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

        # Add related section resources
        for resource in resources:

            # Add consent
            consent_section = CompositionSection()
            consent_section.entry = [FHIR._reference_to(resource)]
            composition.section.append(consent_section)

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

        # Track response for debugging
        content = None
        try:
            # Post it
            response = requests.post(settings.FHIR_URL,
                                     headers={'content-type': 'application/json'},
                                     json=bundle.as_json())
            content = response.content
            response.raise_for_status()

        except Exception as e:
            logger.error("Could not post bundle: {}".format(e), exc_info=True, extra={
                'response': content,
            })

    @staticmethod
    def _obfuscate_email(email):

        # Parts
        parts = email.split('@')
        username = parts[0]
        domain = parts[1]

        # Mask segment of username
        shown_length = int(len(username) / 4 if len(username) > 7 else 1)
        mask_length = len(username) - shown_length * 2

        return '{}{}{}@{}'.format(username[:shown_length],
                                  '*' * mask_length,
                                  username[-shown_length:],
                                  domain)
