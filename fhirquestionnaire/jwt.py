import jwt
import furl
import base64
import json
from jwcrypto import jwk
import requests

from django.conf import settings
from django.shortcuts import redirect

import logging
logger = logging.getLogger(__name__)


def dbmi_jwt(function):
    def wrap(request, *args, **kwargs):

        # Validates the JWT and returns its payload if valid.
        jwt_payload = validate_request(request)

        # Check for a JWT
        if jwt_payload is not None:

            return function(request, *args, **kwargs)

        else:
            logger.warning('No JWT, redirecting to login')

            # Redirect to login
            return authentication_redirect(request)

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


def dbmi_jwt_payload(request):

    # Validates the JWT and returns its payload if valid.
    return validate_request(request)


def validate_request(request):

    # Extract JWT token into a string.
    jwt_string = request.COOKIES.get("DBMI_JWT", None)

    # Check that we actually have a token.
    if jwt_string is not None:
        return validate_rs256_jwt(jwt_string)
    else:
        return None


def retrieve_public_key(jwt_string):

    try:
        # Get the JWK
        jwks = get_public_keys_from_auth0(refresh=False)

        # Decode the JWTs header component
        unverified_header = jwt.get_unverified_header(str(jwt_string))

        # Check the JWK for the key the JWT was signed with
        rsa_key = get_rsa_from_jwks(jwks, unverified_header['kid'])
        if not rsa_key:
            logger.debug('No matching key found in JWKS, refreshing')
            logger.debug('Unverified JWT key id: {}'.format(unverified_header['kid']))
            logger.debug('Cached JWK keys: {}'.format([jwk['kid'] for jwk in jwks['keys']]))

            # No match found, refresh the jwks
            jwks = get_public_keys_from_auth0(refresh=True)
            logger.debug('Refreshed JWK keys: {}'.format([jwk['kid'] for jwk in jwks['keys']]))

            # Try it again
            rsa_key = get_rsa_from_jwks(jwks, unverified_header['kid'])
            if not rsa_key:
                logger.error('No matching key found despite refresh, failing')

        return rsa_key

    except KeyError as e:
        logger.debug('Could not compare keys, probably old HS256 session')
        logger.exception(e)

    return None


def get_rsa_from_jwks(jwks, jwt_kid):

    # Build the dict containing rsa values
    for key in jwks["keys"]:
        if key["kid"] == jwt_kid:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }

            return rsa_key

    # No matching key found, must refresh JWT keys
    return None


def get_public_keys_from_auth0(refresh=False):

    # If refresh, delete cached key
    if refresh:
        delattr(settings, 'AUTH0_JWKS')

    try:
        # Look in settings
        if hasattr(settings, 'AUTH0_JWKS'):
            logger.debug('Using cached JWKS')

            # Parse the cached dict and return it
            return json.loads(settings.AUTH0_JWKS)

        else:

            logger.debug('Fetching remote JWKS')

            # Make the request
            response = requests.get("https://" + settings.AUTH0_DOMAIN + "/.well-known/jwks.json")
            response.raise_for_status()

            # Parse it
            jwks = response.json()

            # Cache it
            setattr(settings, 'AUTH0_JWKS', json.dumps(jwks))

            return jwks

    except KeyError as e:
        logging.exception(e)

    except json.JSONDecodeError as e:
        logging.exception(e)

    except requests.HTTPError as e:
        logging.exception(e)

    return None


def validate_rs256_jwt(jwt_string):

    rsa_pub_key = retrieve_public_key(jwt_string)
    payload = None

    if rsa_pub_key:
        try:
            jwk_key = jwk.JWK(**rsa_pub_key)
        except jwk.InvalidJWKValue as e:
            logger.exception(e)

        # Determine which Auth0 Client ID (aud) this JWT pertains to.
        try:
            auth0_client_id = str(jwt.decode(jwt_string, verify=False)['aud'])
        except Exception as e:
            logger.error('Failed to get the aud from jwt payload')
            return None

        # Check that the Client ID is in the allowed list of Auth0 Client IDs for this application
        allowed_auth0_client_id_list = settings.AUTH0_CLIENT_ID_LIST
        if auth0_client_id not in allowed_auth0_client_id_list:
            logger.error('Auth0 Client ID not allowed')
            return None

        # Attempt to validate the JWT (Checks both expiry and signature)
        try:
            payload = jwt.decode(jwt_string,
                                 jwk_key.export_to_pem(private_key=False),
                                 algorithms=['RS256'],
                                 leeway=120,
                                 audience=auth0_client_id)

        except jwt.InvalidTokenError as err:
            logger.error(str(err))
            logger.error("Invalid JWT Token.")
            payload = None

    return payload


def authentication_redirect(request):
    """
    This will log a user out and redirect them to log in again via the AuthN server.
    :param request:
    :return: The response object that takes the user to the login page. 'next' parameter set to bring them back to their intended page.
    """

    # Build the URL
    login_url = furl.furl(settings.AUTHENTICATION_LOGIN_URL)
    login_url.query.params.add('next', request.build_absolute_uri())

    # Check for branding
    if hasattr(settings, 'SCIAUTH_BRANDING'):
        logger.debug('SciAuth branding passed')

        # Encode it and pass it
        branding = base64.urlsafe_b64encode(json.dumps(settings.SCIAUTH_BRANDING).encode('utf-8')).decode('utf-8')
        login_url.query.params.add('branding', branding)

    # Set the URL and purge cookies
    response = redirect(login_url.url)
    response.delete_cookie('DBMI_JWT', domain=settings.COOKIE_DOMAIN)
    logger.debug('Redirecting to: {}'.format(login_url.url))

    return response