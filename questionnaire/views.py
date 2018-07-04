from django.shortcuts import render
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import View

from questionnaire.forms import QuestionnaireForm
from questionnaire.fhir import FHIR
from fhirquestionnaire.jwt import dbmi_jwt, dbmi_jwt_payload

import logging
logger = logging.getLogger(__name__)


class IndexView(View):

    def get(self, request, *args, **kwargs):
        logger.warning('Index view')

        return QuestionnaireView.render_error(request,
                                              title='Questionnaire Not Specified',
                                              message='A questionnaire must be specified.',
                                              support=True)


class QuestionnaireView(View):

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Get the FHIR ID
        questionnaire_id = kwargs.get('questionnaire_id')
        if not questionnaire_id:
            return QuestionnaireView.render_error(request,
                                                  title='Questionnaire Not Specified',
                                                  message='A questionnaire must be specified.',
                                                  support=True)

        # Get the patient email and ensure they exist
        patient_email = dbmi_jwt_payload(request).get('email')
        try:
            FHIR.check_patient(patient_email)

        except FHIR.PatientDoesNotExist:
            logger.error('Patient does not exist: {}'.format(patient_email[:3]+'****'+patient_email[-4:]))
            return QuestionnaireView.render_error(request,
                                                  title='Patient Does Not Exist',
                                                  message='A FHIR resource does not yet exist for the current user. '
                                                          'Please sign into the People-Powered dashboard to '
                                                          'create your user.',
                                                  support=False)

        try:
            # Check response
            FHIR.check_response(questionnaire_id, patient_email)

            # Create the form
            form = QuestionnaireForm(questionnaire_id)

            # Prepare the context
            context = {
                'questionnaire_id': questionnaire_id,
                'form': form,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/questionnaire.html', context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.error('Questionnaire does not exist: {}'.format(questionnaire_id))
            return QuestionnaireView.render_error(request,
                                                  title='Questionnaire Does Not Exist',
                                                  message='The requested questionnaire does not exist!',
                                                  support=True)

        except FHIR.QuestionnaireResponseAlreadyExists:
            logger.warning('Questionnaire already finished')
            return QuestionnaireView.render_error(request,
                                                  title='Questionnaire Already Completed',
                                                  message='You have already filled out and submitted this '
                                                          'questionnaire.',
                                                  support=True)

        except Exception as e:
            logger.exception(e)
            return render(request, template_name='questionnaire/error.html',
                   context={'error': '{}'.format(e)})

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):

        # Get the FHIR ID
        questionnaire_id = kwargs.get('questionnaire_id')
        if not questionnaire_id:
            return QuestionnaireView.render_error(request,
                                                  title='Questionnaire Not Specified',
                                                  message='A questionnaire must be specified.',
                                                  support=True)

        # Get the patient email
        patient_email = dbmi_jwt_payload(request).get('email')

        # create a form instance and populate it with data from the request:
        form = QuestionnaireForm(questionnaire_id, request.POST)

        # check whether it's valid:
        if not form.is_valid():
            # Get the return URL

            context = {
                'form': form,
                'questionnaire_id': questionnaire_id,
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/questionnaire.html', context=context)

        # Process the form
        try:
            FHIR.submit(settings.FHIR_URL, questionnaire_id, patient_email, form.cleaned_data)

            # Get the return URL
            context = {
                'questionnaire_id': questionnaire_id,
               'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/success.html', context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.error('Questionnaire does not exist: {}'.format(questionnaire_id))
            return QuestionnaireView.render_error(request,
                                                  title='Questionnaire Does Not Exist',
                                                  message='The requested questionnaire does not exist!',
                                                  support=True)

        except FHIR.PatientDoesNotExist:
            logger.error('Patient does not exist: {}'.format(patient_email[:3]+'****'+patient_email[-4:]))
            return QuestionnaireView.render_error(request,
                                                  title='Patient Does Not Exist',
                                                  message='A FHIR resource does not yet exist for the current user. '
                                                          'Please sign into the People-Powered dashboard to '
                                                          'create your user.',
                                                  support=False)
        except Exception as e:
            logger.exception(e)
            return QuestionnaireView.render_error(request)

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

        return render(request, template_name='questionnaire/error.html', context=context)

