FROM python:3.6-slim AS builder

# Install python requirements
COPY requirements.txt /requirements.txt

# Install requirements
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        bzip2 \
        libfontconfig \
        libmariadbclient-dev \
        g++ libssl-dev \
    && pip install -r /requirements.txt

# Install requirements for PDF generation
RUN mkdir /tmp/phantomjs \
    && curl -L https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2 \
           | tar -xj --strip-components=1 -C /tmp/phantomjs

FROM hmsdbmitc/dbmisvc:3.6-slim

# Install python requirements
COPY requirements.txt /requirements.txt

# Install requirements
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libfontconfig \
        libmariadbclient-dev

# Copy pip packages from builder
COPY --from=builder /root/.cache /root/.cache

# Install Python packages
RUN pip install -r /requirements.txt

# Copy PhantomJS binary
COPY --from=builder /tmp/phantomjs/bin/phantomjs /usr/local/bin/phantomjs

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
