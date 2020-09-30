from datetime import datetime
from datetime import timedelta

from django import forms
from django.utils import formats
from django.utils import timezone
from django.conf import settings
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, HTML, Div, Field
from bootstrap_datepicker_plus import DatePickerInput, MonthPickerInput
from django.utils.translation import gettext_lazy as _, ngettext_lazy

from fhirclient import client
from fhirclient.server import FHIRNotFoundException
from fhirclient.models.questionnaire import Questionnaire
from ppmutils.ppm import PPM

from fhirquestionnaire.fhir import FHIR

import logging
logger = logging.getLogger(__name__)


def get_form_for_study(study):
    """
    Returns the class of form to be used for the study. The study must be a valid PPM study and a Form
    class must exist for it, or else an error is raised.
    :param study: The PPM study
    :type study: PPM.Study
    :return: A subclass of FHIRQuestionnaireForm
    :rtype: FHIRQuestionnaireForm.__class__
    """
    form_class = next(iter([cls for cls in FHIRQuestionnaireForm.__subclasses__() if hasattr(cls, 'study')
                            and getattr(cls, 'study') == PPM.Study.enum(study)]), None)
    if not form_class:
        raise ValueError(f'"{study}" is either an invalid PPM study, or no form subclass yet exists for it')

    return form_class


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
        self.fields = self._get_form_fields(questionnaire, questionnaire_id)
        self.fields['questionnaire_id'] = forms.CharField(empty_value=questionnaire_id, widget=forms.HiddenInput)

        # Create the crispy helper
        self.helper = FormHelper(self)
        self.helper.form_method = 'POST'

        # Set the layout
        self.helper.layout = self._get_form_layout(self.questionnaire.item)

        # Add a submit button
        self.helper.layout.append(ButtonHolder(Submit('submit', 'Submit', css_class='btn btn-primary')))

    def _get_parent_item(self, linkId, parent=None):
        """
        Searches the FHIR questionnaire and returns the parent of the given item if it exists
        """
        logger.debug(f'Searching: {parent.linkId if parent else None} for {linkId}')
        # Iterate items
        if not parent:
            for item in self.questionnaire.item:

                # Check for root
                if item.linkId == linkId:
                    return None

                # Search list
                parent = self.questionnaire

        # Return parent if found
        for item in parent.item:
            if item.linkId == linkId:
                return parent

            # Check for children
            if item.item:
                parent_item = self._get_parent_item(linkId, item)
                if parent_item:
                    return parent_item

    def _get_dependent_items(self, linkId, parent=None):
        """
        Searches the FHIR questionnaire and returns the items which depend on the passed item
        """
        # Collect items
        items = []

        # Iterate items
        if not parent:

            # Search list
            parent = self.questionnaire

        # Return parent if found
        for item in parent.item:

            # Check sub items
            if item.item:
                items.extend(self._get_dependent_items(linkId, item))

            # Check for dependency
            if item.enableWhen and next((e for e in item.enableWhen if e.question == linkId), None):
                items.append(item)

        return items

    def _get_form_fields(self, parent, questionnaire_id):

        # Set fields
        fields = {}
        for item in parent.item:

            # Required items are only truly required if root
            required = item.required and not item.enableWhen and not (hasattr(parent, 'enableWhen') and parent.enableWhen)

            # Set widget attributes
            attrs = {
                'data-required': 'true' if item.required else 'false',
            }
            if required:
                # Only set widgets as hard required if they are root level items
                attrs['required'] = 'required'

            # Check for dependent items
            if self._get_dependent_items(item.linkId):
                attrs['data-details'] = item.linkId

            # Check type
            if (item.type == 'string' or item.type == 'text') and item.option:

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
                    widget=forms.RadioSelect(attrs=attrs),
                    required=item.required
                )

            elif item.type == 'string' or item.type == 'text' or (item.type == 'question' and not item.option):

                if item.initialString:

                    # Make this a textbox-style input with minimum width
                    fields[item.linkId] = forms.CharField(
                        label=item.text,
                        required=item.required,
                        widget=forms.Textarea(attrs={**{
                            'placeholder': item.initialString,
                            'pattern': ".{6,}",
                            'title': 'Please be as descriptive as possible for this question',
                            'oninvalid': "setCustomValidity('Please be as "
                                        "descriptive as possible for "
                                        "this question')",
                            'oninput': "setCustomValidity('')",
                        }, **attrs})
                    )

                else:

                    # Plain old text field
                    fields[item.linkId] = forms.CharField(
                        label=item.text,
                        required=required,
                        widget=forms.TextInput(attrs=attrs)
                    )

            elif item.type == 'date':

                # Determine types
                month_year = False

                # Check for coding on type of picker
                if item.code:
                    for code in [c.code for c in item.code if c.system == FHIR.input_type_system]:

                        # Check type of picker
                        if code == 'month-year':
                            month_year = True

                # Set options
                max_date = timezone.now().replace(hour=23, minute=59).strftime("%Y-%m-%dT%H:%M:%S")
                options = {
                    'maxDate': max_date,
                    'useCurrent': False,
                }

                # Create widget
                if month_year:
                    widget = MonthPickerInput(
                        format='%m/%Y',
                        options=options,
                        attrs=attrs,
                    )
                else:
                    widget = DatePickerInput(
                        format='%m/%d/%Y',
                        options=options,
                        attrs=attrs,
                    )

                # Check for coding on ranges
                if item.code:
                    for code in [c.code for c in item.code if c.system == FHIR.input_range_system]:

                        # Check linking
                        if code.startswith('start-of|'):

                            # Set it
                            widget = widget.start_of(code.split('|')[1])

                        elif code.startswith('end-of|'):

                            # Set it
                            widget = widget.end_of(code.split('|')[1])


                # Check for date or month field
                if month_year:
                    # Setup the month field
                    fields[item.linkId] = forms.DateField(
                        input_formats=["%m/%Y"],
                        widget=widget,
                        label=item.text,
                        required=required
                    )

                else:
                    # Setup the date field
                    fields[item.linkId] = forms.DateField(
                        widget=widget,
                        label=item.text,
                        required=required
                    )

            elif item.type == 'boolean':

                fields[item.linkId] = forms.TypedChoiceField(
                    label=item.text,
                    coerce=lambda x: bool(int(x)),
                    choices=((1, 'Yes'), (0, 'No')),
                    widget=forms.RadioSelect(attrs=attrs),
                    required=item.required
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
                    widget=forms.CheckboxSelectMultiple(attrs=attrs),
                    required=item.required
                )

            elif item.type == 'question' and item.option:

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
                        widget=forms.CheckboxSelectMultiple(attrs=attrs),
                        required=item.required
                    )

                else:
                    # Set the input
                    fields[item.linkId] = forms.TypedChoiceField(
                        label=item.text,
                        choices=choices,
                        widget=forms.RadioSelect(attrs=attrs),
                        required=item.required
                    )

            elif item.type == 'display' or item.type == 'group':
                # Nothing to do here
                pass

            else:
                logger.warning(f'Unsupported question type on Questionnaire: {item.linkId}/{item.type}/{item.__dict__}')
                logger.error('Unsupported question type on Questionnaire',
                             extra={'questionnaire': questionnaire_id, 'question': item.linkId, 'type': item.type})
                #continue

            # Process child items
            if item.item:

                # Process the group
                fields.update(self._get_form_fields(item, questionnaire_id))

        return fields

    def _get_form_layout(self, items):

        # Collect them
        layout = Layout()

        # Get all the not groups
        for item in items:

            # Check type
            if item.type == 'group':

                # Add the fieldset
                layout.append(self._get_form_fieldset(item.item, item.text))

            elif item.type == 'display':

                # Add the text
                layout.append(HTML('<p>{}</p>'.format(item.text)))

            else:

                # Add the linkId
                layout.append(item.linkId)

        return layout

    def _get_form_fieldset(self, items, text, **attrs):

        # Collect them
        fieldset = Fieldset(text, **attrs)

        # Get all the not groups
        for item in items:

            # Check type
            if item.type == 'group':

                # Add those group items
                fieldset.append(self._get_form_fieldset(item.item, item.text))

            elif item.type == 'display':

                # Add the text
                fieldset.append(HTML('<p>{}</p>'.format(item.text)))

            else:

                # Add the linkId
                fieldset.append(item.linkId)

        return fieldset

