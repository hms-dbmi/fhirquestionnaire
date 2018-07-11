import re

from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, reverse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages

from fhirquestionnaire.jwt import dbmi_jwt, dbmi_jwt_payload
from contact.forms import ContactForm

import logging
logger = logging.getLogger(__name__)


class ContactView(View):

    @method_decorator(dbmi_jwt)
    def get(self, request, *args, **kwargs):
        logger.debug("Generating contact form")

        # Set initial values.
        initial = {
            'email': dbmi_jwt_payload(request).get('email')
        }

        # Generate and render the form.
        form = ContactForm(initial=initial)
        if request.is_ajax():
            return render(request, 'contact/modal.html', {'contact_form': form})
        else:
            return render(request, 'contact/contact.html', {'contact_form': form})

    @method_decorator(dbmi_jwt)
    def post(self, request, *args, **kwargs):
        logger.debug("Processing contact form POST")

        # Process the form.
        form = ContactForm(request.POST)
        if form.is_valid():
            logger.debug("Form is valid")

            # Get the user's browser
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')

            # Form the context.
            context = {
                'from_email': form.cleaned_data['email'],
                'from_name': form.cleaned_data['name'],
                'message': form.cleaned_data['message'],
                'user_agent': user_agent,
            }

            # List out the recipients.
            recipients = settings.CONTACT_FORM_RECIPIENTS.split(',')

            # Check for test accounts.
            test_admin = ContactView.check_test_account(email=dbmi_jwt_payload(request).get('email'))
            if test_admin is not None:
                recipients = [test_admin]

            logger.debug("Found recipients {}".format(recipients))

            # Send it out.
            msg_html = render_to_string('contact/email/contact.html', context)
            msg_plain = render_to_string('contact/email/contact.txt', context)

            try:
                msg = EmailMultiAlternatives('PPM Contact Form Inquiry', msg_plain, settings.DEFAULT_FROM_EMAIL, recipients)
                msg.attach_alternative(msg_html, "text/html")
                msg.send()

                logger.debug("Contact email sent!")

                # Check how the request was made.
                if request.is_ajax():
                    return HttpResponse('SUCCESS', status=200)
                else:
                    return render(request, 'contact/success.html',
                                  context={'return_url': settings.RETURN_URL})

            except Exception as e:
                logger.exception(e)

                if request.is_ajax():
                    return HttpResponse('ERROR', status=500)
                else:
                    messages.error(request, 'An unexpected error occurred, please try again')
                    return ContactView.render_error(request)

        else:
            logger.error("Form is invalid: {}".format(request.POST))

            # Check how the request was made.
            if request.is_ajax():
                return HttpResponse('INVALID', status=500)
            else:
                messages.error(request, 'An unexpected error occurred, please try again')
                return HttpResponseRedirect(reverse('contact:contact'))

    @staticmethod
    def render_error(request, title=None, message=None, support=True):

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

        return render(request, template_name='contact/error.html', context=context)

    @staticmethod
    def check_test_account(email):
        """
        Tests the given user account for matching that of a test account.
        Test accounts are specified as [regex 1]:[admin email],[regex 2]:[admin email],...
        If the given user is a test account, return the specific admin for which notifications
        should be limited to sending to.
        :param email: The current user's email
        :return: Admin email address if test account, None if not
        """

        # Check for test accounts
        try:
            test_accounts = settings.TEST_EMAIL_ACCOUNTS.split(',')
            if test_accounts is not None and len(test_accounts) > 0:
                for test_account in test_accounts:
                    logger.debug("Trying test account pattern: {}"
                                 .format(test_account))

                    # Split the test account email from the destination admin email
                    test_account_parts = test_account.split(':')
                    regex = re.compile(test_account_parts[0])
                    matches = regex.match(email)
                    if matches is not None and matches.group():
                        logger.debug("Test account found: {}, sending to {}"
                                     .format(email, test_account_parts[1]))

                        # Return the test admin email
                        return test_account_parts[1]

                logger.debug("No test account matches!")

            else:
                logger.debug("No test accounts found!")

        except Exception as e:
            logger.exception("Failed looking for test email: {}".format(e))

        return None
