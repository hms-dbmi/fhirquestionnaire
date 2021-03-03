from datetime import datetime
from django.http.response import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.template.exceptions import TemplateDoesNotExist
from fhirclient.models.fhirabstractbase import FHIRValidationError
import requests
import hashlib
import json
import re
from dateutil.parser import parse
from django.template import loader
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from fhirclient.models.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhirclient.models.questionnaire import Questionnaire
from fhirclient.models.parameters import Parameters
from fhirclient.models.questionnaireresponse import QuestionnaireResponse
from furl import furl

from dbmi_client.authz import DBMIAdminPermission
from fhirquestionnaire.ppmauth import PPMAdminOrOwnerPermission
from ppmutils.fhir import FHIR
from ppmutils.p2md import P2MD
from ppmutils.ppm import PPM
from dbmi_client.authn import get_jwt_email

from pdf.renderers import render_pdf

import logging
logger = logging.getLogger(__name__)


class ConsentView(APIView):
    """
    View to manage and provide details about a user's consent document
    """
    permission_classes = (PPMAdminOrOwnerPermission, )

    def get(self, request, study, ppm_id, format=None):
        """
        Check if consent PDF exists, create it and store it if not, and then returns the download URL for consent
        """
        # Check for the need arguments
        if not study or not ppm_id:
            return Response('study and ppm_id are required', status=status.HTTP_400_BAD_REQUEST)

        # Check permissions.
        self.check_object_permissions(request, ppm_id)

        try:
            # Check patient
            if not FHIR.query_patient(patient=ppm_id):
                return Response(f'Participant {ppm_id} does not exist', status=status.HTTP_404_NOT_FOUND)

            # Check FHIR
            if not FHIR.get_consent_document_reference(patient=ppm_id, study=study, flatten_return=True):

                # Save it
                ConsentView.create_consent_document_reference(request=request, study=study, ppm_id=ppm_id)

            return Response(P2MD.get_consent_url(study=study, ppm_id=ppm_id))

        except Exception as e:
            logger.exception("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': study,
            })

        # Default to an error response
        return Response('An unexpected error occurred, please contact support',
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, study, ppm_id=None, format=None):
        """
        Check if consent PDF exists, create it and store it if not, and then returns the download URL for consent
        """
        # Check for the need arguments
        if not study:
            return Response('ppm_id is required', status=status.HTTP_400_BAD_REQUEST)

        # Check permissions.
        self.check_object_permissions(request, ppm_id)

        try:
            # Check patient
            if not FHIR.query_patient(patient=ppm_id):
                return Response(f'Participant {ppm_id} does not exist', status=status.HTTP_404_NOT_FOUND)

            # Check if we should overwrite
            overwrite = request.data.get('overwrite', request.GET.get('overwrite', False))

            # Get their current consent Document if any
            document_reference = FHIR.get_consent_document_reference(patient=ppm_id, study=study, flatten_return=True)

            # Check FHIR
            if not document_reference or overwrite:

                # Remove currently PDF
                if document_reference and overwrite:
                    logger.debug(f'PPM/{study}/Patient/{ppm_id} has rendered PDF but will overwrite with a new'
                                 f' render: DocumentReference/{document_reference["id"]}')
                    if not ConsentView.delete_consent_document_reference(request, ppm_id=ppm_id, study=study,
                                                                         document_reference=document_reference):
                        logger.error(f'PPM/{study}/Patient/{ppm_id}: Could not fully remove consent render: '
                                     f'DocumentReference/{document_reference["id"]}')

                # Save it
                ConsentView.create_consent_document_reference(request=request, study=study, ppm_id=ppm_id)

                return Response(P2MD.get_consent_url(study=study, ppm_id=ppm_id), status=status.HTTP_201_CREATED)

            else:
                logger.debug(f'PPM/{study}/Patient/{ppm_id} already has consent PDF:'
                             f' DocumentReference/{document_reference["id"]}')
                return Response(P2MD.get_consent_url(study=study, ppm_id=ppm_id), status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': study,
            })

        # Default to an error response
        return Response('An unexpected error occurred, please contact support',
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def delete_consent_document_reference(request, study, ppm_id, document_reference=None):
        """
        Deletes the existing consent PDF and all FHIR references to it
        :param request: The current HttpRequest
        :param study: The PPM study this consent was in reference to
        :param ppm_id: The PPM ID for the person to have their consent PDF deleted
        :param document_reference: The optional DocumentReference object if already fetched
        :return: Whether the deletion succeeded or not
        """
        try:
            if not document_reference:
                document_reference = FHIR.get_consent_document_reference(patient=ppm_id, study=study,
                                                                         flatten_return=True)

            # Get their consent composition
            composition = FHIR.get_consent_composition(patient=ppm_id, study=study)
            if not composition:
                compositions = FHIR.query_consent_compositions(patient=ppm_id)
                if not compositions:
                    logger.error(f'PPM/{study}/{ppm_id}: No consent compositions')
                    return False

                elif len(compositions) > 1:
                    logger.error(f'PPM/{study}/{ppm_id}: Too many generic consent '
                                 f'compositions: {[r["resource"]["id"] for r in compositions]}')
                    return False

                else:
                    composition = compositions[0]

            # Update it
            if FHIR.update_consent_composition(patient=ppm_id, study=study, composition=composition):

                # Delete the DocumentReference
                if P2MD.delete_consent(request, study=study, ppm_id=ppm_id,
                                       document_reference_id=document_reference['id']):
                    return True

            # Must have failed
            logger.error(f'PPM/{study}/{ppm_id}: Consent DocumentReference could not be deleted: '
                         f'DocumentReference/{document_reference["id"]}')

        except Exception as e:
            logger.exception("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': study,
            })
        return False

    @staticmethod
    def create_consent_document_reference(request, study, ppm_id=None):
        """
        Accepts the context of a participant's request and renders their signed and accepted consent
        as a PDF and then sends the PDF details to P2MD to create a file location, and finally uploads
        the contents of the file to the datalake for storage.
        :param request: The current request
        :type request: HttpRequest
        :param study: The study for which the consent was signed
        :type study: str
        :param ppm_id: The participant ID for which the consent render is being generated
        :type ppm_id: str
        """
        # Get the participant ID if needed
        if not ppm_id:
            ppm_id = FHIR.query_patient_id(get_jwt_email(request=request, verify=False))

        # Pull their record
        bundle = FHIR.query_participant(patient=ppm_id, flatten_return=True)

        # Get study title
        study_title = PPM.Study.title(study)

        # Check for study-specific PDF
        try:
            template_name = f"consent/pdf/{PPM.Study.get(study).value}.html"
            loader.get_template(template_name)
        except TemplateDoesNotExist:
            template_name = 'consent/pdf/consent.html'

        # Submit consent PDF
        logger.debug(f"PPM/{study}: Rendering consent with template: {template_name}")
        response = render_pdf(f'People-Powered Medicine {study_title} Consent', request, template_name,
                              context=bundle.get('composition'), options={})

        # Hash the content
        hash = hashlib.md5(response.content).hexdigest()
        size = len(response.content)

        # Create the file through P2MD
        uuid, upload_data = P2MD.create_consent_file(request, study, ppm_id, hash, size)

        # Pull the needed bits to upload the PDF
        location = upload_data['locationid']
        post = upload_data['post']

        # Set the files dictionary
        files = {'file': response.content}

        # Now that we have the file locally, send it to S3
        response = requests.post(post['url'], data=post['fields'], files=files)
        response.raise_for_status()

        # Set request data
        P2MD.uploaded_consent(request, study, ppm_id, uuid, location)

        return True


