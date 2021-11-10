#!/bin/bash

# Update FHIR resources
python ${DBMI_APP_ROOT}/manage.py updatefhirconsents
python ${DBMI_APP_ROOT}/manage.py updatefhirquestionnaires
