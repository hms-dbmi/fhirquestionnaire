import datetime
from urllib.parse import quote

from django.template.loader import render_to_string

from fhirclient.models.patient import Patient
from fhirclient.models.questionnaire import Questionnaire
from fhirclient.models.bundle import Bundle
from ppmutils.ppm import PPM
from ppmutils.fhir import FHIR as PPMFHIR

import logging
logger = logging.getLogger(__name__)


class FHIR:

    # Coding systems for questionnaires
    input_type_system = 'https://peoplepoweredmedicine.org/questionnaire/input/type'
    input_range_system = 'https://peoplepoweredmedicine.org/questionnaire/input/range'

    @staticmethod
    def submit_consent(study, patient_email, form, pdf=None, dry=False):
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
        :param dry: If True, do not persist questionnaire response to store
        :type dry: bool
        :return: Whether the operation succeeded or not
        :rtype: bool
        """

        # Get the exception codes from the form
        data = dict(form)
        codes = data.get('exceptions', [])
        name = data['name']
        signature = data['signature']
        date = data['date']

        # Build a list of resources to create
        resources = []

        # Get the current timestamp
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        # Check if consent has questionnaire
        if PPM.Questionnaire.consent_questionnaire_for_study(study):

            # Get the questionnaire
            questionnaire, patient = FHIR.get_resources(PPM.Questionnaire.consent_questionnaire_for_study(study), patient_email, dry)

            # Map exception codes to linkId
            # TODO: Figure out how to generalize the handling of exceptions per consent
            exception_codes = PPM.Questionnaire.exceptions(PPM.Questionnaire.consent_questionnaire_for_study(study))

            # Build answers
            answers = {linkId: code in codes for linkId, code in exception_codes.items()}

            # Create needed resources
            questionnaire_response = PPMFHIR.Resources.questionnaire_response(questionnaire, patient, date, answers)
            contract = PPMFHIR.Resources.contract(patient, timestamp, name, signature, questionnaire_response)
            exceptions = PPMFHIR.Resources.consent_exceptions(codes)
            consent = PPMFHIR.Resources.consent(patient, timestamp, exceptions)

            resources.extend([questionnaire_response, consent, contract])
        else:

            # Get patient
            patient = Patient(PPMFHIR.get_patient(patient_email))

            # Create needed resources
            contract = PPMFHIR.Resources.contract(patient, timestamp, name, signature)
            consent = PPMFHIR.Resources.consent(patient, timestamp)

            resources.extend([consent, contract])

        # Get the signature HTML
        text = '<div>{}</div>'.format(render_to_string('consent/{}/_consent.html'.format(study)))

        # Generate composition
        composition = PPMFHIR.Resources.composition(patient, timestamp, text, PPM.Study.get(study), [consent, contract])

        # Add it to the resources
        resources.append(composition)

        # Bundle it into a transaction
        bundle = PPMFHIR.Resources.bundle(resources)

        # Save it
        if dry:
            logger.warning('PPM/{}: Dry mode, not persisting responses'.format(study))
        else:
            PPMFHIR.fhir_transaction(bundle.as_json())

    @staticmethod
    def submit_questionnaire(study, patient_email, form, dry=False):
        """
        Accepts the filled out form for the given study and submits the data to FHIR for retaining
        :param study: The study for which the questionnaire was completed
        :type study: str
        :param patient_email: The current user's email
        :type patient_email: str
        :param form: The form filled out for the questionnaire
        :type form: Form
        :param dry: If True, do not persist questionnaire response to store
        :type dry: bool
        :return: Whether the operation succeeded or not
        :rtype: bool
        """
        # Get the questionnaire
        questionnaire, patient = FHIR.get_resources(PPM.Questionnaire.questionnaire_for_study(study), patient_email, dry)

        # Just use now
        date = datetime.datetime.now(datetime.timezone.utc)

        # Build the response
        questionnaire_response = PPMFHIR.Resources.questionnaire_response(questionnaire, patient, date, form)

        # Bundle it into a transaction
        bundle = PPMFHIR.Resources.bundle([questionnaire_response])

        # Save it
        if dry:
            logger.warning('PPM/{}: Dry mode, not persisting responses'.format(study))
        else:
            PPMFHIR.fhir_transaction(bundle.as_json())

    @staticmethod
    def submit_asd_individual(patient_email, forms, dry=False):
        """
        Accepts the filled out form for the given study and submits the data to FHIR for retaining
        :param patient_email: The current user's email
        :type patient_email: str
        :param form: The forms filled out for the questionnaire
        :type form: [Form]
        :param dry: If True, do not persist questionnaire response to store
        :type dry: bool
        :return: Whether the operation succeeded or not
        :rtype: bool
        """

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
            # Check if this is testing/dry
            if not dry:
                logger.error("Patient could not be fetched", exc_info=True, extra={
                    'patient': FHIR.obfuscate_email(patient_email),
                })
                raise FHIR.PatientDoesNotExist
            else:
                patient = FHIR.get_demo_patient(patient_email)

        # Get the current timestamp
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        # Get the exception codes from the form
        individual_form = forms['individual']
        codes = individual_form.get('exceptions', [])
        name = individual_form['name']
        signature = individual_form['signature']
        date = individual_form['date']

        # Map exception codes to linkId
        exception_codes = {
            'question-1': '225098009',
            'question-2': '284036006',
            'question-3': '702475000',
        }

        # Build answers
        answers = {linkId: code in codes for linkId, code in exception_codes.items()}

        # Create needed resources
        quiz_questionnaire_response = PPMFHIR.Resources.questionnaire_response(quiz_questionnaire, patient, date, forms['quiz'])
        questionnaire_response = PPMFHIR.Resources.questionnaire_response(signature_questionnaire, patient, date, answers)
        contract = PPMFHIR.Resources.contract(patient, timestamp, name, signature, questionnaire_response)
        exceptions = PPMFHIR.Resources.consent_exceptions(codes)
        consent = PPMFHIR.Resources.consent(patient, timestamp, exceptions)

        # Get the signature HTML
        text = '<div>{}</div>'.format(render_to_string('consent/asd/_individual_consent.html'))

        # Generate composition
        composition = PPMFHIR.Resources.composition(patient, timestamp, text, PPM.Study.ASD, [consent, contract])

        # Bundle it into a transaction
        bundle = PPMFHIR.Resources.bundle([questionnaire_response, consent, contract, composition, quiz_questionnaire_response])

        # Save it
        PPMFHIR.fhir_transaction(bundle.as_json())

    @staticmethod
    def submit_asd_guardian(patient_email, forms, dry=False):
        """
        Accepts the filled out form for the given study and submits the data to FHIR for retaining
        :param patient_email: The current user's email
        :type patient_email: str
        :param form: The forms filled out for the questionnaire
        :type form: [Form]
        :param dry: If True, do not persist questionnaire response to store
        :type dry: bool
        :return: Whether the operation succeeded or not
        :rtype: bool
        """

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
            # Check if this is testing/dry
            if not dry:
                logger.error("Patient could not be fetched", exc_info=True, extra={
                    'patient': FHIR.obfuscate_email(patient_email),
                })
                raise FHIR.PatientDoesNotExist
            else:
                patient = FHIR.get_demo_patient(patient_email)

        # Process the guardian's resources first

        # Get the current timestamp
        timestamp = datetime.datetime.now(datetime.timezone.utc)

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
        ward_date = ward_form['date']

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
        related_person = PPMFHIR.Resources.related_person(patient, guardian, relationship)

        # Create all questionnaire response resources
        quiz_questionnaire_response = PPMFHIR.Resources.questionnaire_response(quiz_questionnaire, patient, date, quiz,
                                                                   related_person)
        guardian_signature_questionnaire_response = PPMFHIR.Resources.questionnaire_response(guardian_signature_questionnaire,
                                                                                 patient, date, exception_answers,
                                                                                 related_person)
        guardian_explained_questionnaire_response = PPMFHIR.Resources.questionnaire_response(guardian_reason_questionnaire,
                                                                                 patient, date, reason_answers,
                                                                                 related_person)

        # Create contract resources
        signature_contract = PPMFHIR.Resources.related_contract(patient, timestamp, name, related_person, guardian,
                                                    signature, guardian_signature_questionnaire_response)
        explained_contract = PPMFHIR.Resources.related_contract(patient, timestamp, name, related_person, guardian,
                                                    explained_signature, guardian_explained_questionnaire_response)

        # Create the guardian's consent
        exceptions = PPMFHIR.Resources.consent_exceptions(guardian_codes)
        consent = PPMFHIR.Resources.consent(patient, timestamp, exceptions, related_person)

        # Get the signature HTML
        text = '<div>{}</div>'.format(render_to_string('consent/asd/_guardian_consent.html'))

        # Generate composition
        composition = PPMFHIR.Resources.composition(patient, timestamp, text, PPM.Study.ASD, [consent, signature_contract, explained_contract])

        # Map exception codes to linkId
        ward_exception_codes = {
            'question-1': '225098009',
            'question-2': '284036006',
        }

        # Get the ward signature HTML
        ward_text = '<div>{}</div>'.format(render_to_string('consent/asd/_ward_assent.html'))

        # Create participant resources
        ward_exceptions = {linkId: code in ward_codes for linkId, code in ward_exception_codes.items()}
        ward_signature_questionnaire_response = PPMFHIR.Resources.questionnaire_response(ward_signature_questionnaire,
                                                                             patient, date, ward_exceptions)

        # Create the contract and composition
        ward_contract = PPMFHIR.Resources.contract(patient, timestamp, name, ward_signature, ward_signature_questionnaire_response)
        ward_composition = PPMFHIR.Resources.composition(patient, timestamp, ward_text, [ward_contract])

        # Bundle it into a transaction
        bundle = PPMFHIR.Resources.bundle([related_person,
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
        PPMFHIR.fhir_transaction(bundle.as_json())

    @staticmethod
    def get_demo_patient(email):
        """
        Returns an instance of a FHIR Patient using dummy info for testing

        :param email: The email of the testing user
        :type email: str
        :return: Test Patient resource object
        :rtype: Patient
        """
        return Patient(jsondict={
            'id': 'TEST',
            'identifier': [
                {
                    'system': PPMFHIR.patient_email_identifier_system,
                    'value': email
                }
            ]
        })

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
        response = PPMFHIR.fhir_transaction(transaction)

        # Build the objects
        bundle = Bundle(response)

        return bundle

    @staticmethod
    def get_resources(questionnaire_id, patient_email, dry=False):

        # Get the questionnaire
        questionnaire = Questionnaire(PPMFHIR.fhir_read("Questionnaire", questionnaire_id))

        # Search for the patient
        patient = Patient(PPMFHIR.get_patient(patient_email))

        # Check for the patient
        if not dry:
            if not patient:
                logger.error("Patient could not be fetched", exc_info=True, extra={
                    'patient': FHIR.obfuscate_email(patient_email),
                    'questionnaires': questionnaire_id,
                })
                raise FHIR.PatientDoesNotExist()
        else:
            # In dry mode, use a fake patient
            patient = FHIR.get_demo_patient(patient_email)

        return questionnaire, patient

    @staticmethod
    def check_patient(patient_email):
        """
        Checks FHIR for a Patient resource for the given email.

        :param patient_email: The email of the participant to check
        :type patient_email: str
        :raises FHIR.PatientDoesNotExist: If does not exist
        """

        # Search for Patient
        if not PPMFHIR.get_patient(patient_email):
            logger.warning(
                f"PPM/{FHIR.obfuscate_email(patient_email)}: "
                "Patient NOT found"
            )
            raise FHIR.PatientDoesNotExist

    @staticmethod
    def check_consent(study, patient_email):
        """
        Checks FHIR for resources pertaining to a signed consent for this
        specific patient and study.

        :param patient_email: The email of the participant to check
        :type patient_email: str
        :param study: The study for which the consent would be signed
        :type study: str
        :raises FHIR.ConsentAlreadyExists: If exists already
        """

        # Search for the consent composition resource specific to this study
        if PPMFHIR.get_consent_composition(patient_email, study):
            logger.debug(
                f"PPM/{study}/{FHIR.obfuscate_email(patient_email)}: "
                "Consent composition already exists"
            )
            raise FHIR.ConsentAlreadyExists

        return False

    @staticmethod
    def check_response(questionnaire_id, patient_email):
        """
        Checks FHIR for resources pertaining to a response for this
        specific questionnaire.

        :param questionnaire_id: The questionnaire for which the response was made
        :type questionnaire_id: str
        :param patient_email: The email of the participant to check
        :type patient_email: str
        :raises FHIR.QuestionnaireResponseAlreadyExists: If exists already
        """

        # Get the questionnaire
        if PPMFHIR.get_questionnaire_response(patient_email, questionnaire_id):
            logger.warning(
                f"PPM/{FHIR.obfuscate_email(patient_email)}: "
                f"QuestionnaireResponse found for '{questionnaire_id}'"
            )
            raise FHIR.QuestionnaireResponseAlreadyExists
        else:
            logger.debug(
                f"PPM/{FHIR.obfuscate_email(patient_email)}: "
                f"QuestionnaireResponse NOT found for '{questionnaire_id}'"
            )

    class QuestionnaireDoesNotExist(Exception):
        pass

    class PatientDoesNotExist(Exception):
        pass

    class QuestionnaireResponseAlreadyExists(Exception):
        pass

    class ConsentAlreadyExists(Exception):
        pass

    @staticmethod
    def obfuscate_email(email):

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
