import datetime

from django.shortcuts import render, redirect, reverse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.contrib import messages

from fhirquestionnaire.fhir import FHIR
from fhirquestionnaire.jwt import dbmi_jwt, dbmi_jwt_payload

import logging
logger = logging.getLogger(__name__)


class IndexView(View):

    def get(self, request, *args, **kwargs):
        logger.warning('Index view')

        return ConsentView.render_error(request,
                                        title='Consent Not Specified',
                                        message='A consent must be specified.',
                                        support=False)


class ProjectView(View):

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Get the project ID
        project_id = kwargs.get('project_id')
        if not project_id:
            return ConsentView.render_error(request,
                                            title='Project Not Specified',
                                            message='A project must be specified in order to load the needed consent.',
                                            support=False)

        # Redirect them
        if project_id == 'neer':

            return redirect(reverse('consent:consent',
                                    kwargs={'questionnaire_id': 'neer-signature'}))

        #elif project_id == 'autism':

            #return redirect(reverse('consent:consent',
                            # kwargs={'questionnaire_id': 'ppm-neer-registration-questionnaire'}))

        else:
            return ConsentView.render_error(request,
                                            title='Invalid Project Specified',
                                            message='A valid project must be specified in order to load the needed consent.',
                                            support=False)


class ConsentView(View):

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Get the FHIR ID
        questionnaire_id = kwargs.get('questionnaire_id')
        if not questionnaire_id:
            return ConsentView.render_error(request,
                                            title='Consent Not Specified',
                                            message='A consent must be specified.',
                                            support=False)

        # Get the patient email and ensure they exist
        patient_email = dbmi_jwt_payload(request).get('email')
        try:
            FHIR.check_patient(patient_email)

        except FHIR.PatientDoesNotExist:
            logger.error('Patient does not exist: {}'.format(patient_email[:3]+'****'+patient_email[-4:]))
            return ConsentView.render_error(request,
                                            title='Patient Does Not Exist',
                                            message='A FHIR resource does not yet exist for the current user. '
                                                    'Please sign into the People-Powered dashboard to '
                                                    'create your user.',
                                            support=False)

        try:
            # Check response
            FHIR.check_response(questionnaire_id, patient_email)

            # Prepare the context
            context = {
                'questionnaire_id': questionnaire_id,
                'return_url': settings.RETURN_URL,
                'today': datetime.datetime.utcnow().strftime('%Y-%m-%d')
            }

            # Get the passed parameters
            return render(request, template_name='consent/{}.html'.format(questionnaire_id), context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.error('Consent does not exist: {}'.format(questionnaire_id))
            return ConsentView.render_error(request,
                                            title='Consent Does Not Exist',
                                            message='The requested consent does not exist!',
                                            support=True)

        except FHIR.QuestionnaireResponseAlreadyExists:
            logger.warning('Consent already finished')
            return ConsentView.render_error(request,
                                            title='Consent Already Completed',
                                            message='You have already filled out and submitted this '
                                                    'consent.',
                                            support=True)

        except Exception as e:
            logger.exception(e)
            return ConsentView.render_error(request,
                                            title='Application Error',
                                            message='The application has experienced an unknown error {}'
                                            .format(': {}'.format(e) if settings.DEBUG else '.'),
                                            support=True)

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):

        # Get the FHIR ID
        questionnaire_id = kwargs.get('questionnaire_id')
        if not questionnaire_id:
            return ConsentView.render_error(request,
                                            title='Consent Not Specified',
                                            message='A consent must be specified.',
                                            support=True)

        # Get the patient email
        patient_email = dbmi_jwt_payload(request).get('email')

        # Parse the fields
        try:
            name = request.POST['name-of-participant'][0]
            signature = request.POST['signature-of-participant'][0]
            date = request.POST['date'][0]

            # Verify all data
            # TODO: DO this!

        except Exception as e:
            logger.exception(e)

            # Prepare the context
            context = {
                'questionnaire_id': questionnaire_id,
                'return_url': settings.RETURN_URL,
                'today': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
                'error': 'Please ensure all fields are filled out',
            }

            # Get the passed parameters
            return render(request, template_name='consent/{}.html'.format(questionnaire_id), context=context)

        # Process the form
        try:
            FHIR.submit(settings.FHIR_URL, questionnaire_id, patient_email, request.POST)

            # Get the return URL
            context = {
                'return_url': settings.RETURN_URL,
            }

            # Set a message.
            messages.success(request, 'Your consent submission has succeeded!',
                             extra_tags='success', fail_silently=True)

            # Get the passed parameters
            return render(request, template_name='consent/success.html', context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.error('Consent does not exist: {}'.format(questionnaire_id))
            return ConsentView.render_error(request,
                                            title='Consent Does Not Exist',
                                            message='The requested consent does not exist!',
                                            support=True)

        except FHIR.PatientDoesNotExist:
            logger.error('Patient does not exist: {}'.format(patient_email[:3]+'****'+patient_email[-4:]))
            return ConsentView.render_error(request,
                                            title='Patient Does Not Exist',
                                            message='A FHIR resource does not yet exist for the current user. '
                                                    'Please sign into the People-Powered dashboard to '
                                                    'create your user.',
                                            support=False)
        except Exception as e:
            logger.exception(e)
            return ConsentView.render_error(request,
                                            title='Application Error',
                                            message='The application has experienced an unknown error {}'
                                            .format(': {}'.format(e) if settings.DEBUG else '.'),
                                            support=True)

    @staticmethod
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

