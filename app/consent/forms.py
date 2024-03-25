import datetime
import os
import json

from django.utils import timezone
from django import forms
from django.conf import settings
from django.template.defaultfilters import mark_safe
from bootstrap_datepicker_plus.widgets import DatePickerInput, MonthPickerInput
from ppmutils.ppm import PPM

from consent.apps import ConsentConfig

import logging
logger = logging.getLogger(__name__)


class SignatureDatePickerInput(DatePickerInput):
    """
    This subclass merely enforces a maximum date equal to the current
    date and ensures this is calculated at render time instead of
    initialization time.
    """

    _default_options = {
        'showClose': True,
        'showClear': True,
        'showTodayButton': True,
        'useCurrent': True,
    }

    def get_context(self, name, value, attrs):
        """Return widget context dictionary."""

        # Ensure maxDate has current date
        self.config['options']['maxDate'] = datetime.datetime.today()\
            .replace(hour=23, minute=59)\
                .strftime("%Y-%m-%dT%H:%M:%S")

        return super(SignatureDatePickerInput, self).get_context(
            name, value, attrs
        )


def _exception_choices(questionnaire_id):
    '''
    Takes the FHIR Questionnaire resource and returns a tuple of choices to be used
    for the exception options on the signature portion of the consents
    :param resource: The FHIR Questionnaire resource as a dict
    :return: choices
    '''

    # Open resource
    fhir_dir = os.path.join(os.path.dirname(settings.STATIC_ROOT), ConsentConfig.name, 'fhir')
    with open(os.path.join(fhir_dir, '{}.json'.format(questionnaire_id))) as f:

        # Load the file
        questionnaire = json.loads(f.read())

        # Get the exception items
        texts = [item['text'] for item in questionnaire['item'] if item['type'].lower() == 'boolean']

        # Set the codes and the relevant section of text
        codes = {
            '82078001': 'BLOOD SAMPLE',
            '165334004': 'STOOL SAMPLE',
            '258435002': 'TUMOR SAMPLES',
            '284036006': 'FITBIT',
            '702475000': 'ADDITIONAL QUESTIONNAIRES',
            '225098009': 'SALIVA SAMPLE',
        }

        # Build the choices tuple
        choices = []
        for text in texts:

            # Get the code
            code = next(key for key, value in codes.items() if value in text)

            # Add emphasis to 'DO NOT'
            label = text.replace('I DO NOT', 'I <strong><em>DO NOT</em></strong>')

            # Add it
            choices.append((code, mark_safe(label)))

        # Return the field
        return forms.MultipleChoiceField(
            required=False,
            widget=forms.CheckboxSelectMultiple,
            choices=tuple(choices),
        )


def _quiz_fields(questionnaire_id):
    '''
    Takes the id of a Questionnaire resource and returns the form fields
    rekated to the quiz question items. All questions are assumed to be
    single choice items rendered as radio inputs. Returns a dictionary
    of form fields keyed by the question's linkId.
    :param questionnaire_id: FHIR resource ID
    :return: dict
    '''
    # Open resource
    fhir_dir = os.path.join(os.path.dirname(settings.STATIC_ROOT), ConsentConfig.name, 'fhir')
    with open(os.path.join(fhir_dir, '{}.json'.format(questionnaire_id))) as f:

        # Load the file
        quiz = json.loads(f.read())

        # Get questions and answers
        fields = {}
        for question in quiz['item']:
            fields[question['linkId']] = forms.ChoiceField(
                label=question['text'],
                required=True,
                widget=forms.RadioSelect,
                choices=tuple([(option['valueString'], option['valueString']) for option in question["answerOption"]])
            )

        return fields


def get_form_for_study(study):
    """
    Returns the class of form to be used for the study. The study must be a valid PPM study and a Form
    class must exist for it, or else an error is raised.
    :param study: The PPM study
    :type study: PPM.Study
    :return: A subclass of forms.Form
    :rtype: forms.Form.__class__
    """
    form_class = next(iter([cls for cls in forms.Form.__subclasses__() if hasattr(cls, 'study')
                            and getattr(cls, 'study') == PPM.Study.enum(study)]), None)
    if not form_class:
        raise ValueError(f'"{study}" is either an invalid PPM study, or no form subclass yet exists for it')

    return form_class


