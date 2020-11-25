"""
Django settings for fhirquestionnaire project.

Generated by 'django-admin startproject' using Django 2.0.6.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import os
import logging

from django.contrib.messages import constants as message_constants

from dbmi_client import logging as dbmi_logging
from dbmi_client.environment import get_bool, get_str, get_int, get_list

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_str("SECRET_KEY", required=True)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = get_list("ALLOWED_HOSTS", required=True)

# Set the message level
MESSAGE_LEVEL = message_constants.INFO if not DEBUG else message_constants.DEBUG

# Application definition

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'questionnaire.apps.QuestionnaireConfig',
    'consent.apps.ConsentConfig',
    'contact',
    'bootstrap3',
    'crispy_forms',
    'health_check',
    'raven.contrib.django.raven_compat',
    'dbmi_client',
    'api',
    'pdf',
    'bootstrap_datepicker_plus',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'dbmi_client.middleware.DBMIJWTAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fhirquestionnaire.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, "templates"),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fhirquestionnaire.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Configure sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_DOMAIN = get_str('COOKIE_DOMAIN', required=True)
SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_SECURE = not get_bool('DJANGO_DEBUG', default=False)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = get_str("STATIC_URL", default='/static/')
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "staticfiles"),
]

# Use the DBMI Client Admin-only model backend
AUTHENTICATION_BACKENDS = ['dbmi_client.authn.DBMIJWTAdminAuthenticationBackend', ]

DBMI_CLIENT_CONFIG = {
    'CLIENT': 'ppm',
    'ENVIRONMENT': get_str('DBMI_ENV', required=True),
    'ENABLE_LOGGING': True,
    'LOG_LEVEL': get_int('DBMI_LOG_LEVEL', default=logging.WARNING),

    # AuthZ
    'AUTHZ_ADMIN_GROUP': 'ppm-admins',
    'AUTHZ_ADMIN_PERMISSION': 'ADMIN',
    'JWT_COOKIE_DOMAIN': get_str('COOKIE_DOMAIN', required=True),

    # Auth0
    'AUTH0_TENANT': get_str('AUTH0_TENANT', required=True),
    'AUTH0_CLIENT_ID': get_str('AUTH0_CLIENT_ID', required=True),
    'AUTHN_TITLE': 'People-Powered Medicine',
    'AUTHN_ICON_URL': 'https://peoplepoweredmedicine.org/img/ppm_RGB_115x30.svg',

    # Misc
    'DRF_OBJECT_OWNER_KEY': 'email',
}

# Api settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'fhirquestionnaire.ppmauth.PPMAdminOrOwnerPermission',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'dbmi_client.authn.DBMIUser',
    ),
}

# App configurations
FHIR_APP_ID = get_str("FHIR_APP_ID", required=True)
FHIR_URL = get_str("FHIR_URL", required=True)
RETURN_URL = get_str("RETURN_URL", required=True)
PPM_P2MD_URL = get_str("PPM_P2MD_URL", required=True)

# Crispy forms
CRISPY_TEMPLATE_PACK = 'bootstrap3'

# Get email details and enable SSL for SSL backend
EMAIL_BACKEND = get_str("EMAIL_BACKEND", 'django_smtp_ssl.SSLEmailBackend')
EMAIL_USE_SSL = EMAIL_BACKEND == 'django_smtp_ssl.SSLEmailBackend'
EMAIL_HOST = get_str("EMAIL_HOST", required=True)
EMAIL_HOST_USER = get_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = get_str("EMAIL_HOST_PASSWORD")
EMAIL_PORT = get_str("EMAIL_PORT")
TEST_EMAIL_ACCOUNTS = get_str("TEST_EMAIL_ACCOUNTS", "")
CONTACT_FORM_RECIPIENTS = get_str('CONTACT_FORM_RECIPIENTS', required=True)
DEFAULT_FROM_EMAIL = "ppm-no-reply@dbmi.hms.harvard.edu"

# Check for sentry
RAVEN_URL = get_str("RAVEN_URL", required=True)
if RAVEN_URL:
    RAVEN_CONFIG = {
        'dsn': RAVEN_URL,
    }

# Output the standard logging configuration
LOGGING = dbmi_logging.config('QUESTIONNAIRE', sentry=True, root_level=logging.DEBUG)
