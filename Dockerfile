FROM hmsdbmitc/dbmisvc:debian11-slim-python3.10-0.4.0 AS builder

# Install requirements
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        bzip2 \
        gcc \
        libssl-dev \
        libfontconfig \
    && rm -rf /var/lib/apt/lists/*

# Install requirements for PDF generation
RUN mkdir /tmp/phantomjs \
    && curl -L https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2 \
           | tar -xj --strip-components=1 -C /tmp/phantomjs

# Add requirements
ADD requirements.* /

# Build Python wheels with hash checking
RUN pip install -U wheel \
    && pip wheel -r /requirements.txt \
        --wheel-dir=/root/wheels

FROM hmsdbmitc/dbmisvc:debian11-slim-python3.10-0.4.0

# Copy PhantomJS binary
COPY --from=builder /tmp/phantomjs/bin/phantomjs /usr/local/bin/phantomjs

# Copy Python wheels from builder
COPY --from=builder /root/wheels /root/wheels

# Install requirements
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libfontconfig \
    && rm -rf /var/lib/apt/lists/*

# Add requirements files
ADD requirements.* /

# Install Python packages from wheels
RUN pip install --no-index \
        --find-links=/root/wheels \
        --force-reinstall \
        # Use requirements without hashes to allow using wheels.
        # For some reason the hashes of the wheels change between stages
        # and Pip errors out on the mismatches.
        -r /requirements.in

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
