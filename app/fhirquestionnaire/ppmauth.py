from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from ppmutils.fhir import FHIR

from dbmi_client.authz import is_admin

import logging
logger = logging.getLogger(__name__)


def _ppm_id_for_email(request, email):
    """
    This accepts an email associated with a request and returns the ppm_id for that user. This
    will be used to confirm requests by a user are only operating on resources owned by that user.
    :return: str
    """
    # Get the ID
    ppm_id = FHIR.get_ppm_id(email=email)
    if ppm_id:
        return ppm_id
    else:
        # This shouldn't happen but log it either way
        logger.error('PPM ID lookup failed: {}', extra={
            'request': request, 'email': email
        })

        return None


###################################################################
#
# Django Rest Framework (DRF) Custom Authentication/Authorization
#
###################################################################

class PPMAdminOrOwnerPermission(BasePermission):
    """
    Permission check for owner or MANAGE permissions on PPM
    'obj' in this context is the FHIR ID of the Patient to performs ops for
    """
    permission_item = 'PPM'
    message = 'User does not have proper permission on item PPM'

    def has_object_permission(self, request, view, obj):

        # Get the email of the authenticated user
        if not hasattr(request, 'user'):
            logger.warning('No \'user\' attribute on request')
            raise PermissionDenied

        # Check claims first for membership in the admin group
        if is_admin(request, request.user):
            return True

        # Check if owner
        if _ppm_id_for_email(request, request.user) == obj:
            return True

        # Possibly store these elsewhere for records
        logger.info('{} Failed MANAGE or owner permission for PPM'.format(request.user))

        raise PermissionDenied


class PPMOwnerPermission(BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):

        # Get the email
        if not hasattr(request, 'user'):
            logger.warning('No \'user\' attribute on request')
            raise PermissionDenied

        # Check if owner
        if _ppm_id_for_email(request, request.user) == obj:
            return True

        raise PermissionDenied
