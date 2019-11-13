from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ppmutils.fhir import FHIR
from ppmutils.p2md import P2MD

from consent.views import save_consent_pdf

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
                save_consent_pdf(request=request, study=study, ppm_id=ppm_id)

            return Response(P2MD.get_consent_url(study=study, ppm_id=ppm_id))

        except Exception as e:
            logger.exception("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': study,
            })

        # Default to an error response
        return Response('An unexpected error occurred, please contact support',
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, study, ppm_id, format=None):
        """
        Check if consent PDF exists, create it and store it if not, and then returns the download URL for consent
        """
        # Check for the need arguments
        if not study or not ppm_id:
            return Response('ppm_id and uuid are required', status=status.HTTP_400_BAD_REQUEST)

        # Check permissions.
        self.check_object_permissions(request, ppm_id)

        try:
            # Check patient
            if not FHIR.query_patient(patient=ppm_id):
                return Response(f'Participant {ppm_id} does not exist', status=status.HTTP_404_NOT_FOUND)

            # Check if we should overwrite
            overwrite = request.data.get('overwrite', False)

            # Get their current consent Document if any
            document_reference = FHIR.get_consent_document_reference(patient=ppm_id, study=study, flatten_return=True)
            logger.debug(f'{study} - Patient/{ppm_id} found render: DocumentReference/{document_reference["id"]}')

            # Check FHIR
            if not document_reference or overwrite:

                # Remove currently PDF
                if document_reference and overwrite:

                    # TODO: Implement the purge of existing consent DocumentReference
                    logger.debug(f'PPM/{study}/Patient/{ppm_id} has rendered PDF but will overwrite with a new'
                                 f' render: DocumentReference/{document_reference["id"]}')
                    return Response('Removal of old consent renders is not yet implemented', status=status.HTTP_501_NOT_IMPLEMENTED)

                # Save it
                save_consent_pdf(request=request, study=study, ppm_id=ppm_id)

                return Response(P2MD.get_consent_url(study=study, ppm_id=ppm_id), status=status.HTTP_201_CREATED)

            else:
                return Response(P2MD.get_consent_url(study=study, ppm_id=ppm_id), status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': study,
            })

        # Default to an error response
        return Response('An unexpected error occurred, please contact support',
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
