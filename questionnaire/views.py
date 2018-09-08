from django.shortcuts import render, reverse, redirect
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import View

from questionnaire.forms import NEERQuestionnaireForm, ASDQuestionnaireForm
from fhirquestionnaire.fhir import FHIR
from pyauth0jwt.auth0authenticate import dbmi_jwt, validate_request

import logging
logger = logging.getLogger(__name__)


class IndexView(View):

    def get(self, request, *args, **kwargs):
        logger.warning('Index view')

        return render_error(request,
                            title='Questionnaire Not Specified',
                            message='A questionnaire must be specified.',
                            support=False)


class ProjectView(View):

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Get the project ID
        project_id = kwargs.get('project_id')
        if not project_id:
            return render_error(request,
                                title='Project Not Specified',
                                message='A project must be specified in order to load the needed consent.',
                                support=False)

        # Redirect them
        if project_id == 'neer':

            return redirect(reverse('questionnaire:neer'))

        elif project_id == 'asd':

            return redirect(reverse('questionnaire:asd'))

        else:
            return render_error(request,
                                title='Invalid Project Specified',
                                message='A valid project must be specified in order to load the needed consent.',
                                support=False)


class NEERView(View):

    questionnaire_id = 'ppm-neer-registration-questionnaire'

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Get the patient email and ensure they exist
        patient_email = validate_request(request).get('email')

        try:
            # Check the current patient
            FHIR.check_patient(patient_email)

            # Check response
            FHIR.check_response(self.questionnaire_id, patient_email)

            # Create the form
            form = NEERQuestionnaireForm(self.questionnaire_id)

            # Prepare the context
            context = {
                'questionnaire_id': self.questionnaire_id,
                'form': form,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/neer.html', context=context)

        except FHIR.PatientDoesNotExist:
            logger.warning('Patient does not exist: {}'.format(patient_email[:3]+'****'+patient_email[-4:]))
            return render_error(request,
                                title='Patient Does Not Exist',
                                message='A FHIR resource does not yet exist for the current user. '
                                        'Please sign into the People-Powered dashboard to '
                                        'create your user.',
                                support=False)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Questionnaire does not exist: {}'.format(self.questionnaire_id))
            return render_error(request,
                                title='Questionnaire Does Not Exist',
                                message='The requested questionnaire does not exist!',
                                support=False)

        except FHIR.QuestionnaireResponseAlreadyExists:
            logger.warning('Questionnaire already finished')
            return render_error(request,
                                title='Questionnaire Already Completed',
                                message='You have already filled out and submitted this '
                                        'questionnaire.',
                                support=False)

        except Exception as e:
            logger.error("Error while rendering questionnaire: {}".format(e), exc_info=True, extra={
                'request': request, 'project': 'neer',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):

        # Get the patient email
        patient_email = validate_request(request).get('email')

        # create a form instance and populate it with data from the request:
        form = NEERQuestionnaireForm(self.questionnaire_id, request.POST)

        # check whether it's valid:
        if not form.is_valid():
            # Get the return URL

            context = {
                'form': form,
                'questionnaire_id': self.questionnaire_id,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/neer.html', context=context)

        # Process the form
        try:
            FHIR.submit_neer_questionnaire(patient_email, form.cleaned_data)

            # Get the return URL
            context = {
                'questionnaire_id': self.questionnaire_id,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/success.html', context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Questionnaire does not exist: {}'.format(self.questionnaire_id))
            return render_error(request,
                                title='Questionnaire Does Not Exist',
                                message='The requested questionnaire does not exist!',
                                support=False)

        except FHIR.PatientDoesNotExist:
            logger.warning('Patient does not exist: {}'.format(patient_email[:3]+'****'+patient_email[-4:]))
            return render_error(request,
                                title='Patient Does Not Exist',
                                message='A FHIR resource does not yet exist for the current user. '
                                        'Please sign into the People-Powered dashboard to '
                                        'create your user.',
                                support=False)
        except Exception as e:
            logger.error("Error while submitting questionnaire: {}".format(e), exc_info=True, extra={
                'project': 'neer',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class ASDView(View):

    # Set the questionnaire ID
    questionnaire_id = 'ppm-asd-questionnaire'

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Get the patient email and ensure they exist
        patient_email = validate_request(request).get('email')

        try:
            # Check the patient
            FHIR.check_patient(patient_email)

            # Check response
            FHIR.check_response(self.questionnaire_id, patient_email)

            # Create the form
            form = ASDQuestionnaireForm(self.questionnaire_id)

            # Prepare the context
            context = {
                'questionnaire_id': self.questionnaire_id,
                'form': form,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/asd.html', context=context)

        except FHIR.PatientDoesNotExist:
            logger.warning('Patient does not exist: {}'.format(patient_email[:3] + '****' + patient_email[-4:]))
            return render_error(request,
                                title='Patient Does Not Exist',
                                message='A FHIR resource does not yet exist for the current user. '
                                        'Please sign into the People-Powered dashboard to '
                                        'create your user.',
                                support=False)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Questionnaire does not exist: {}'.format(self.questionnaire_id))
            return render_error(request,
                                title='Questionnaire Does Not Exist',
                                message='The requested questionnaire does not exist!',
                                support=False)

        except FHIR.QuestionnaireResponseAlreadyExists:
            logger.warning('Questionnaire already finished')
            return render_error(request,
                                title='Questionnaire Already Completed',
                                message='You have already filled out and submitted this '
                                        'questionnaire.',
                                support=False)

        except Exception as e:
            logger.error("Error while rendering questionnaire: {}".format(e), exc_info=True, extra={
                'request': request, 'project': 'asd',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'.format(
                                    ': {}'.format(e) if settings.DEBUG else '.'
                                ),
                                support=False)

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):

        # Get the patient email
        patient_email = validate_request(request).get('email')

        # create a form instance and populate it with data from the request:
        form = ASDQuestionnaireForm(self.questionnaire_id, request.POST)

        # check whether it's valid:
        if not form.is_valid():
            # Get the return URL

            context = {
                'form': form,
                'questionnaire_id': self.questionnaire_id,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/asd.html', context=context)

        # Process the form
        try:
            FHIR.submit_asd_questionnaire(patient_email, form.cleaned_data)

            # Get the return URL
            context = {
                'questionnaire_id': self.questionnaire_id,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/success.html', context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Questionnaire does not exist: {}'.format(self.questionnaire_id))
            return render_error(request,
                                title='Questionnaire Does Not Exist',
                                message='The requested questionnaire does not exist!',
                                support=False)

        except FHIR.PatientDoesNotExist:
            logger.warning('Patient does not exist: {}'.format(patient_email[:3] + '****' + patient_email[-4:]))
            return render_error(request,
                                title='Patient Does Not Exist',
                                message='A FHIR resource does not yet exist for the current user. '
                                        'Please sign into the People-Powered dashboard to '
                                        'create your user.',
                                support=False)
        except Exception as e:
            logger.error("Error while submitting questionnaire: {}".format(e), exc_info=True, extra={
                'project': 'asd',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


def render_error(request, title=None, message=None, support=False):

    # Set default values
    if not title:
        title = 'Application Error'

    if not message:
        message = 'The application has experienced an error. Please contact support or try again.'

    # Enable the contact button
    context = {'error_title': title,
               'error_message': message,
               'return_url': settings.RETURN_URL,
               'support': support}

    return render(request, template_name='fhirquestionnaire/error.html', context=context)
