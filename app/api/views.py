from datetime import datetime
from django.template.exceptions import TemplateDoesNotExist
import requests
import hashlib
from django.template import loader
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from dbmi_client.authz import DBMIAdminPermission
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
