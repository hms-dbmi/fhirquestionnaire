import threading

from django.http.response import HttpResponseRedirect
from django.shortcuts import render, redirect, reverse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import View

from dbmi_client.auth import dbmi_user
from dbmi_client.authn import get_jwt_email

from ppmutils.ppm import PPM
from ppmutils.p2md import P2MD
from ppmutils.fhir import FHIR as PPMFHIR
from fhirquestionnaire.fhir import FHIR
from consent.forms import AutismTypeForm, AutismGuardianQuiz, AutismIndividualQuiz, \
    AutismIndividualSignatureForm, AutismGuardianSignatureForm, AutismWardSignatureForm
from consent import forms
from questionnaire.views import get_return_url
from api.views import ConsentView as APIConsentView

import logging
logger = logging.getLogger(__name__)


class IndexView(View):

    def get(self, request, *args, **kwargs):
        logger.warning('Index view')

        # Get return URL
        get_return_url(request)

        return render_error(request,
                            title='Consent Not Specified',
                            message='A consent must be specified.',
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

        # Set a test cookie
        request.session.set_test_cookie()

        # Get return URL
        get_return_url(request)

        # Redirect them
        if PPM.Study.get(study) is PPM.Study.ASD:

            return redirect(reverse('consent:autism'))

        elif PPM.Study.from_value(study):

            return redirect(reverse('consent:consent', kwargs={'study': study}))

        else:
            logger.warning('Invalid study ID: {}'.format(study))
            return render_error(request,
                                title='Invalid Study Specified',
                                message='A valid study must be specified in order to load the needed consent.',
                                support=False)


class ConsentView(View):

    # Set the FHIR ID if the Questionnaire resource
    study = None
    questionnaire_id = None
    Form = None
    return_url = None

    @method_decorator(dbmi_user)
    def dispatch(self, request, *args, **kwargs):

        # Get study from the URL
        self.study = kwargs['study']
        self.questionnaire_id = PPM.Questionnaire.consent_questionnaire_for_study(self.study)

        # Select form from study
        self.Form = forms.get_form_for_study(self.study)

        # Get return URL
        self.return_url = get_return_url(request)

        # Proceed with super's implementation.
        return super(ConsentView, self).dispatch(request, *args, **kwargs)

    @method_decorator(dbmi_user)
    def get(self, request, *args, **kwargs):

        # Clearing any leftover sessions
        request.session.clear()
        request.session['return_url'] = self.return_url

        # Get the patient email and ensure they exist
        patient_email = get_jwt_email(request=request, verify=False)

        try:
            FHIR.check_patient(patient_email)

            # Check response
            FHIR.check_response(self.questionnaire_id, patient_email)

            # Create the form
            form = self.Form()

            context = {
                'study': self.study,
                'form': form,
                'return_url': self.return_url
            }

            # Build the template response
            response = render(request, template_name='consent/{}.html'.format(self.study), context=context)

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
            logger.warning('Consent does not exist: {}'.format(PPM.Study.title(self.study)))
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
                'request': request, 'project': self.study, 'questionnaire': self.questionnaire_id, 'form': self.Form
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)

    @method_decorator(dbmi_user)
    def post(self, request, *args, **kwargs):

        # Get the patient email
        patient_email = get_jwt_email(request=request, verify=False)

        # Get the form
        form = self.Form(request.POST)
        if not form.is_valid():

            # Return the form
            context = {
                'study': self.study,
                'form': form,
                'return_url': self.return_url
            }

            return render(request, template_name='consent/{}.html'.format(self.study), context=context)

        # Process the form
        try:
            # Submit the consent
            FHIR.submit_consent(self.study, patient_email, form.cleaned_data)

            # Submit consent PDF in the background
            threading.Thread(target=APIConsentView.create_consent_document_reference,
                             args=(request, self.study)).start()

            # Get the return URL
            context = {
                'study': self.study,
                'return_url': self.return_url,
            }

            # Get the passed parameters
            return render(request, template_name='consent/success.html', context=context)

        except FHIR.QuestionnaireDoesNotExist:
            logger.warning('Consent does not exist: {}'.format(PPM.Study.title(self.study)))
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
                'request': request, 'project': self.study, 'questionnaire': self.questionnaire_id, 'form': self.Form
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class AutismView(View):

    # Set the FHIR ID if the Questionnaire resource
    individual_questionnaire_id = 'ppm-asd-consent-guardian-quiz'
    guardian_questionnaire_id = 'ppm-asd-consent-individual-quiz'
    return_url = None

    @method_decorator(dbmi_user)
    def dispatch(self, request, *args, **kwargs):

        # Get return URL
        self.return_url = get_return_url(request)

        # Proceed with super's implementation.
        return super(AutismView, self).dispatch(request, *args, **kwargs)

    @method_decorator(dbmi_user)
    def get(self, request, *args, **kwargs):

        # Clearing any leftover sessions
        request.session.clear()
        request.session['return_url'] = self.return_url

        # Get the patient email and ensure they exist
        patient_email = get_jwt_email(request=request, verify=False)

        try:
            FHIR.check_patient(patient_email)

            # Check response
            FHIR.check_response(self.individual_questionnaire_id, patient_email)
            FHIR.check_response(self.guardian_questionnaire_id, patient_email)

            # Create the form
            form = AutismTypeForm()

            context = {
                'form': form,
                'return_url': self.return_url
            }

            return render(request, template_name='consent/autism.html', context=context)

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
                 'request': request, 'project': 'autism',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)

    @method_decorator(dbmi_user)
    def post(self, request, *args, **kwargs):

        # Process the form
        try:
            # Get the form
            form = AutismTypeForm(request.POST)
            if not form.is_valid():

                # Return the form
                context = {
                    'form': form,
                    'return_url': self.return_url
                }

                return render(request, template_name='consent/autism.html', context=context)

            # Save it in their session
            request.session['individual'] = form.cleaned_data['individual']

            # Check the consent type
            if form.cleaned_data['individual']:

                # Build the quiz form
                form = AutismIndividualQuiz()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': self.return_url,
                }

                # Get the passed parameters
                return render(request, template_name='consent/autism/ppm-asd-consent-individual-quiz.html', context=context)
            else:

                # Build the quiz form
                form = AutismGuardianQuiz()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': request.session['return_url'],
                }

                # Get the passed parameters
                return render(request, template_name='consent/autism/ppm-asd-consent-guardian-quiz.html', context=context)

        except Exception as e:
            logger.error("Error while submitting consent: {}".format(e), exc_info=True, extra={
                'project': 'autism',
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class AutismQuizView(View):

    return_url = None

    @method_decorator(dbmi_user)
    def dispatch(self, request, *args, **kwargs):

        # Get return URL
        self.return_url = get_return_url(request)

        # Proceed with super's implementation.
        return super(AutismQuizView, self).dispatch(request, *args, **kwargs)

    @method_decorator(dbmi_user)
    def post(self, request, *args, **kwargs):
        logger.debug('Autism Quiz')

        # Process the form
        try:
            # Check form type
            if request.session['individual']:
                logger.debug('Individual quiz submitted')

                # Get the form
                form = AutismIndividualQuiz(request.POST)
                if not form.is_valid():
                    logger.debug('Form errors: {}'.format(form.errors.as_json()))

                    # Return the form
                    context = {
                        'form': form,
                        'return_url': self.return_url
                    }

                    return render(request, template_name='consent/autism/ppm-asd-consent-individual-quiz.html',
                                  context=context)

                # Retain their responses
                request.session['quiz'] = form.cleaned_data

                # Create the form
                form = AutismIndividualSignatureForm()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': self.return_url,
                }

                # Get the passed parameters
                return render(request, template_name='consent/autism/individual-signature-part-1.html', context=context)

            else:
                logger.debug('Guardian quiz submitted')

                # Get the form
                form = AutismGuardianQuiz(request.POST)
                if not form.is_valid():
                    logger.debug('Guardian quiz invalid: {}'.format(form.errors.as_json()))

                    # Return the form
                    context = {
                        'form': form,
                        'return_url': self.return_url
                    }

                    return render(request, template_name='consent/autism/ppm-asd-consent-guardian-quiz.html',
                                  context=context)

                # Retain their responses
                request.session['quiz'] = form.cleaned_data

                # Make the form
                form = AutismGuardianSignatureForm()

                # Get the return URL
                context = {
                    'form': form,
                    'return_url': self.return_url,
                }

                # Get the passed parameters
                return render(request, template_name='consent/autism/guardian-signature-part-1-2.html', context=context)

        except Exception as e:
            logger.error("Error while submitting consent quiz: {}".format(e), exc_info=True, extra={
                'project': 'autism', 'request': request,
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error {}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class AutismSignatureView(View):

    return_url = None

    @method_decorator(dbmi_user)
    def dispatch(self, request, *args, **kwargs):

        # Get return URL
        self.return_url = get_return_url(request)

        # Proceed with super's implementation.
        return super(AutismSignatureView, self).dispatch(request, *args, **kwargs)

    @method_decorator(dbmi_user)
    def post(self, request, *args, **kwargs):
        logger.debug('Signature view')

        # Get the patient's email
        patient_email = get_jwt_email(request=request, verify=False)

        # Process the form
        try:
            # Check form type
            if request.session['individual']:
                logger.debug('Individual signature')

                # Get the form
                form = AutismIndividualSignatureForm(request.POST)
                if not form.is_valid():
                    logger.debug('Individual signature invalid: {}'.format(form.errors.as_json()))

                    # Return the form
                    context = {
                        'form': form,
                        'return_url': self.return_url
                    }

                    return render(request, template_name='consent/autism/individual-signature-part-1.html', context=context)

                # Build the data
                forms = dict({'individual': form.cleaned_data, 'quiz': request.session['quiz']})

                # Submit the data
                FHIR.submit_autism_individual(patient_email, forms)

                # Submit consent PDF in the background
                threading.Thread(target=APIConsentView.create_consent_document_reference,
                                 args=(request, PPM.Study.ASD.value)).start()

                # Get the return URL
                context = {
                    'return_url': self.return_url,
                }

                # Get the passed parameters
                return render(request, template_name='consent/success.html', context=context)

            else:
                logger.debug('Guardian/ward signature')

                # Check which signature
                if request.session.get('guardian'):
                    logger.debug('Ward signature')

                    # Get the form
                    form = AutismWardSignatureForm(request.POST)
                    if not form.is_valid():
                        logger.debug('Ward signature invalid: {}'.format(form.errors.as_json()))

                        # Return the form
                        context = {
                            'form': form,
                            'return_url': request.session['return_url']
                        }

                        return render(request, template_name='consent/autism/guardian-signature-part-3.html',
                                      context=context)

                    # Build the data
                    forms = dict({'ward': form.cleaned_data,
                                 'guardian': request.session['guardian'],
                                 'quiz': request.session['quiz']})

                    # Submit the data
                    FHIR.submit_autism_guardian(patient_email, forms)

                    # Submit consent PDF in the background
                    threading.Thread(target=APIConsentView.create_consent_document_reference,
                                     args=(request, PPM.Study.ASD.value)).start()

                    # Get the return URL
                    context = {
                        'return_url': self.return_url,
                    }

                    # Get the passed parameters
                    return render(request, template_name='consent/success.html', context=context)

                else:
                    logger.debug('Guardian signature')

                    # Get the form
                    form = AutismGuardianSignatureForm(request.POST)
                    if not form.is_valid():
                        logger.debug('Guardian signature invalid: {}'.format(form.errors.as_json()))

                        # Return the form
                        context = {
                            'form': form,
                            'return_url': self.return_url
                        }

                        return render(request, template_name='consent/autism/guardian-signature-part-1-2.html', context=context)

                    # Fix the date
                    date = form.cleaned_data['date'].isoformat()
                    form.cleaned_data['date'] = date

                    # Retain their responses
                    request.session['guardian'] = form.cleaned_data

                    # Make the ward signature form
                    form = AutismWardSignatureForm()

                    # Get the return URL
                    context = {
                        'form': form,
                        'return_url': self.return_url,
                    }

                    # Get the passed parameters
                    return render(request, template_name='consent/autism/guardian-signature-part-3.html', context=context)

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
                'project': 'autism', 'request': request,
            })
            return render_error(request,
                                title='Application Error',
                                message='The application has experienced an unknown error{}'
                                .format(': {}'.format(e) if settings.DEBUG else '.'),
                                support=False)


class DownloadView(View):
    """
    This is a temporary viewset to retroactively populate participants' datasets
    with renders of their signed consents and then redirecting them to P2MD where
    the actual download will take place.
    """

    @method_decorator(dbmi_user)
    def get(self, request, *args, **kwargs):

        # Get the study
        study = kwargs['study']

        try:
            # Get the patient email and ensure they exist
            patient_email = get_jwt_email(request=request, verify=False)

            # Check FHIR
            if not PPMFHIR.get_consent_document_reference(patient=patient_email, study=study, flatten_return=True):

                # Save it
                APIConsentView.create_consent_document_reference(request=request, study=study)

            # Get their ID
            ppm_id = PPMFHIR.query_patient_id(email=patient_email)

            return HttpResponseRedirect(redirect_to=P2MD.get_consent_url(study=study, ppm_id=ppm_id))

        except Exception as e:
            logger.error("Error while rendering consent: {}".format(e), exc_info=True, extra={
                 'request': request, 'project': study,
            })

        raise SystemError('Could not render consent document')


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
               'return_url': request.session['return_url'],
               'support': support}

    return render(request, template_name='fhirquestionnaire/error.html', context=context)
