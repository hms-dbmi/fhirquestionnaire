from django import forms
from django.conf import settings

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, HTML

from fhirclient import client
from fhirclient.server import FHIRNotFoundException
from fhirclient.models.questionnaire import Questionnaire

from fhirquestionnaire.fhir import FHIR

import logging
logger = logging.getLogger(__name__)


class FHIRQuestionnaireForm(forms.Form):
    '''
    Builds a form from a FHIR Questionnaire resource. Attempts to build fields and inputs
    according to the resource
    '''
    questionnaire_id = None
    questionnaire = None

    def __init__(self, questionnaire_id, *args, **kwargs):
        super(FHIRQuestionnaireForm, self).__init__(*args, **kwargs)

        try:
            # Prepare the client
            fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

            # Get the questionnaire
            questionnaire = Questionnaire.read(questionnaire_id, fhir.server)

            # Retain it
            self.questionnaire_id = questionnaire_id
            self.questionnaire = questionnaire

        except FHIRNotFoundException:
            raise FHIR.QuestionnaireDoesNotExist

        # Get fields
        self.fields = FHIRQuestionnaireForm._get_form_fields(questionnaire.item, questionnaire_id)
        self.fields['questionnaire_id'] = forms.CharField(empty_value=questionnaire_id, widget=forms.HiddenInput)

    @staticmethod
    def _get_form_fields(items, questionnaire_id):

        # Set fields
        fields = {}
        for item in items:

            # Check type
            if item.type == 'string' or item.type == 'text':

                # Check for options
                if item.option:

                    # Set the choices
                    choices = ()
                    for option in item.option:

                        # Assume valueString
                        if not option.valueString:
                            logger.error('Unsupported choice type for question on Questionnaire',
                                         extra={'questionnaire': questionnaire_id, 'question': item.linkId,})
                        else:
                            choices = choices + ((option.valueString, option.valueString),)

                    # Set the input
                    fields[item.linkId] = forms.TypedChoiceField(
                        label=item.text,
                        choices=choices,
                        widget=forms.RadioSelect(attrs={"required": "required"} if item.required else {}),
                        required=item.required
                    )

                elif item.initialString:

                    # Make this a textbox-style input with minimum width
                    fields[item.linkId] = forms.CharField(label=item.text,
                                                          required=item.required,
                                                          widget=forms.Textarea(attrs={
                                                              'placeholder': item.initialString,
                                                              'pattern': ".{6,}",
                                                              'title': 'Please be as descriptive as possible for this question',
                                                              'oninvalid': "setCustomValidity('Please be as "
                                                                           "descriptive as possible for "
                                                                           "this question')",
                                                              'oninput': "setCustomValidity('')",
                                                          }))

                else:

                    # Plain old text field
                    fields[item.linkId] = forms.CharField(label=item.text, required=item.required)

            elif item.type == 'date':

                # Just do a text field for now.
                fields[item.linkId] = forms.CharField(label=item.text, required=item.required)

            elif item.type == 'boolean':

                fields[item.linkId] = forms.TypedChoiceField(
                    label=item.text,
                    coerce=lambda x: bool(int(x)),
                    choices=((1, 'Yes'), (0, 'No')),
                    widget=forms.RadioSelect(attrs={"required": "required"} if item.required else {}),
                    required=True
                )

            elif item.type == 'choice':

                # Set the choices
                choices = ()
                for option in item.option:

                    # Assume valueString
                    if not option.valueString:
                        logger.error('Unsupported choice type for question on Questionnaire',
                                     extra={'questionnaire': questionnaire_id, 'question': item.linkId,})
                    else:
                        choices = choices + ((option.valueString, option.valueString),)

                # Set the input
                fields[item.linkId] = forms.TypedChoiceField(
                    label=item.text,
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple,
                    required=item.required
                )

            elif item.type == 'question':

                # Set the choices
                choices = ()
                for option in item.option:

                    # Assume valueString
                    if not option.valueString:
                        logger.error('Unsupported choice type for question on Questionnaire',
                                     extra={'questionnaire': questionnaire_id, 'question': item.linkId,})
                    else:
                        choices = choices + ((option.valueString, option.valueString),)

                # Check if repeats
                if item.repeats:
                    # Set the input
                    fields[item.linkId] = forms.MultipleChoiceField(
                        label=item.text,
                        choices=choices,
                        widget=forms.CheckboxSelectMultiple(attrs={'data-details': '{}'.format(item.linkId) if item.item else ''}),
                        required=item.required
                    )

                else:
                    # Set the input
                    fields[item.linkId] = forms.TypedChoiceField(
                        label=item.text,
                        choices=choices,
                        widget=forms.RadioSelect(attrs={"required": "required"} if item.required else {}),
                        required=item.required
                    )

                # Check for subitems
                if item.item:

                    # Add them
                    for subitem in item.item:

                        # Build Input attributes
                        attrs = {'class': 'inline-checkbox',
                                 'data-parent': item.linkId,
                                 'data-required': subitem.required,
                                 'id': 'id_{}_{}'.format(item.linkId, subitem.linkId)
                                 }
                        for enable_when in subitem.enableWhen:
                            attrs['data-enabled-when'] = '{}={}'.format(enable_when.question, enable_when.answerString)

                        # Check for text
                        if subitem.text:
                            attrs['placeholder'] = subitem.text

                        # Plain old text field
                        fields[subitem.linkId] = forms.CharField(
                            required=False,
                            label=False,
                            widget=forms.TextInput(attrs=attrs))

            elif item.type == 'group':

                # Process the group
                fields.update(FHIRQuestionnaireForm._get_form_fields(item.item, questionnaire_id))

            elif item.type == 'display':
                # Nothing to do here
                pass

            else:
                logger.error('Unsupported question type on Questionnaire',
                             extra={'questionnaire': questionnaire_id, 'question': item.linkId, 'type': item.type})
                continue

        return fields