class NEERQuestionnaireForm(FHIRQuestionnaireForm):

    # Link the form to the study
    study = PPM.Study.NEER


class RANTQuestionnaireForm(FHIRQuestionnaireForm):

    # Link the form to the study
    study = PPM.Study.RANT

    def _get_form_layout(self, items):

        # Collect them
        layout = Layout()

        # Get all the not groups
        for item in items:

            # Check type
            if item.type == 'group':

                # Add the fieldset
                layout.append(self._get_form_fieldset(item.item, item.text))

            elif item.type == 'display':

                # Add the text
                layout.append(HTML('<p>{}</p>'.format(item.text)))


            elif item.type == 'question' and item.item:

                # Add the linkId
                layout.append(item.linkId)

                # Check for groups
                for subitem in item.item:

                    # If group...
                    if subitem.type == 'group':

                        # Set attributes
                        attrs = {
                            'data_parent': item.linkId,
                            'data_detached': "true",
                            'data_required': "true" if item.required else "false",
                            'id': 'id_{}_{}'.format(item.linkId, subitem.linkId)
                        }
                        for enable_when in subitem.enableWhen:
                            attrs['data_enabled-when'] = '{}={}'.format(enable_when.question, enable_when.answerString)

                        # Add the fieldset
                        layout.append(self._get_form_fieldset(subitem.item, "", **attrs))

            else:

                # Add the linkId
                layout.append(item.linkId)

        return layout