class NEERSignatureForm(forms.Form):

    study = PPM.Study.NEER
    exceptions = _exception_choices(PPM.Questionnaire.consent_questionnaire_for_study(PPM.Study.NEER))

    name = forms.CharField(label='Name of participant',
                           required=True,
                           widget=forms.TextInput(attrs={'class': 'form-control'})
                           )
    signature = forms.CharField(label='Signature of participant (Please type your name)',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    date = forms.DateField(label='Date',
                           required=True,
                           input_formats=["%m/%d/%Y"],
                           initial=datetime.date.today,
                           widget=SignatureDatePickerInput(attrs={'required': 'required'})
                           )


class RANTSignatureForm(forms.Form):

    study = PPM.Study.RANT

    name = forms.CharField(label='Name of participant',
                           required=True,
                           widget=forms.TextInput(attrs={'class': 'form-control'})
                           )
    signature = forms.CharField(label='Signature of participant (Please type your name)',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    date = forms.DateField(label='Date',
                           required=True,
                           input_formats=["%m/%d/%Y"],
                           initial=datetime.date.today,
                           widget=SignatureDatePickerInput()
                           )


class EXAMPLESignatureForm(forms.Form):

    study = PPM.Study.EXAMPLE
    exceptions = _exception_choices(PPM.Questionnaire.consent_questionnaire_for_study(PPM.Study.EXAMPLE))

    name = forms.CharField(label='Name of participant',
                           required=True,
                           widget=forms.TextInput(attrs={'class': 'form-control'})
                           )
    signature = forms.CharField(label='Signature of participant (Please type your name)',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    date = forms.DateField(label='Date',
                           required=True,
                           input_formats=["%m/%d/%Y"],
                           initial=datetime.date.today,
                           widget=SignatureDatePickerInput()
                           )


class ASDTypeForm(forms.Form):

    TYPE_CHOICES = (
        ('0', 'If you are a parent or legal guardian consenting for a minor or individual in your care '
              'who is unable to consent for himself or herself, choose this option.'),
        ('1', 'If you are an individual over the age of 18 years with autism or ASD and are interested '
              'in participating in this study, choose this option.')
    )

    individual = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: bool(int(x)),
        widget=forms.RadioSelect,
        choices=TYPE_CHOICES,
    )

    _unused_ = forms.DateField(
        required=False,
        input_formats=["%m/%d/%Y"],
        initial=datetime.date.today,
        widget=SignatureDatePickerInput()
    )


class ASDGuardianQuiz(forms.Form):

    resource = 'ppm-asd-consent-guardian-quiz'

    def __init__(self, *args, **kwargs):
        super(ASDGuardianQuiz, self).__init__(*args, **kwargs)

        # Get fields
        self.fields = _quiz_fields(self.resource)


class ASDIndividualQuiz(forms.Form):

    resource = 'ppm-asd-consent-individual-quiz'

    def __init__(self, *args, **kwargs):
        super(ASDIndividualQuiz, self).__init__(*args, **kwargs)

        # Get fields
        self.fields = _quiz_fields(self.resource)


class ASDIndividualSignatureForm(forms.Form):

    exceptions = _exception_choices('individual-signature-part-1')

    name = forms.CharField(label='Name of participant',
                           required=True,
                           widget=forms.TextInput(attrs={'class': 'form-control'})
                           )
    signature = forms.CharField(label='Signature of participant (Please type your name)',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    date = forms.DateField(label='Date',
                           required=True,
                           input_formats=["%m/%d/%Y"],
                           initial=datetime.date.today,
                           widget=SignatureDatePickerInput()
                           )


class ASDGuardianSignatureForm(forms.Form):

    RELATIONSHIP_CHOICES = (
        ('Parent/Legal Guardian', 'Parent/Legal Guardian'),
        ('Healthcare Proxy', 'Healthcare Proxy'),
        ('Other', 'Other'),
    )

    EXPLAINED_CHOICES = (
        ('yes', 'I acknowledge that I have explained this study to my child or individual in my care who will be participating.'),
        ('no', 'I was not able to explain this study to my child or individual in my care who will be participating.')
    )

    exceptions = _exception_choices('guardian-signature-part-1')

    name = forms.CharField(label='Name of participant',
                           required=True,
                           widget=forms.TextInput(attrs={'class': 'form-control'})
                           )
    guardian = forms.CharField(label='Your name',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    relationship = forms.ChoiceField(label='Relationship with participant',
                                     required=True,
                                     choices=RELATIONSHIP_CHOICES
                                     )

    signature = forms.CharField(label='Signature of parent or authorized caregiver (Please type your name)',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )

    explained = forms.ChoiceField(required=True, widget=forms.RadioSelect(), choices=EXPLAINED_CHOICES)

    reason = forms.CharField(label='The reason for this is (e.g., too young, not cognitively able to '
                                   'comprehend study procedures and risks, etc.):',
                             required=False,
                             widget=forms.TextInput(attrs={'class': 'form-control'})
                             )

    explained_signature = forms.CharField(label='Parent or caregiver signature (Typing your name acts as your signature):',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    date = forms.DateField(label='Date',
                           required=True,
                           input_formats=["%m/%d/%Y"],
                           initial=datetime.date.today,
                           widget=SignatureDatePickerInput()
                           )


class ASDWardSignatureForm(forms.Form):

    exceptions = _exception_choices('guardian-signature-part-3')

    signature = forms.CharField(label='Signature of participant (Please type your name)',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    date = forms.DateField(label='Date',
                           required=True,
                           input_formats=["%m/%d/%Y"],
                           initial=datetime.date.today,
                           widget=SignatureDatePickerInput()
                           )
