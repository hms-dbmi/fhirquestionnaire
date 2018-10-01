FROM python:3.6-alpine3.8 AS builder

# Install dependencies
RUN apk add --update \
    build-base \
    g++ \
    openssl-dev \
    libffi-dev

# Add requirements
ADD requirements.txt /requirements.txt

# Install Python packages
RUN pip install -r /requirements.txt

FROM hmsdbmitc/dbmisvc:3.6-alpine

RUN apk add --no-cache --update \
    bash \
    nginx \
    curl \
    openssl \
    jq \
  && rm -rf /var/cache/apk/*

# Copy pip packages from builder
COPY --from=builder /root/.cache /root/.cache

# Add requirements
ADD requirements.txt /requirements.txt

# Install Python packages
RUN pip install -r /requirements.txt

# Add additional init scripts
COPY docker-entrypoint-init.d/* /docker-entrypoint-init.d/

# Copy app source
COPY /app /app

# Set the build env
ENV DBMI_ENV=prod

# Set app parameters
ENV DBMI_PARAMETER_STORE_PREFIX=ppm.questionnaire.${DBMI_ENV}
ENV DBMI_PARAMETER_STORE_PRIORITY=true
ENV DBMI_AWS_REGION=us-east-1

ENV DBMI_APP_WSGI=fhirquestionnaire
ENV DBMI_APP_ROOT=/app
ENV DBMI_APP_DOMAIN=p2m2.dbmi.hms.harvard.edu

# Static files
ENV DBMI_STATIC_FILES=true
ENV DBMI_APP_STATIC_URL_PATH=/fhirquestionnaire/static
ENV DBMI_APP_STATIC_ROOT=/app/static

# Set nginx and network parameters
ENV DBMI_LB=true
ENV DBMI_SSL=true
ENV DBMI_CREATE_SSL=true
ENV DBMI_SSL_PATH=/etc/nginx/ssl

ENV DBMI_HEALTHCHECK=true
ENV DBMI_HEALTHCHECK_PATH=/healthcheck
ENV DBMI_APP_HEALTHCHECK_PATH=/healthcheck
