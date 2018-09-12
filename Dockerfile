FROM python:3.6-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        jq \
        curl \
        openssl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install some pip packages
RUN pip install awscli boto3 gunicorn shinto-cli dumb-init

# Add requirements
ADD requirements.txt /requirements.txt

# Build and install python requirements
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    g++ \
    && pip install -r /requirements.txt && \
    apt-get remove --purge -y g++ \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y

# Copy templates
ADD docker-entrypoint-templates.d/ /docker-entrypoint-templates.d/

# Setup entry scripts
ADD docker-entrypoint-init.d/ /docker-entrypoint-init.d/
ADD docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod a+x docker-entrypoint.sh

# Copy app source
COPY /app /app

# Set the build env
ENV PPM_ENV=prod

# Set app parameters
ENV PPM_PARAMETER_STORE_PREFIX=ppm.questionnaire.${PPM_ENV}
ENV PPM_PARAMETER_STORE_PRIORITY=true
ENV PPM_AWS_REGION=us-east-1

ENV PPM_APP_ROOT=/app
ENV PPM_APP_HEALTHCHECK_PATH=/healthcheck
ENV PPM_APP_DOMAIN=p2m2.dbmi.hms.harvard.edu

# Static files
ENV PPM_STATIC_FILES=true
ENV PPM_APP_STATIC_URL_PATH=/fhirquestionnaire/static
ENV PPM_APP_STATIC_ROOT=/app/static

# Set nginx and network parameters
ENV PPM_GUNICORN_PORT=8000
ENV PPM_PORT=443
ENV PPM_NGINX_USER=www-data
ENV PPM_NGINX_PID_PATH=/var/run/nginx.pid
ENV PPM_LB=true
ENV PPM_SSL=true
ENV PPM_CREATE_SSL=true
ENV PPM_SSL_PATH=/etc/nginx/ssl

ENV PPM_HEALTHCHECK=true
ENV PPM_HEALTHCHECK_PATH=/healthcheck

ENTRYPOINT ["dumb-init", "/docker-entrypoint.sh"]

CMD gunicorn fhirquestionnaire.wsgi:application -b 0.0.0.0:${PPM_GUNICORN_PORT} \
    --user ${PPM_NGINX_USER} --group ${PPM_NGINX_USER} --chdir=${PPM_APP_ROOT}