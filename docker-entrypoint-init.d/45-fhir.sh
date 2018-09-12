#!/bin/bash

# Update FHIR resources
python ${PPM_APP_ROOT}/manage.py updatefhirconsents
python ${PPM_APP_ROOT}/manage.py updatefhirquestionnaires