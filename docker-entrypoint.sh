#!/bin/bash -e

export SECRET_KEY=$(aws ssm get-parameters --names $PS_PATH.secret_key --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export RETURN_URL=$(aws ssm get-parameters --names $PS_PATH.return_url --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export FHIR_URL=$(aws ssm get-parameters --names $PS_PATH.fhir_url --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export FHIR_APP_ID=$(aws ssm get-parameters --names $PS_PATH.fhir_app_id --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export RAVEN_URL=$(aws ssm get-parameters --names $PS_PATH.raven_url --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export ALLOWED_HOSTS=$(aws ssm get-parameters --names $PS_PATH.allowed_hosts --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')

export AUTH0_DOMAIN=$(aws ssm get-parameters --names $PS_PATH.auth0_domain --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export AUTH0_CLIENT_ID_LIST=$(aws ssm get-parameters --names $PS_PATH.auth0_client_id_list --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export AUTH0_SECRET=$(aws ssm get-parameters --names $PS_PATH.auth0_secret --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export AUTH0_LOGOUT_URL=$(aws ssm get-parameters --names $PS_PATH.auth0_logout_url --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export AUTH0_SUCCESS_URL=$(aws ssm get-parameters --names $PS_PATH.auth0_success_url --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export AUTHENTICATION_LOGIN_URL=$(aws ssm get-parameters --names $PS_PATH.authentication_login_url --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')

export EMAIL_HOST=$(aws ssm get-parameters --names $PS_PATH.email_host --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export EMAIL_HOST_USER=$(aws ssm get-parameters --names $PS_PATH.email_host_user --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export EMAIL_HOST_PASSWORD=$(aws ssm get-parameters --names $PS_PATH.email_host_password --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')
export EMAIL_PORT=$(aws ssm get-parameters --names $PS_PATH.email_port --with-decryption --region us-east-1 | jq -r '.Parameters[].Value')

# Specify where we will install
SSL_DIR="/etc/nginx/ssl"
mkdir -p ${SSL_DIR}

# Get the EC2 host IP
export EC2_HOST=$(wget -O - http://169.254.169.254/latest/meta-data/local-ipv4 2> /dev/null)
export ALLOWED_HOSTS=$ALLOWED_HOSTS,$EC2_HOST
echo "Running on EC2: $EC2_HOST - Updated ALLOWED_HOSTS: $ALLOWED_HOSTS"

# Set the trusted addresses for load balancers to the current subnet
EC2_MAC=$(curl -sL http://169.254.169.254/latest/meta-data/mac)
EC2_SUBNET=$(curl -sL http://169.254.169.254/latest/meta-data/network/interfaces/macs/$EC2_MAC/vpc-ipv4-cidr-blocks)
sed -i "/set_real_ip_from xxx.xxx.xxx.xxx\/xx/c\    set_real_ip_from $EC2_SUBNET;" /etc/nginx/sites-available/site.conf
sed -i "/allow xxx.xxx.xxx.xxx\/xx/c\    allow $EC2_SUBNET;" /etc/nginx/sites-available/site.conf

# A random passphrase
PASSPHRASE="$(openssl rand -base64 15)"

# Set the wildcarded domain we want to use
commonname="*.${SSL_ROOT_DOMAIN}"
country=US
state=Massachusetts
locality=Boston
organization=HMS
organizationalunit=DBMI
email=ppm@hms.harvard.edu

# Generate our Private Key, CSR and Certificate
openssl genrsa -out "$SSL_DIR/server.key" 2048
openssl req -new -key "$SSL_DIR/server.key" -out "$SSL_DIR/server.csr" -passin pass:${PASSPHRASE} -subj "/C=$country/ST=$state/L=$locality/O=$organization/OU=$organizationalunit/CN=$commonname/emailAddress=$email"
openssl x509 -req -days 365 -in "$SSL_DIR/server.csr" -signkey "$SSL_DIR/server.key" -out "$SSL_DIR/server.crt"

# Manage django
mkdir -p /app/static
python /app/manage.py collectstatic --no-input

# Link nginx logs to stdout/stderr
ln -sf /dev/stdout /var/log/nginx/access.log
ln -sf /dev/stdout /var/log/nginx/error.log

/etc/init.d/nginx restart

gunicorn fhirquestionnaire.wsgi:application -b 0.0.0.0:8000 --chdir=/app
