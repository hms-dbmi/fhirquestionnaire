FROM python:3.5-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        jq \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install some pip packages
RUN pip install awscli

# Configure NGINX
RUN rm -rf /etc/nginx/sites-available/default
RUN mkdir /etc/nginx/ssl/
RUN chmod 710 /etc/nginx/ssl/
COPY site.conf /etc/nginx/sites-available/site.conf
RUN ln -s /etc/nginx/sites-available/site.conf /etc/nginx/sites-enabled/site.conf

# Setup entry scripts
RUN mkdir /docker-entrypoint.d/
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod u+x /docker-entrypoint.sh

# Set the environment
ENV FHIR_APP_ID ppm-fhir-questionnaire-app

# Install application requirements
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY . /app

ENTRYPOINT ["/docker-entrypoint.sh"]