class NEERQuestionnaireForm(FHIRQuestionnaireForm):

    def __init__(self, questionnaire_id, *args, **kwargs):
        super(NEERQuestionnaireForm, self).__init__(questionnaire_id, *args, **kwargs)

        # Create the crispy helper
        self.helper = FormHelper(self)
        self.helper.form_method = 'POST'

        # Set the layout
        self.helper.layout = NEERQuestionnaireForm._get_form_layout(self.questionnaire.item)

        # Add a submit button
        self.helper.layout.append(ButtonHolder(Submit('submit', 'Submit', css_class='btn btn-primary')))

    @staticmethod
    def _get_form_layout(items):

        # Collect them
        layout = Layout()

        # Get all the not groups
        for item in items:

            # Check type
            if item.type == 'group':

                # Add the fieldset
                layout.append(NEERQuestionnaireForm._get_form_fieldset(item.item, item.text))

            elif item.type == 'display':

                # Add the text
                layout.append(HTML('<p>{}</p>'.format(item.text)))

            else:

                # Add the linkId
                layout.append(item.linkId)

        return Layout(layout)

    @staticmethod
    def _get_form_fieldset(items, text):

        # Collect them
        fieldset = Fieldset(text)

        # Get all the not groups
        for item in items:

            # Check type
            if item.type == 'group':

                # Add those group items
                fieldset.append(NEERQuestionnaireForm._get_form_fieldset(item.item, item.text))

            elif item.type == 'display':

                # Add the text
                fieldset.append(HTML('<p>{}</p>'.format(item.text)))

            else:

                # Add the linkId
                fieldset.append(item.linkId)

        return fieldset


class ASDQuestionnaireForm(FHIRQuestionnaireForm):

    def __init__(self, questionnaire_id, *args, **kwargs):
        super(ASDQuestionnaireForm, self).__init__(questionnaire_id, *args, **kwargs)

        # Create the crispy helper
        self.helper = FormHelper(self)
        self.helper.form_method = 'POST'

        # Set the layout
        self.helper.layout = Layout(
            'question-1',
            HTML('<h4>From now on we will call the person you selected above the study Subject.</h4><hr />'),
            'question-2',
            'question-3',
            'question-3-1',
            'question-3-2',
            'question-3-3',
            'question-3-4',
            'question-3-5',
            'question-3-6',
            'question-4',
            'question-4-1',
            'question-4-2',
            'question-4-3',
            'question-4-4',
            'question-4-5',
            ButtonHolder(Submit('submit', 'Submit', css_class='btn btn-primary'))
        )

