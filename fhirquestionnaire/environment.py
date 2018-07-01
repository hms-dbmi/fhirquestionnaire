import os
import json

__all__ = ['BASE_DIR', 'ABS_PATH', 'ENV_BOOL', 'ENV_STR', 'ENV_LIST', 'ENV_DICT']


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

import logging
logger = logging.getLogger(__name__)


def ENV_SETTING(key, default):
    return os.environ.get(key, default)


def ENV_CODE(name, default=0):
    """
    Get a numeric value from environment and convert it accordingly.
    Return default if value does not exist or fails to parse.
    """
    if name not in os.environ:
        return default

    try:
        value = os.environ.get(name, default)
        return int(value)
    except ValueError:
        logger.error('Non-numeric type found for: {}'.format(name))
        return default


def ABS_PATH(*args):  # noqa
    return os.path.join(BASE_DIR, *args)


def ENV_BOOL(name, default=False):  # noqa
    """
    Get a boolean value from environment variable.
    If the environment variable is not set or value is not one or "true" or
    "false", the default value is returned instead.
    """

    if name not in os.environ:
        return default
    if os.environ[name].lower() in ['true', 'yes', '1', 'y']:
        return True
    elif os.environ[name].lower() in ['false', 'no', '0', 'n']:
        return False
    else:
        return default


def ENV_STR(name, default=None):  # noqa
    """
    Get a string value from environment variable.
    If the environment variable is not set, the default value is returned
    instead.
    """

    return os.environ.get(name, default)


def ENV_LIST(name, separator=',', default=None):  # noqa
    """
    Get a list of string values from environment variable.
    If the environment variable is not set, the default value is returned
    instead.
    """
    if default is None:
        default = []

    if name not in os.environ:
        logger.error('Nothing found for: {}'.format(name))
        return default
    return os.environ[name].split(separator)


def ENV_DICT(name, default={}):
    """
    Get JSON encoded string from environment variable and return
    the default if it does not exist.
    """
    if name not in os.environ:
        logger.error('Nothing found for: {}'.format(name))
        return default
    try:
        dict = json.loads(os.environ[name])
        return dict
    except ValueError as e:
        logger.error('Failed to parse value for: {}'.format(name))
        return default
