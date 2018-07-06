"""
Django settings for fhirquestionnaire project.

Generated by 'django-admin startproject' using Django 2.0.6.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import os
import sys
import raven

from django.contrib.messages import constants as message_constants

from fhirquestionnaire import environment

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = environment.ENV_BOOL("DJANGO_DEBUG", False)

ALLOWED_HOSTS = environment.ENV_LIST("ALLOWED_HOSTS")

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
    'contact',
    'bootstrap3',
    'markdown_deux',
    'crispy_forms',
    'health_check',
    'raven.contrib.django.raven_compat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fhirquestionnaire.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = os.environ.get("STATIC_URL", '/static/')
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Crispy forms
CRISPY_TEMPLATE_PACK = 'bootstrap3'

# Authentication
AUTH0_CLIENT_ID_LIST = environment.ENV_LIST("AUTH0_CLIENT_ID_LIST", ",")
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
AUTHENTICATION_LOGIN_URL = os.environ.get("AUTHENTICATION_LOGIN_URL")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN")
SCIAUTH_BRANDING = {
    'title': 'People-Powered Medicine',
    'description': 'People-Powered Medicine (PPM) is a project that aims to gather as much information'
                   ' as possible about individuals with particular conditions into one secure '
                   'research database.',
    'icon_url': 'https://peoplepoweredmedicine.org/img/ppm_RGB_115x30.svg',
}

# App configurations
FHIR_APP_ID = os.environ.get("FHIR_APP_ID")
FHIR_URL = os.environ.get("FHIR_URL")
RETURN_URL = os.environ.get("RETURN_URL")

# Get email details and enable SSL for SSL backend
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", 'django_smtp_ssl.SSLEmailBackend')
EMAIL_USE_SSL = EMAIL_BACKEND == 'django_smtp_ssl.SSLEmailBackend'
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
EMAIL_PORT = os.environ.get("EMAIL_PORT")
TEST_EMAIL_ACCOUNTS = os.environ.get("TEST_EMAIL_ACCOUNTS", "")
CONTACT_FORM_RECIPIENTS = os.environ.get('CONTACT_FORM_RECIPIENTS')
DEFAULT_FROM_EMAIL = "ppm-no-reply@dbmi.hms.harvard.edu"

# Check for sentry
RAVEN_URL = os.environ.get("RAVEN_URL")

if RAVEN_URL:
    RAVEN_CONFIG = {
        'dsn': RAVEN_URL,
    }

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '[DJANGO] - [QUESTIONNAIRE] - [%(asctime)s][%(levelname)s]'
                      '[%(name)s.%(funcName)s:%(lineno)d] - %(message)s',
        },
    },
    'handlers': {
        'sentry': {
            'level': 'ERROR', # To capture more than ERROR, change to WARNING, INFO, etc.
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
            'tags': {'custom-tag': 'x'},
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'console',
            'stream': sys.stdout,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'raven': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False,
        },
        'sentry.errors': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}