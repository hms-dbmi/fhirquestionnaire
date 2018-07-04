from django import forms
from django.conf import settings

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit

from fhirclient import client
from fhirclient.server import FHIRNotFoundException
from fhirclient.models.questionnaire import Questionnaire

from questionnaire.fhir import FHIR

import logging
logger = logging.getLogger(__name__)


class QuestionnaireForm(forms.Form):

    def __init__(self, questionnaire_id, *args, **kwargs):
        super(QuestionnaireForm, self).__init__(*args, **kwargs)

        try:
            # Prepare the client
            fhir = client.FHIRClient(settings={'app_id': settings.FHIR_APP_ID, 'api_base': settings.FHIR_URL})

            # Get the questionnaire
            questionnaire = Questionnaire.read(questionnaire_id, fhir.server)

        except FHIRNotFoundException:
            raise FHIR.QuestionnaireDoesNotExist

        # Get fields
        self.fields = QuestionnaireForm._get_form_fields(questionnaire.item, questionnaire_id)

        # Create the crispy helper
        self.helper = FormHelper(self)
        self.helper.form_method = 'POST'

        # Set the layout
        self.helper.layout = QuestionnaireForm._get_form_layout(questionnaire.item)

        # Add a submit button
        self.helper.layout.append(ButtonHolder(Submit('submit', 'Submit', css_class='btn btn-primary')))

    @staticmethod
    def _get_form_fields(items, questionnaire_id):

        # Set fields
        fields = {}
        for item in items:

            # Check type
            if item.type == 'text':

                # Check for options
                if item.option:

                    # Set the choices
                    choices = ()
                    for option in item.option:

                        # Assume valueString
                        if not option.valueString:
                            logger.error(
                                '{}: Unsupported choice type for question {}'.format(questionnaire_id, item.linkId))
                        else:
                            choices = choices + ((option.valueString, option.valueString),)

                    # Set the input
                    fields[item.linkId] = forms.TypedChoiceField(
                        label=item.text,
                        choices=choices,
                        widget=forms.RadioSelect(attrs={"required": "required"}),
                        required=item.required
                    )

                else:

                    fields[item.linkId] = forms.CharField(label=item.text, required=item.required)

            elif item.type == 'date':

                # Just do a text field for now.
                fields[item.linkId] = forms.CharField(label=item.text, required=item.required)

            elif item.type == 'boolean':

                fields[item.linkId] = forms.TypedChoiceField(
                    label=item.text,
                    coerce=lambda x: bool(int(x)),
                    choices=((0, 'No'), (1, 'Yes')),
                    widget=forms.RadioSelect(attrs={"required": "required"}),
                    required=True
                )

            elif item.type == 'choice':

                # Set the choices
                choices = ()
                for option in item.option:

                    # Assume valueString
                    if not option.valueString:
                        logger.error(
                            '{}: Unsupported choice type for question {}'.format(questionnaire_id, item.linkId))
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
                        logger.error(
                            '{}: Unsupported choice type for question {}'.format(questionnaire_id, item.linkId))
                    else:
                        choices = choices + ((option.valueString, option.valueString),)

                # Check if repeats
                if item.repeats:
                    # Set the input
                    fields[item.linkId] = forms.TypedChoiceField(
                        label=item.text,
                        choices=choices,
                        widget=forms.CheckboxSelectMultiple,
                        required=item.required
                    )
                else:
                    # Set the input
                    fields[item.linkId] = forms.TypedChoiceField(
                        label=item.text,
                        choices=choices,
                        widget=forms.RadioSelect,
                        required=item.required
                    )

            elif item.type == 'group':

                # Process the group
                fields.update(QuestionnaireForm._get_form_fields(item.item, questionnaire_id))

            else:
                logger.error('{}: Unsupported type {} for question {}'.format(questionnaire_id, item.type, item.linkId))
                continue

        return fields

    @staticmethod
    def _get_form_layout(items):

        # Collect them
        layout = Layout()

        # Get all the not groups
        for item in items:

            # Check type
            if item.type == 'group':

                # Add the fieldset
                layout.append(QuestionnaireForm._get_form_fieldset(item.item, item.text))

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
                fieldset.append(QuestionnaireForm._get_form_fieldset(item.item, item.text))

            else:

                # Add the linkId
                fieldset.append(item.linkId)

        return fieldset