class EXAMPLEQuestionnaireForm(FHIRQuestionnaireForm):

    # Link the form to the study
    study = PPM.Study.EXAMPLE


class ASDQuestionnaireForm(FHIRQuestionnaireForm):

    study = PPM.Study.ASD

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
            Div(
                Field('question-3-1', placeholder='Please list family members here...'),
                data_parent='question-3',
                data_required='true',
                css_id='id_question-3_question-3-1',
                data_enabled_when='question-3=Irritable Bowel Syndrome (IBS)',
                data_detached='false',
            ),
            Div(
                Field('question-3-2', placeholder='Please list family members here...'),
                data_parent='question-3',
                data_required='true',
                css_id='id_question-3_question-3-2',
                data_enabled_when='question-3=Inflammatory Bowel Disease (IBD)',
                data_detached='false',
            ),
            Div(
                Field('question-3-3', placeholder='Please list family members here...'),
                data_parent='question-3',
                data_required='true',
                css_id='id_question-3_question-3-3',
                data_enabled_when='question-3=Rheumatoid Arthritis',
                data_detached='false',
            ),
            Div(
                Field('question-3-4', placeholder='Please list family members here...'),
                data_parent='question-3',
                data_required='true',
                css_id='id_question-3_question-3-4',
                data_enabled_when='question-3=Type 1 diabetes',
                data_detached='false',
            ),
            Div(
                Field('question-3-5', placeholder='Please list family members here...'),
                data_parent='question-3',
                data_required='true',
                css_id='id_question-3_question-3-5',
                data_enabled_when='question-3=Scleroderma',
                data_detached='false',
            ),
            Div(
                Field('question-3-6', placeholder='Please list family members here...'),
                data_parent='question-3',
                data_required='true',
                css_id='id_question-3_question-3-6',
                data_enabled_when='question-3=Lupus',
                data_detached='false',
            ),
            'question-4',
            Div(
                Field('question-4-1', placeholder='Please list medications here...'),
                data_parent='question-4',
                data_required='true',
                css_id='id_question-4_question-4-1',
                data_enabled_when='question-4=Anti-anxiety medications',
                data_detached='false',
            ),
            Div(
                Field('question-4-2', placeholder='Please list medications here...'),
                data_parent='question-4',
                data_required='true',
                css_id='id_question-4_question-4-2',
                data_enabled_when='question-4=Attention Deficit Disorder (ADHD) medications',
                data_detached='false',
            ),
            Div(
                Field('question-4-3', placeholder='Please list medications here...'),
                data_parent='question-4',
                data_required='true',
                css_id='id_question-4_question-4-3',
                data_enabled_when='question-4=Anti-inflammatory medications',
                data_detached='false',
            ),
            Div(
                Field('question-4-4', placeholder='Please list medications here...'),
                data_parent='question-4',
                data_required='true',
                css_id='id_question-4_question-4-4',
                data_enabled_when='question-4=Any other medications',
                data_detached='false',
            ),
            Div(
                Field('question-4-5', placeholder='Please list medications here...'),
                data_parent='question-4',
                data_required='true',
                css_id='id_question-4_question-4-5',
                data_enabled_when='question-4=Vitamins',
                data_detached='false',
            ),
            ButtonHolder(Submit('submit', 'Submit', css_class='btn btn-primary'))
        )

