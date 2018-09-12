#!/bin/bash -e

# Check for static files
if [[ -n $PPM_STATIC_FILES ]]; then

    # Make the directory and collect static files
    mkdir -p "$PPM_APP_STATIC_ROOT"
    python ${PPM_APP_ROOT}/manage.py collectstatic --no-input  > /dev/null 2>&1

fi

