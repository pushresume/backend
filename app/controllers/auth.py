from datetime import datetime, timedelta

from flask import Blueprint, current_app, abort, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, jwt_optional, get_jwt_identity)

from .. import db
from ..models import User
from ..providers import ProviderError
from ..utils import validation_required


module = Blueprint('auth', __name__, url_prefix='/auth')


@module.route('/providers', methods=['GET'])
def providers():
    """
    Providers list

    .. :quickref: auth; Retrieve providers list

    **Request**:

        .. sourcecode:: http

            GET /auth/providers HTTP/1.1

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            [
                "provider_one",
                "provider_two"
            ]

    :statuscode 200: OK
    :statuscode 500: unexpected errors
    """
    return jsonify([key for key in current_app.providers.keys()])


@module.route('/<provider_name>', methods=['GET'])
def redirect(provider_name):
    """
    Returns URL for redirect user to provider's auth page

    .. :quickref: auth; Retrieve redirect URL to provider's auth page

    **Request**:

        .. sourcecode:: http

            GET /auth/<provider_name> HTTP/1.1

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "redirect": "http://<provider's_auth_page>"
            }

    :statuscode 200: OK
    :statuscode 500: unexpected errors
    :statuscode 503: provider errors
    """
    provider = current_app.providers.get(provider_name.lower(), None)

    if not provider:
        return abort(404, 'Provider not found')

    return jsonify(redirect=provider.redirect())


@module.route('/<provider_name>', methods=['POST'])
@jwt_optional
@validation_required({'code': {'type': 'string', 'required': True}})
def login(provider_name):
    """
    Log-in user, returns JWT token for signing future requests
    to protected routes.

    .. :quickref: auth; Retrieve JWT token to access protected routes

    **Request**:

        .. sourcecode:: http

            POST /auth/<provider_name> HTTP/1.1
            Content-Type: application/json

            {
                "code": "qwerty"
            }

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "token": "q1w2.e3r4.t5y"
            }

    :reqjson string code: authorization code from callback

    :statuscode 200: OK
    :statuscode 400: invalid JSON in request's body
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    :statuscode 503: provider errors
    """
    try:
        provider = current_app.providers.get(provider_name.lower(), None)

        if not provider:
            current_app.logger.warning(f'Provider [{provider_name}] not found')
            return abort(404, 'Provider not found')

        code = request.get_json()['code']
        ids = provider.tokenize(code, refresh=False)
        identity = provider.identity(ids['access_token'])

        user = User.query.filter_by(
            uniq=identity, provider=provider.name).first()
        if not user:
            user = User(uniq=identity, provider=provider.name)

        user.access = ids['access_token']
        user.refresh = ids['refresh_token']
        user.expires = datetime.utcnow() + timedelta(seconds=ids['expires_in'])

        db.session.add(user)
        db.session.commit()

    except ProviderError as e:
        current_app.logger.error(f'Login error: {e}')
        return abort(503, 'Provider error')

    else:
        current_app.logger.info(f'Logged in: {user}')
        return jsonify(token=create_access_token(user.id))


@module.route('/refresh', methods=['GET'])
@jwt_required
def refresh():
    """
    Returns new JWT token with fresh expiration date

    .. :quickref: auth; Refresh exists JWT token (reset TTL)

    **Request**:

        .. sourcecode:: http

            GET /auth/refresh HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "token": "q1w2.e3r4.t5y"
            }

    :reqheader Authorization: valid JWT token

    :statuscode 200: OK
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    """
    user_id = get_jwt_identity()
    token = create_access_token(user_id)
    return jsonify(token=token)
