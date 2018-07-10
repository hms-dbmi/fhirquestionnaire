import datetime
from django import forms
from django.conf import settings

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit

from fhirclient import client
from fhirclient.server import FHIRNotFoundException
from fhirclient.models.questionnaire import Questionnaire

from fhirquestionnaire.fhir import FHIR

import logging
logger = logging.getLogger(__name__)