from django.shortcuts import render, redirect, reverse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import View

from fhirquestionnaire.fhir import FHIR
from consent.forms import ASDTypeForm, ASDGuardianQuiz, ASDIndividualQuiz, \
    ASDIndividualSignatureForm, ASDGuardianSignatureForm, ASDWardSignatureForm
from consent.forms import NEERSignatureForm
from pyauth0jwt.auth0authenticate import dbmi_jwt, validate_request

import logging
logger = logging.getLogger(__name__)


class IndexView(View):

    def get(self, request, *args, **kwargs):
        logger.warning('Index view')

        return render_error(request,
                            title='Consent Not Specified',
                            message='A consent must be specified.',
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

        # Set a test cookie
        request.session.set_test_cookie()

        # Redirect them
        if project_id == 'neer':

            return redirect(reverse('consent:neer'))

        elif project_id == 'asd':

            return redirect(reverse('consent:asd'))

        else:
            logger.warning('Invalid project ID: {}'.format(project_id))
            return render_error(request,
                                title='Invalid Project Specified',
                                message='A valid project must be specified in order to load the needed consent.',
                                support=False)


class NEERView(View):

    # Set the FHIR ID if the Questionnaire resource
    questionnaire_id = 'neer-signature'

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Clearing any leftover sessions
        request.session.clear()

        # Get the patient email and ensure they exist
        patient_email = validate_request(request).get('email')

        try:
            FHIR.check_patient(patient_email)

            # Check response
            FHIR.check_response(self.questionnaire_id, patient_email)

            # Create the form
            form = NEERSignatureForm()

            context = {
                'form': form,
                'return_url': settings.RETURN_URL
            }

            # Build the template response
            response = render(request, template_name='consent/neer.html', context=context)

            return response

        except FHIR.PatientDoesNotExist:
            logger.warning('Patient does not exist')
            return render_error(request,
                                title='Patient Does Not Exist',
                                message='A FHIR resource does not yet exist for the current user. '
                                        'Please sign into the People-Powered dashboard to '
                                        'create your user.',
                                support=False)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Consent does not exist: NEER')
            return render_error(request,
                                title='Consent Does Not Exist: {}'.format(self.questionnaire_id),
                                message='The requested consent does not exist!',
                                support=False)

        except FHIR.QuestionnaireResponseAlreadyExists:
            logger.warning('Consent already finished')
            return render_error(request,
                                title='Consent Already Completed',
                                message='You have already filled out and submitted this '
                                        'consent.',
                                support=False)

        except Exception as e:
            logger.error("Error while rendering consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': 'neer', 'questionnaire': self.questionnaire_id,
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):

        # Get the patient email
        patient_email = validate_request(request).get('email')

        # Get the form
        form = NEERSignatureForm(request.POST)
        if not form.is_valid():

            # Return the form
            context = {
                'form': form,
                'return_url': settings.RETURN_URL
            }

            return render(request, template_name='consent/neer.html', context=context)

        # Process the form
        try:
            FHIR.submit_neer_consent(patient_email, form.cleaned_data)

            # Get the return URL
            context = {
                'return_url': settings.RETURN_URL,
            }

            # Get the passed parameters
            return render(request, template_name='consent/success.html', context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Consent does not exist: NEER')
            return render_error(request,
                                title='Consent Does Not Exist: {}'.format(self.questionnaire_id),
                                message='The requested consent does not exist!',
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
            logger.error("Error while submitting consent: {}".format(e), exc_info=True, extra={
                'request': request, 'project': 'neer', 'questionnaire': self.questionnaire_id,
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class ASDView(View):

    # Set the FHIR ID if the Questionnaire resource
    individual_questionnaire_id = 'ppm-asd-consent-guardian-quiz'
    guardian_questionnaire_id = 'ppm-asd-consent-individual-quiz'

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):

        # Clearing any leftover sessions
        request.session.clear()

        # Get the patient email and ensure they exist
        patient_email = validate_request(request).get('email')

        try:
            FHIR.check_patient(patient_email)

            # Check response
            FHIR.check_response(self.individual_questionnaire_id, patient_email)
            FHIR.check_response(self.guardian_questionnaire_id, patient_email)

            # Create the form
            form = ASDTypeForm()

            context = {
                'form': form,
                'return_url': settings.RETURN_URL
            }

            return render(request, template_name='consent/asd.html', context=context)

        except FHIR.PatientDoesNotExist:
            logger.warning('Patient does not exist')
            return render_error(request,
                                title='Patient Does Not Exist',
                                message='A FHIR resource does not yet exist for the current user. '
                                        'Please sign into the People-Powered dashboard to '
                                        'create your user.',
                                support=False)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Consent does not exist: NEER')
            return render_error(request,
                                title='Consent Does Not Exist',
                                message='The requested consent does not exist!',
                                support=False)

        except FHIR.QuestionnaireResponseAlreadyExists:
            logger.warning('Consent already finished')
            return render_error(request,
                                title='Consent Already Completed',
                                message='You have already filled out and submitted this '
                                        'consent.',
                                support=False)

        except Exception as e:
            logger.error("Error while rendering consent: {}".format(e), exc_info=True, extra={
                 'request': request, 'project': 'asd',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):

        # Process the form
        try:
            # Get the form
            form = ASDTypeForm(request.POST)
            if not form.is_valid():

                # Return the form
                context = {
                    'form': form,
                    'return_url': settings.RETURN_URL
                }

                return render(request, template_name='consent/neer.html', context=context)

            # Save it in their session
            request.session['individual'] = form.cleaned_data['individual']

            # Check the consent type
            if form.cleaned_data['individual']:

                # Build the quiz form
                form = ASDIndividualQuiz()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': settings.RETURN_URL,
                }

                # Get the passed parameters
                return render(request, template_name='consent/asd/ppm-asd-consent-individual-quiz.html', context=context)
            else:

                # Build the quiz form
                form = ASDGuardianQuiz()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': settings.RETURN_URL,
                }

                # Get the passed parameters
                return render(request, template_name='consent/asd/ppm-asd-consent-guardian-quiz.html', context=context)

        except Exception as e:
            logger.error("Error while submitting consent: {}".format(e), exc_info=True, extra={
                'project': 'asd',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class ASDQuizView(View):

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):
        logger.debug('ASD Quiz')

        # Process the form
        try:
            # Check form type
            if request.session['individual']:
                logger.debug('Individual quiz submitted')

                # Get the form
                form = ASDIndividualQuiz(request.POST)
                if not form.is_valid():
                    logger.debug('Form errors: {}'.format(form.errors.as_json()))

                    # Return the form
                    context = {
                        'form': form,
                        'return_url': settings.RETURN_URL
                    }

                    return render(request, template_name='consent/asd/ppm-asd-consent-individual-quiz.html',
                                  context=context)

                # Retain their responses
                request.session['quiz'] = form.cleaned_data

                # Create the form
                form = ASDIndividualSignatureForm()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': settings.RETURN_URL,
                }

                # Get the passed parameters
                return render(request, template_name='consent/asd/individual-signature-part-1.html', context=context)

            else:
                logger.debug('Guardian quiz submitted')

                # Get the form
                form = ASDGuardianQuiz(request.POST)
                if not form.is_valid():
                    logger.debug('Guardian quiz invalid: {}'.format(form.errors.as_json()))

                    # Return the form
                    context = {
                        'form': form,
                        'return_url': settings.RETURN_URL
                    }

                    return render(request, template_name='consent/asd/ppm-asd-consent-guardian-quiz.html',
                                  context=context)

                # Retain their responses
                request.session['quiz'] = form.cleaned_data

                # Make the form
                form = ASDGuardianSignatureForm()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': settings.RETURN_URL,
                }

                # Get the passed parameters
                return render(request, template_name='consent/asd/guardian-signature-part-1-2.html', context=context)

        except Exception as e:
            logger.error("Error while submitting consent quiz: {}".format(e), exc_info=True, extra={
                'project': 'asd', 'request': request,
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class ASDSignatureView(View):

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):
        logger.debug('Signature view')

        # Get the patient's email
        patient_email = validate_request(request).get('email')

        # Process the form
        try:
            # Check form type
            if request.session['individual']:
                logger.debug('Individual signature')

                # Get the form
                form = ASDIndividualSignatureForm(request.POST)
                if not form.is_valid():
                    logger.debug('Individual signature invalid: {}'.format(form.errors.as_json()))

                    # Return the form
                    context = {
                        'form': form,
                        'return_url': settings.RETURN_URL
                    }

                    return render(request, template_name='consent/asd/individual-signature-part-1.html', context=context)

                # Build the data
                forms = dict({'individual': form.cleaned_data, 'quiz': request.session['quiz']})

                # Submit the data
                FHIR.submit_asd_individual(patient_email, forms)

                # Get the return URL
                context = {
                    'return_url': settings.RETURN_URL,
                }

                # Get the passed parameters
                return render(request, template_name='consent/success.html', context=context)

            else:
                logger.debug('Guardian/ward signature')

                # Check which signature
                if request.session.get('guardian'):
                    logger.debug('Ward signature')

                    # Get the form
                    form = ASDWardSignatureForm(request.POST)
                    if not form.is_valid():
                        logger.debug('Ward signature invalid: {}'.format(form.errors.as_json()))

                        # Return the form
                        context = {
                            'form': form,
                            'return_url': settings.RETURN_URL
                        }

                        return render(request, template_name='consent/asd/guardian-signature-part-3.html',
                                      context=context)

                    # Build the data
                    forms = dict({'ward': form.cleaned_data,
                                 'guardian': request.session['guardian'],
                                 'quiz': request.session['quiz']})

                    # Submit the data
                    FHIR.submit_asd_guardian(patient_email, forms)

                    # Get the return URL
                    context = {
                        'return_url': settings.RETURN_URL,
                    }

                    # Get the passed parameters
                    return render(request, template_name='consent/success.html', context=context)

                else:
                    logger.debug('Guardian signature')

                    # Get the form
                    form = ASDGuardianSignatureForm(request.POST)
                    if not form.is_valid():
                        logger.debug('Guardian signature invalid: {}'.format(form.errors.as_json()))

                        # Return the form
                        context = {
                            'form': form,
                            'return_url': settings.RETURN_URL
                        }

                        return render(request, template_name='consent/asd/guardian-signature-part-1-2.html', context=context)

                    # Fix the date
                    date = form.cleaned_data['date'].isoformat()
                    form.cleaned_data['date'] = date

                    # Retain their responses
                    request.session['guardian'] = form.cleaned_data

                    logger.debug('Guardian: {}'.format(request.session['guardian']))

                    # Make the ward signature form
                    form = ASDWardSignatureForm()

                    # Get the return URL
                    context = {
                        'form': form,
                        'return_url': settings.RETURN_URL,
                    }

                    # Get the passed parameters
                    return render(request, template_name='consent/asd/guardian-signature-part-3.html', context=context)

        except FHIR.PatientDoesNotExist:
            logger.warning('Patient does not exist')
            return render_error(request,
                                title='Patient Does Not Exist',
                                message='A FHIR resource does not yet exist for the current user. '
                                        'Please sign into the People-Powered dashboard to '
                                        'create your user.',
                                support=False)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Consent does not exist: NEER')
            return render_error(request,
                                title='Consent Does Not Exist',
                                message='The requested consent does not exist!',
                                support=False)

        except FHIR.QuestionnaireResponseAlreadyExists:
            logger.warning('Consent already finished')
            return render_error(request,
                                title='Consent Already Completed',
                                message='You have already filled out and submitted this '
                                        'consent.',
                                support=False)

        except Exception as e:
            logger.error("Error while submitting consent signature: {}".format(e), exc_info=True, extra={
                'project': 'asd', 'request': request,
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


def render_error(request, title=None, message=None, error=None, support=False):

    # Set default values
    if not title:
        title = 'Application Error'

    if not message and support:
        message = 'The application has experienced an error. Please contact support or try again.'
    elif not message:
        message = 'The application has experienced an error. Please try again.'

    # Enable the contact button
    context = {'error_title': title,
               'error_message': message,
               'error_description': error,
               'return_url': settings.RETURN_URL,
               'support': support}

    return render(request, template_name='fhirquestionnaire/error.html', context=context)