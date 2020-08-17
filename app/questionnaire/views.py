import base64
from django.shortcuts import render, reverse, redirect
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import View

from ppmutils.ppm import PPM
from dbmi_client.auth import dbmi_user
from dbmi_client.authn import get_jwt_email

from questionnaire import forms
from fhirquestionnaire.fhir import FHIR


import logging
logger = logging.getLogger(__name__)


def get_return_url(request):
    """ This method checks the common locations for the URL, decodes it and returns it"""
    # Get return URL
    if request.GET.get('return_url'):
        return_url = base64.b64decode(request.GET.get('return_url').encode()).decode()
        logger.debug('Querystring Return URL: {}'.format(return_url))
    elif request.session.get('return_url'):
        return_url = request.session['return_url']
        logger.debug('Session Return URL: {}'.format(return_url))
    elif request.META.get('HTTP_REFERER'):
        return_url = request.META.get('HTTP_REFERER')
        logger.debug('Referrer Return URL: {}'.format(return_url))
    else:
        raise ValueError('Request must include the \'return_url\' query parameter')

    # Set it on session and return it
    request.session['return_url'] = return_url
    return return_url


class IndexView(View):

    def get(self, request, *args, **kwargs):
        logger.warning('Index view')

        # Set return URL in session
        get_return_url(request)

        return render_error(request,
                            title='Questionnaire Not Specified',
                            message='A questionnaire must be specified.',
                            support=False)


class StudyView(View):

    @method_decorator(dbmi_user)
    def get(self, request, *args, **kwargs):

        # Get the project ID
        study = kwargs.get('study')
        if not study:
            return render_error(request,
                                title='Study Not Specified',
                                message='A study must be specified in order to load the needed consent.',
                                support=False)

        # Set return URL in session
        get_return_url(request)

        # Pass along querystring if present
        query_string = "?" + request.META.get('QUERY_STRING') if request.META.get('QUERY_STRING') else ""

        # Redirect them
        if PPM.Study.from_value(study):

            return redirect(reverse('questionnaire:questionnaire', kwargs={'study': study}) + query_string)

        else:
            return render_error(request,
                                title='Invalid Study Specified',
                                message='A valid study must be specified in order to load the needed consent.',
                                support=False)


class QuestionnaireView(View):

    study = None
    questionnaire_id = None
    Form = None
    return_url = None

    @method_decorator(dbmi_user)
    def dispatch(self, request, *args, **kwargs):

        # Get study from the URL
        self.study = kwargs['study']
        self.questionnaire_id = PPM.Questionnaire.questionnaire_for_study(self.study)

        # Convert "autism" to "asd"
        if PPM.Study.get(self.study) is PPM.Study.ASD:
            self.study = 'asd'

        # Select form from study
        self.Form = forms.get_form_for_study(self.study)

        # Get return URL
        self.return_url = get_return_url(request)

        # Proceed with super's implementation.
        return super(QuestionnaireView, self).dispatch(request, *args, **kwargs)

    @method_decorator(dbmi_user)
    def get(self, request, *args, **kwargs):

        # Get the patient email and ensure they exist
        patient_email = get_jwt_email(request=request, verify=False)

        try:
            # Check the current patient
            FHIR.check_patient(patient_email)

            # Check response
            FHIR.check_response(self.questionnaire_id, patient_email)

            # Create the form
            form = self.Form(self.questionnaire_id)

            # Prepare the context
            context = {
                'study': self.study,
                'questionnaire_id': self.questionnaire_id,
                'form': form,
                'return_url': self.return_url,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/{}.html'.format(self.study), context=context)

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
                'request': request, 'project': self.study,
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)

    @method_decorator(dbmi_user)
    def post(self, request, *args, **kwargs):

        # Get the patient email
        patient_email = get_jwt_email(request=request, verify=False)

        # create a form instance and populate it with data from the request:
        form = self.Form(self.questionnaire_id, request.POST)

        # check whether it's valid:
        if not form.is_valid():
            # Get the return URL

            context = {
                'study': self.study,
                'form': form,
                'questionnaire_id': self.questionnaire_id,
                'return_url': self.return_url,
            }

            # Get the passed parameters
            return render(request, template_name='questionnaire/{}.html'.format(self.study), context=context)

        # Process the form
        try:
            FHIR.submit_questionnaire(self.study, patient_email, form.cleaned_data)

            # Get the return URL
            context = {
                'questionnaire_id': self.questionnaire_id,
                'return_url': self.return_url,
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
                'project': self.study,
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