class ConsentsView(APIView):
    """
    View to manage and provide details about a study's consent documents
    """
    permission_classes = (DBMIAdminPermission, )

    def get(self, request, study, format=None):
        """
        Return participants list with consent URLs
        """
        # Check for the need arguments
        if not study:
            return Response('study is required', status=status.HTTP_400_BAD_REQUEST)

        # Check study
        try:
            ppm_study = PPM.Study.enum(study)
        except ValueError as e:
            logger.exception('Invalid study identifier: {}'.format(e), exc_info=True, extra={
                'request': request, 'study': study,
            })
            return Response(f'{study} is not a valid PPM study', status=status.HTTP_404_NOT_FOUND)

        # Check permissions.
        self.check_permissions(request)

        try:
            # Get optional parameters
            ppm_ids = request.GET.get('ppm_ids').split(',') if request.data.get('ppm_ids', False) else None

            # Build response object details consents
            response = []

            # Get participants for study
            participants = FHIR.query_participants(studies=[study])
            for participant in participants:

                # Pull their details
                ppm_id = participant['ppm_id']
                logger.debug(f'{study}/Patient/{ppm_id}: Checking consent render')

                # Toss out if not consented
                if PPM.Enrollment.enum(participant['enrollment']) is PPM.Enrollment.Registered:
                    continue

                # If filtered, toss out
                if ppm_ids and ppm_id not in ppm_ids:
                    logger.debug(f'{study}/Patient/{ppm_id}: Filtered out')
                    continue

                # Check consent
                document_reference = FHIR.get_consent_document_reference(patient=ppm_id,
                                                                         study=study,
                                                                         flatten_return=True)
                # Add the URL
                response.append({
                    'ppm_id': ppm_id,
                    'download_url': P2MD.get_consent_url(study=study, ppm_id=ppm_id) if document_reference else None,
                    'url': document_reference['url'] if document_reference else None,
                    'enrollment': participant['enrollment'],
                    'created': document_reference.get('timestamp') if document_reference else None,
                })

            return Response(response)

        except Exception as e:
            logger.exception("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': study,
            })

        # Default to an error response
        return Response('An unexpected error occurred, please contact support',
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, study, format=None):
        """
        Check if consent PDF exists, create it and store it if not, and then returns the download URL for consent
        """
        # Check for the need arguments
        if not study:
            return Response('study is required', status=status.HTTP_400_BAD_REQUEST)

        # Check study
        try:
            study = PPM.Study.get(study).value
        except ValueError as e:
            logger.exception('Invalid study identifier: {}'.format(e), exc_info=True, extra={
                'request': request, 'study': study,
            })
            return Response(f'{study} is not a valid PPM study', status=status.HTTP_404_NOT_FOUND)

        # Check permissions.
        self.check_permissions(request)

        try:
            # Build response object detailing operations
            response = []

            # Check if we should overwrite
            overwrite = request.data.get('overwrite', request.GET.get('overwrite', False))
            ppm_ids = request.data.get('ppm_ids').split(',') if request.data.get('ppm_ids', False) else None

            # Get participants for study
            participants = FHIR.query_participants(studies=[study])
            for participant in participants:

                # Pull their details
                ppm_id = participant['ppm_id']
                logger.debug(f'{study}/Patient/{ppm_id}: Checking consent render')

                # Toss out if not consented
                if PPM.Enrollment.enum(participant['enrollment']) is PPM.Enrollment.Registered:
                    continue

                # If filtered, toss out
                if ppm_ids and ppm_id not in ppm_ids:
                    logger.debug(f'{study}/Patient/{ppm_id}: Filtered out')
                    continue

                # Check consents
                document_reference = FHIR.get_consent_document_reference(patient=ppm_id,
                                                                         study=study,
                                                                         flatten_return=True)

                # Check state of consent
                if not document_reference or overwrite:

                    # Remove currently PDF
                    if document_reference and overwrite:
                        logger.debug(f'PPM/{study}/Patient/{ppm_id} has rendered PDF but will overwrite with a new'
                                     f' render: DocumentReference/{document_reference["id"]}')
                        if not ConsentView.delete_consent_document_reference(request, ppm_id=ppm_id, study=study,
                                                                             document_reference=document_reference):
                            logger.error(f'PPM/{study}/Patient/{ppm_id} could not overwrite consent render with a new'
                                         f' render: DocumentReference/{document_reference["id"]}')
                            continue

                    # Create their consent
                    logger.debug(f'{study}/Patient/{ppm_id}: Generating consent...')
                    ConsentView.create_consent_document_reference(request=request, study=study, ppm_id=ppm_id)

                    # Add the URL
                    response.append({
                        'ppm_id': ppm_id,
                        'download_url': P2MD.get_consent_url(study=study, ppm_id=ppm_id),
                        'created': datetime.now().isoformat(),
                        'enrollment': participant['enrollment'],
                    })
                else:
                    logger.debug(f'PPM/{study}/Patient/{ppm_id} already has consent PDF:'
                                 f' DocumentReference/{document_reference["id"]}')

            return Response(response)

        except Exception as e:
            logger.exception("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': study,
            })

        # Default to an error response
        return Response('An unexpected error occurred, please contact support',
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class QualtricsView(APIView):
    """
    View to manage Qualtrics survey/FHIR Questionnaire resources
    """
    permission_classes = (DBMIAdminPermission, )

    class QualtricsConversionError(Exception):
        pass

    def get(self, request, format=None, *args, **kwargs):
        """
        Returns a listing of questionnaires or a specific
        questionnaire if requested.
        """
        # Check for optional arguments
        questionnaire_id = request.GET.get("questionnaire_id")
        survey_id = request.GET.get("survey_id")

        # Check for questionnaire ID
        if questionnaire_id:

            # Try to fetch it
            questionnaire = FHIR.get_questionnaire(
                questionnaire_id=questionnaire_id,
                flatten_return=False
            )

            # Return it or 404
            if questionnaire:
                return Response(questionnaire)
            else:

                # Attempt the search by identifier
                questionnaires = FHIR._query_resources(
                    "Questionnaire",
                    {
                        "identifier": f"{FHIR.qualtrics_survey_identifier_system}|{questionnaire_id}"
                    }
                )

                # Return them
                if questionnaires:
                    return Response(questionnaires)
                else:
                    raise Http404

        elif survey_id:

            # Fetch them all
            questionnaires = FHIR._query_resources(
                "Questionnaire",
                {
                    "identifier": f"{FHIR.qualtrics_survey_identifier_system}|{survey_id}"
                }
            )

            # Return them
            if questionnaires:
                return Response(questionnaires)
            else:
                raise Http404

        else:

            # Fetch them all
            questionnaires = FHIR._query_resources(
                "Questionnaire",
                {
                    "identifier": f"{FHIR.qualtrics_survey_identifier_system}|"
                }
            )

            # Return them
            if questionnaires:
                return Response(questionnaires)
            else:
                raise Http404

    def post(self, request, questionnaire_id=None, format=None, *args, **kwargs):
        """
        Creates A FHIR Questionnaire from the passed data
        """
        if questionnaire_id:
            return HttpResponseBadRequest()

        try:
            # Get needed data
            questionnaire_id = request.data["questionnaire_id"]
            survey_id = request.data["survey_id"]
            survey = request.data["survey"]
        except Exception as e:
            return HttpResponseBadRequest()

        try:
            # Load the survey
            survey = json.loads(survey.file.read().decode())
        except Exception as e:
            logger.debug(f"API/Qualtrics/POST: Invalid survey file: {e}", exc_info=True)
            return HttpResponseBadRequest()

        try:
            # Convert it
            questionnaire = QualtricsView.questionnaire(
                survey, survey_id, questionnaire_id,
            )

            # Submit it
            return QualtricsView.questionnaire_transaction(
                questionnaire
            )

        except FHIRValidationError as e:
            logger.exception(
                "API/Qualtrics: Validate questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )
            return HttpResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except QualtricsView.QualtricsConversionError as e:
            logger.exception(
                "API/Qualtrics: Convert survey to questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )
            return HttpResponseBadRequest()

        except Exception as e:
            logger.exception(
                "API/Qualtrics: Create Questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )
            return HttpResponseServerError()

    def put(self, request, questionnaire_id=None, format=None, *args, **kwargs):
        """
        Creates A FHIR Questionnaire from the passed data
        """
        if not questionnaire_id:
            return HttpResponseBadRequest()

        try:
            # Load the survey
            survey_id = request.data["survey_id"]
            survey = request.data["survey"]
        except Exception as e:
            return HttpResponseBadRequest()

        try:
            # Load the survey
            survey = json.loads(survey.file.read().decode())
        except Exception as e:
            logger.debug(f"API/Qualtrics/POST: Invalid survey file: {e}", exc_info=True)
            return HttpResponseBadRequest()

        try:
            # Convert it
            questionnaire = QualtricsView.questionnaire(
                survey, survey_id, questionnaire_id,
            )

            # Submit it
            return QualtricsView.questionnaire_transaction(
                questionnaire, questionnaire_id
            )

        except FHIRValidationError as e:
            logger.exception(
                "API/Qualtrics: Validate questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )
            return HttpResponseServerError()

        except QualtricsView.QualtricsConversionError as e:
            logger.exception(
                "API/Qualtrics: Convert survey to questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )
            return HttpResponseBadRequest()

        except Exception as e:
            logger.exception(
                "API/Qualtrics: Create Questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )
            return HttpResponseServerError()

    def patch(self, request, questionnaire_id=None, format=None, *args, **kwargs):
        """
        Updates A FHIR Questionnaire from the passed data
        """
        # This is operationally the same as a PUT-to-update
        return self.put(request, questionnaire_id, format, *args, **kwargs)

    @classmethod
    def questionnaire_transaction(cls, questionnaire, questionnaire_id=None):
        """
        Accepts a Questionnaire object and builds the transaction to be used
        to perform the needed operation in FHIR. Operations can be POST, PUT,
        and DELETE. An error will be raised if an incomptible combination
        if resource ID and operation is passed (e.g. ID and POST, or no ID
        and PUT)

        :param questionnaire: The Questionnaire object to be persisted
        :type questionnaire: dict
        :param questionnaire_id: The ID to use for new Questionnaire, defaults to None
        :type questionnaire_id: str, optional
        :return: The response to be returned to caller
        :rtype: HttpResponse
        """
        # Check for a version matching the created one
        version = questionnaire['version']
        query = {
            "identifier": f"{FHIR.qualtrics_survey_version_identifier_system}|{version}"
        }
        if questionnaire_id:
            query["_id"] = questionnaire_id

        questionnaires = FHIR._query_resources("Questionnaire", query)
        if questionnaires:

            # No need to recreate it
            logger.debug(f"API/Qualtrics: Questionnaire already exists for survey version {version}")
            return HttpResponse(status=status.HTTP_204_NO_CONTENT)

        # Use the FHIR client lib to validate our resource.
        questionnaire = Questionnaire(questionnaire)
        questionnaire_request = BundleEntryRequest(
            {
                "url": f"Questionnaire/{questionnaire_id}" if questionnaire_id else "Questionnaire",
                "method": "PUT" if questionnaire_id else "POST",
            }
        )
        questionnaire_entry = BundleEntry()
        questionnaire_entry.resource = questionnaire
        questionnaire_entry.request = questionnaire_request

        # Validate it.
        bundle = Bundle()
        bundle.entry = [questionnaire_entry]
        bundle.type = "transaction"

        # Create the organization
        response = requests.post(PPM.fhir_url(), json=bundle.as_json())
        logger.debug("Response: {}".format(response.status_code))
        response.raise_for_status()

        return Response(response.json())

    @classmethod
    def get_survey_questionnaire(cls, survey_id, version=None):
        """
        Checks the FHIR server for a Questionnaire resource for the
        passed study and version.

        :param survey_id: The survey ID for which the Questionnaire was created
        :type survey_id: str
        :param version: The hashed version of the Questionnaire, defaults to None
        :type version: str, optional
        :yield: Returns the Questionnaire, if it exists
        :rtype: dict
        """
        pass

    @classmethod
    def questionnaire(cls, survey, survey_id, questionnaire_id=None):
        """
        Accepts a Qualtrics survey definition (QSF) and creates a FHIR
        Questionnaire resource from it. Does not support all of Qualtrics
        functionality and will fail where question-types or other unsupported
        features are encountered.add()

        :param survey: The Qualtrics survey object
        :type survey: dict
        :param survey_id: The ID of the survey in Qualtrics (may differ from ID on QSF)
        :type survey_id: str
        :param questionnaire_id: The ID to assign to the Questionnaire, defaults to None
        :type questionnaire_id: str, optional
        """
        try:
            # Extract the items
            items = [i for i in cls.questionnaire_items(survey_id, survey)]

            # Hash the questions and flow of the survey to track version of the survey
            version = hashlib.md5(json.dumps(items).encode()).hexdigest()

            # Build the resource
            data = {
                "resourceType": "Questionnaire",
                "meta": {"lastUpdated": datetime.now().isoformat()},
                "identifier": [
                    {
                        "system": FHIR.qualtrics_survey_identifier_system,
                        "value": survey_id,
                    },
                    {
                        "system": FHIR.qualtrics_survey_version_identifier_system,
                        "value": version,
                    },
                    {
                        "system": FHIR.qualtrics_survey_questionnaire_identifier_system,
                        "value": questionnaire_id,
                    },
                ],
                "version": version,
                "name": survey_id,
                "title": survey["SurveyEntry"]["SurveyName"],
                "status": "active" if survey["SurveyEntry"]["SurveyStatus"] == "Active" else "draft",
                "approvalDate": parse(survey["SurveyEntry"]["SurveyCreationDate"]).isoformat(),
                "date": parse(survey["SurveyEntry"]["LastModified"]).isoformat(),
                "extension": [
                    {
                        "url": "https://p2m2.dbmi.hms.harvard.edu/fhir/StructureDefinition/qualtrics-survey",
                        "valueString": survey_id,
                    }
                ],
                "item": items,
            }

            # If survey start date, add it
            if survey["SurveyEntry"].get("SurveyStartDate") and \
            survey["SurveyEntry"]["SurveyStartDate"] != "0000-00-00 00:00:00":

                data["effectivePeriod"] = {
                    "start": parse(survey["SurveyEntry"]["SurveyStartDate"]).isoformat()
                }

            # If expiration, add it
            if survey["SurveyEntry"].get("SurveyExpirationDate") and \
                survey["SurveyEntry"]["SurveyStartDate"] != "0000-00-00 00:00:00":

                data["effectivePeriod"]["end"] = parse(survey["SurveyEntry"]["SurveyExpirationDate"]).isoformat()

                # If after expiration, set status
                if parse(survey["SurveyEntry"]["SurveyExpirationDate"]) < datetime.now():
                    data["status"] = "retired"

            return data

        except Exception as e:
            logger.exception(f"Qualtrics Error: {e}", exc_info=True)
            raise QualtricsView.QualtricsConversionError

    @classmethod
    def questionnaire_items(cls, survey_id, survey):
        """
        Returns a generator of QuestionnaireItem resources
        to be added to the Questionnaire. This will determine
        the type of QuestionnaireItem needed and yield it
        accordingly for inclusion into the Questionnaire.

        :param survey_id: The Qualtrics survey identifier
        :type survey_id: str
        :param survey: The Qualtrics survey object
        :type survey: dict
        :raises Exception: Raises exception if block is an unhandled type
        :return: The FHIR QuestionnaireItem generator
        :rtype: generator
        """
        # Flow sets order of blocks, blocks set order of questions
        flows = [
            f["ID"] for f in
            next(e["Payload"]["Flow"] for e in
                 survey["SurveyElements"]
                 if e.get("Element") == "FL")
            if f["Type"] in ["Block", "Standard"]
            ]
        # Check which type of block spec (list or dict)
        _blocks = next(
            e["Payload"] for e in survey["SurveyElements"]
            if e.get("Element") == "BL"
        )
        if type(_blocks) is list:
            blocks = {
                f: next(b for b in _blocks
                    if b["Type"] in ["Default", "Standard"]
                    and b["ID"] == f)
                for f in flows
                }
        elif type(_blocks) is dict:
            blocks = {
                f: next(b for b in _blocks.values()
                    if b["Type"] in ["Default", "Standard"]
                    and b["ID"] == f)
                for f in flows
                }
        else:
            logger.error(f"PPM/Qualtrics: Invalid Qualtrics block spec")

        questions = {
            f: [e["QuestionID"] for e
                in blocks[f]["BlockElements"]
                if e["Type"] == "Question"] for f in flows
        }

        # Walk through elements
        for block_id, block in blocks.items():

            # Check if we need this grouped
            if block.get("Options", {}).get("Looping", False):

                # Build the group
                group = cls.questionnaire_group(survey_id, survey, block_id, block)

                yield group

            else:
                # Yield each question individually
                for question_id in questions[block_id]:

                    # Look up the question
                    question = next(
                        e["Payload"] for e in
                        survey["SurveyElements"]
                        if e["PrimaryAttribute"] == question_id
                        )

                    # Create it
                    item = cls.questionnaire_item(
                        survey_id, survey, question_id, question
                    )

                    yield item

    @classmethod
    def questionnaire_group(cls, survey_id, survey, block_id, block):
        """
        Returns a FHIR resource for a QuestionnaireItem parsed from
        a block of Qualtrics survey's questions. This should be used
        when a set of questions should be grouped for the purpose of
        conditional showing, repeating/looping.

        :param survey_id: The Qualtrics survey identifier
        :type survey_id: str
        :param survey: The Qualtrics survey object
        :type survey: dict
        :param block_id: The Qualtrics survey block identifier
        :type block_id: str
        :param block: The Qualtrics survey block object
        :type block: dict
        :raises Exception: Raises exception if block is an unhandled type
        :return: The FHIR QuestionnaireItem resource
        :rtype: dict
        """
        try:
            # Set root link ID
            link_id = f"group-{block_id.replace('BL_', '')}"

            # Get all questions in this block
            question_ids = [b["QuestionID"] for b in block["BlockElements"]]

            # Prepare group item
            item = {
                "linkId": link_id,
                "type": "group",
                "repeats": True if block.get("Options", {}).get("Looping", False) else False,
                "item": [
                    cls.questionnaire_item(
                        survey_id,
                        survey,
                        question_id,
                        next(e["Payload"] for e in survey["SurveyElements"] if e["PrimaryAttribute"] == question_id)
                    )
                    for question_id in question_ids
                ],
            }

            return item

        except Exception as e:
            logger.exception(
                f"PPM/FHIR: Error processing block {block_id}: {e}",
                exc_info=True,
                extra={
                    "survey_id": survey_id,
                    "block_id": block_id,
                    "block": block,
                }
            )
            raise e

    @classmethod
    def questionnaire_item(cls, survey_id, survey, question_id, question):
        """
        Returns a FHIR resource for a QuestionnaireItem parsed from
        the Qualtrics survey's question

        :param survey_id: The Qualtrics survey identifier
        :type survey_id: str
        :param survey: The Qualtrics survey object
        :type survey: dict
        :param qid: The Qualtrics survey question identifier
        :type qid: str
        :param question: The Qualtrics survey question object
        :type question: dict
        :raises Exception: Raises exception if question is an unhandled type
        :return: The FHIR QuestionnaireItem resource
        :rtype: dict
        """
        # Set root link ID
        link_id = f"question-{question_id.replace('QID', '')}"

        # Strip text of HTML and other characters
        text = re.sub("<[^<]+?>", "", question["QuestionText"]).strip().replace("\n", "").replace("\r", "")

        # Determine if required
        required = question["Validation"].get("Settings", {}).get("ForceResponse", False) == "ON"

        # Get question text
        item = {
            "linkId": link_id,
            "text": text,
            "required": required,
        }

        try:
            # Check for conditional enabling
            if question.get("DisplayLogic", False):

                # Intialize enableWhen item
                enable_whens = []

                # We are only processing BooleanExpressions
                if question["DisplayLogic"]["Type"] != "BooleanExpression":
                    logger.error(
                        f"PPM/Questionnaire: Unhandled DisplayLogic "
                        f"type {survey_id}/{question_id}: {question['DisplayLogic']}"
                    )
                    raise ValueError(f"Failed to process survey {survey['id']}")

                # Iterate conditions for display of this question
                # INFO: Currently only selected choice conditions are supported
                statement = question["DisplayLogic"]["0"]["0"]

                # Get the question ID it depends on
                conditional_qid = statement["QuestionID"]

                # Fetch the value of the answer
                components = furl(statement["LeftOperand"]).path.segments

                # Check type
                if components[0] == "SelectableChoice":

                    # Get answer index and value
                    index = components[1]

                    # Find question
                    conditional_question = next(
                        e for e in survey["SurveyElements"]
                        if e["PrimaryAttribute"] == conditional_qid
                    )

                    # Get answer value
                    conditional_value = next(
                        c["Display"] for i, c in
                        conditional_question["Payload"]["Choices"].items()
                        if i == index
                    )

                    # Add it
                    enable_whens.append({
                        "question": f"question-{conditional_qid.replace('QID', '')}",
                        "answerString": conditional_value,
                    })

                else:
                    logger.error(
                        f"PPM/Questionnaire: Unhandled DisplayLogic expression"
                        f"type {survey_id}/{question_id}: {components}"
                    )
                    raise ValueError(f"Failed to process survey {survey['id']}")

                # Add enableWhen's if we've got them
                if enable_whens:
                    item["enableWhen"] = enable_whens

        except Exception as e:
            logger.exception(
                f"PPM/FHIR: Error processing display logic: {e}",
                exc_info=True,
                extra={
                    "survey_id": survey_id,
                    "question_id": question_id,
                }
            )
            raise e

        # Check type
        question_type = question["QuestionType"]
        selector = question["Selector"]
        sub_selector = question.get("SubSelector")

        try:
            # Text (single line)
            if question_type == "TE" and selector == "SL":

                # Set type
                item["type"] = "string"

            # Text (multiple line)
            elif question_type == "TE" and selector == "ESTB":

                # Set type
                item["type"] = "text"

            # Text (multiple line)
            elif question_type == "TE" and selector == "ML":

                # Set type
                item["type"] = "text"

            # Multiple choice (single answer)
            elif question_type == "MC" and selector == "SAVR":

                # Set type
                item["type"] = "choice"

                # Set choices
                item["option"] = [{"valueString": c["Display"]} for k, c in question["Choices"].items()]

            # Multiple choice (multiple answer)
            elif question_type == "MC" and selector == "MAVR":

                # Set type
                item["type"] = "choice"
                item["repeats"] = True

                # Set choices
                item["option"] = [{"valueString": c["Display"]} for k, c in question["Choices"].items()]

            # Matrix (single answer)
            elif (
                question_type == "Matrix"
                and selector == "Likert"
                and sub_selector == "SingleAnswer"
            ):

                # Add this as a grouped set of multiple choice, single answer questions
                item["type"] = "group"

                # Preselect choices
                choices = [{"valueString": c["Display"]} for k, c in question["Answers"].items()]

                # Set subitems
                item["item"] = [
                    {
                        "linkId": f"{link_id}-{k}",
                        "text": s["Display"],
                        "type": "choice",
                        "option": choices,
                        "required": required,
                    }
                    for k, s in question["Choices"].items()
                ]

            # Matrix (multiple answer)
            elif (
                question_type == "Matrix"
                and selector == "Likert"
                and sub_selector == "MultipleAnswer"
            ):

                # Add this as a grouped set of multiple choice, single answer questions
                item["type"] = "group"
                item["repeats"] = True

                # Preselect choices
                choices = [{"valueString": c["Display"]} for k, c in question["Answers"].items()]

                # Set subitems
                item["item"] = [
                    {
                        "linkId": f"{link_id}-{k}",
                        "text": s["Display"],
                        "type": "choice",
                        "option": choices,
                        "required": required,
                    }
                    for k, s in question["Choices"].items()
                ]

            # Slider (integer answer)
            elif question_type == "Slider" and selector == "HBAR":

                # Set type
                item["type"] = "integer"

            # Slider (integer answer)
            elif question_type == "Slider" and selector == "HSLIDER":

                # Set type
                item["type"] = "decimal"

            # Hot spot (multiple choice, multiple answer)
            elif question_type == "HotSpot" and selector == "OnOff":

                # Set type
                item["type"] = "choice"
                item["repeats"] = True

                # Set choices
                item["option"] = [{"valueString": c["Display"]} for k, c in question["Choices"].items()]

            # Drill down
            elif question_type == "DD" and selector == "DL":

                # Set type
                item["type"] = "choice"
                item["repeats"] = False

                # Set choices
                item["option"] = [{"valueString": c["Display"]} for k, c in question["Answers"].items()]

            # Descriptive text
            elif question_type == "DB":

                # Set type
                item["type"] = "display"

            # Descriptive graphics
            elif question_type == "GB":

                # Set type
                item["type"] = "display"

            # Multiple, matrix-style questions
            elif question_type == "SBS":

                # Put them in a group
                item["type"] = "group"
                item["text"] = question["QuestionText"]
                item["item"] = []

                # Add this as multiple grouped sets of multiple choice, single answer questions
                for k, additional_question in question["AdditionalQuestions"].items():

                    # Add another display for the subquestion
                    sub_item = {
                        "linkId": f"{link_id}-{k}",
                        "type": "group",
                        "text": additional_question["QuestionText"],
                        "item": [],
                    }

                    # Get choices
                    questions = {k: c["Display"] for k, c in additional_question["Choices"].items()}

                    # Preselect choices
                    answers = [{"valueString": c["Display"]} for k, c in additional_question["Answers"].items()]

                    # Add a question per choice
                    for sub_k, sub_question in questions.items():

                        # Remove prefixes, if set
                        sub_question = re.sub(r"^[\d]{1,4}\.\s", "", sub_question)

                        # Set subitems
                        sub_item["item"].append({
                            "linkId": f"{link_id}-{k}-{sub_k}",
                            "text": sub_question,
                            "type": "choice",
                            "option": answers,
                            "required": required,
                            })

                    item["item"].append(sub_item)

            else:
                logger.error(
                    "PPM/Questionnaire: Unhandled survey question" f" type {survey_id}/{question_id}: {question_type}"
                )
                raise ValueError(f"Failed to process survey {survey_id}")
        except Exception as e:
            logger.exception(
                f"PPM/FHIR: Error processing questionnaire item: {e}",
                exc_info=True,
                extra={
                    "survey_id": survey_id,
                    "question_id": question_id,
                    "question": question,
                }
            )
            raise e

        return item

class QuestionnaireView(APIView):
    """
    View to manage FHIR Questionnaire resources
    """
    permission_classes = (DBMIAdminPermission, )

    def get(self, request, questionnaire_id=None, format=None):
        """
        Returns a listing of questionnaires or a specific
        questionnaire if requested.
        """
        # Check for questionnaire ID
        if questionnaire_id:

            # Try to fetch it
            questionnaire = FHIR.get_questionnaire(
                questionnaire_id=questionnaire_id,
                flatten_return=False
            )

            # Return it or 404
            if questionnaire:
                return Response(questionnaire)
            else:
                raise Http404

        else:

            # Fetch them all
            questionnaires = FHIR._query_resources("Questionnaire")

            # Return them
            if questionnaires:
                return Response(questionnaires)
            else:
                raise Http404

    def post(self, request, format=None):
        """
        Creates A FHIR Questionnaire from the passed data
        """
        # Use the FHIR client lib to validate our resource.
        questionnaire = Questionnaire(request.data)
        questionnaire_request = BundleEntryRequest(
            {
                "url": f"Questionnaire",
                "method": "POST",
            }
        )
        questionnaire_entry = BundleEntry()
        questionnaire_entry.resource = questionnaire
        questionnaire_entry.request = questionnaire_request

        # Validate it.
        bundle = Bundle()
        bundle.entry = [questionnaire_entry]
        bundle.type = "transaction"

        try:
            # Create the organization
            response = requests.post(PPM.fhir_url(), json=bundle.as_json())
            logger.debug("Response: {}".format(response.status_code))
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.exception(
                "API/Questionnaire: Create Questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )

    def put(self, request, questionnaire_id, format=None):
        """
        Creates or updates A FHIR Questionnaire from the passed data
        """
        # Use the FHIR client lib to validate our resource.
        questionnaire = Questionnaire(request.data)
        questionnaire_request = BundleEntryRequest(
            {
                "url": f"Questionnaire/{questionnaire_id}",
                "method": "PUT",
            }
        )
        questionnaire_entry = BundleEntry()
        questionnaire_entry.resource = questionnaire
        questionnaire_entry.request = questionnaire_request

        # Validate it.
        bundle = Bundle()
        bundle.entry = [questionnaire_entry]
        bundle.type = "transaction"

        try:
            # Create the organization
            response = requests.post(PPM.fhir_url(), json=bundle.as_json())
            logger.debug("Response: {}".format(response.status_code))
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.exception(
                "API/Questionnaire: Update Questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )

    def delete(self, request, questionnaire_id, format=None):
        """
        Deletes A FHIR Questionnaire for the passed ID
        """
        # Use the FHIR client lib to validate our resource.
        questionnaire_request = BundleEntryRequest(
            {
                "url": f"Questionnaire/{questionnaire_id}",
                "method": "DELETE",
            }
        )
        questionnaire_entry = BundleEntry()
        questionnaire_entry.request = questionnaire_request

        # Validate it.
        bundle = Bundle()
        bundle.entry = [questionnaire_entry]
        bundle.type = "transaction"

        try:
            # Create the organization
            response = requests.post(PPM.fhir_url(), json=bundle.as_json())
            logger.debug("Response: {}".format(response.status_code))
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.exception(
                "API/Questionnaire: Delete Questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )

    def patch(request, questionnaire_id, format=None):
        """
        Uses FHIR+json patch to update a resource
        """

        # Base 64 encode the patch
        parameters = Parameters(request.data)
        questionnaire_request = BundleEntryRequest(
            {
                "url": f"Questionnaire/{questionnaire_id}",
                "method": "PATCH",
            }
        )
        questionnaire_entry = BundleEntry()
        questionnaire_entry.resource = parameters
        questionnaire_entry.request = questionnaire_request

        # Validate it.
        bundle = Bundle()
        bundle.entry = [questionnaire_entry]
        bundle.type = "transaction"

        try:
            # Create the organization
            response = requests.post(PPM.fhir_url(), json=bundle.as_json())
            logger.debug("Response: {}".format(response.status_code))
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.exception(
                "API/Questionnaire: Delete Questionnaire error: {}".format(e),
                exc_info=True,
                extra={
                    "request": request,
                },
            )
