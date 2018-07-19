import datetime
from django import forms
from django.conf import settings
from django.template.defaultfilters import mark_safe

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, HTML, Hidden, Div
from crispy_forms.bootstrap import FormActions, Field

from fhirclient import client
from fhirclient.server import FHIRNotFoundException
from fhirclient.models.questionnaire import Questionnaire

from fhirquestionnaire.fhir import FHIR

import logging
logger = logging.getLogger(__name__)


class NEERSignatureForm(forms.Form):

    EXCEPTION_CHOICES = (
        ('82078001', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO PROVIDE A BLOOD SAMPLE FOR THIS STUDY.')),
        ('165334004', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO PROVIDE A STOOL SAMPLE FOR THIS STUDY.')),
        ('258435002', mark_safe(
            'I <strong><em>DO NOT</em></strong> GIVE PERMISSION FOR MY EXISTING TUMOR SAMPLES TO BE USED FOR THIS STUDY.')),
        ('284036006', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO WEAR A FITBIT™ FOR THIS STUDY.')),
        ('702475000', mark_safe(
            'I <strong><em>DO NOT</em></strong> WISH TO BE CONTACTED WITH ADDITIONAL QUESTIONNAIRES FOR THIS STUDY.')),
    )

    exceptions = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=EXCEPTION_CHOICES,
    )

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
                           widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                           initial=datetime.date.today
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


class ASDGuardianQuiz(forms.Form):

    QUESTION_1_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    QUESTION_2_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    QUESTION_3_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    QUESTION_4_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    def __init__(self, *args, **kwargs):
        super(ASDGuardianQuiz, self).__init__(*args, **kwargs)

        # Set fields
        self.fields['question-1'] = forms.ChoiceField(
                                                      label='In this consent, which is TRUE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_1_CHOICES,
                                                    )

        # Set fields
        self.fields['question-2'] = forms.ChoiceField(
                                                      label='In this consent, which is TRUE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_2_CHOICES,
                                                    )

        # Set fields
        self.fields['question-3'] = forms.ChoiceField(
                                                      label='In this consent, which is FALSE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_3_CHOICES,
                                                    )

        # Set fields
        self.fields['question-4'] = forms.ChoiceField(
                                                      label='In this consent, which is FALSE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_4_CHOICES,
                                                    )


class ASDIndividualQuiz(forms.Form):

    QUESTION_1_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    QUESTION_2_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    QUESTION_3_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    QUESTION_4_CHOICES = (
        ('You agreed that you could be contacted in the future.', 'You agreed that you could be contacted in the future.'),
        ('You agreed to call us with yearly updates.', 'You agreed to call us with yearly updates.'),
        ('You agreed to send us monthly lists of your medications.', 'You agreed to send us monthly lists of your medications.'),
    )

    def __init__(self, *args, **kwargs):
        super(ASDIndividualQuiz, self).__init__(*args, **kwargs)

        # Set fields
        self.fields['question-1'] = forms.ChoiceField(
                                                      label='In this consent, which is TRUE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_1_CHOICES,
                                                    )

        # Set fields
        self.fields['question-2'] = forms.ChoiceField(
                                                      label='In this consent, which is TRUE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_2_CHOICES,
                                                    )

        # Set fields
        self.fields['question-3'] = forms.ChoiceField(
                                                      label='In this consent, which is FALSE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_3_CHOICES,
                                                    )

        # Set fields
        self.fields['question-4'] = forms.ChoiceField(
                                                      label='In this consent, which is FALSE?',
                                                      required=True,
                                                      widget=forms.RadioSelect,
                                                      choices=self.QUESTION_4_CHOICES,
                                                    )


class ASDIndividualSignatureForm(forms.Form):

    EXCEPTION_CHOICES = (
        ('225098009', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO PROVIDE A SALIVA SAMPLE FOR THIS STUDY.')),
        ('284036006', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO WEAR A FITBIT™ FOR THIS STUDY.')),
        ('702475000', mark_safe(
            'I <strong><em>DO NOT</em></strong> WISH TO BE CONTACTED WITH ADDITIONAL QUESTIONNAIRES FOR THIS STUDY.')),
    )

    exceptions = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=EXCEPTION_CHOICES,
    )

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
                           widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                           initial=datetime.date.today
                           )


class ASDGuardianSignatureForm(forms.Form):

    EXCEPTION_CHOICES = (
        ('225098009', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO HAVE MY CHILD PROVIDE A SALIVA SAMPLE FOR THIS STUDY.')),
        ('284036006', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO HAVE MY CHILD WEAR A FITBIT™ FOR THIS STUDY.')),
        ('702475000', mark_safe(
            'I <strong><em>DO NOT</em></strong> WISH TO BE CONTACTED WITH ADDITIONAL QUESTIONNAIRES ABOUT MY CHILD FOR THIS STUDY.')),
    )

    RELATIONSHIP_CHOICES = (
        ('Parent/Legal Guardian', 'Parent/Legal Guardian'),
        ('Healthcare Proxy', 'Healthcare Proxy'),
        ('Other', 'Other'),
    )

    EXPLAINED_CHOICES = (
        ('yes', 'I acknowledge that I have explained this study to my child or individual in my care who will be participating.'),
        ('no', 'I was not able to explain this study to my child or individual in my care who will be participating.')
    )

    exceptions = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=EXCEPTION_CHOICES,
    )

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
                           widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                           initial=datetime.date.today
                           )


class ASDWardSignatureForm(forms.Form):

    EXCEPTION_CHOICES = (
        ('225098009', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO PROVIDE A SALIVA SAMPLE FOR THIS STUDY.')),
        ('284036006', mark_safe('I <strong><em>DO NOT</em></strong> WISH TO WEAR A FITBIT™ FOR THIS STUDY.')),
    )

    exceptions = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=EXCEPTION_CHOICES,
    )

    signature = forms.CharField(label='Signature of participant (Please type your name)',
                                required=True,
                                widget=forms.TextInput(attrs={'class': 'form-control'})
                                )
    date = forms.DateField(label='Date',
                           required=True,
                           widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                           initial=datetime.date.today
                           )