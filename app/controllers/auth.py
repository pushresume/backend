from datetime import datetime, timedelta

from flask import Blueprint, current_app, abort, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, jwt_optional, get_jwt_identity)

from .. import db
from ..models import User, Account
from ..providers import ProviderError
from ..utils import validation_required


module = Blueprint('auth', __name__, url_prefix='/auth')


@module.route('/providers', methods=['GET'])
def providers():
    """
    Список провайдеров, через которых доступна авторизация для пользователей.
    Используется в */auth/<provider>*

    .. :quickref: auth; Список провайдеров

    **Пример запроса**:

        .. sourcecode:: http

            GET /auth/providers HTTP/1.1

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            [
                "provider_one",
                "provider_two"
            ]

    :statuscode 200: OK
    :statuscode 500: ошибки бэкенда
    """
    return jsonify([key for key in current_app.providers.keys()])


@module.route('/<provider_name>', methods=['GET'])
def redirect(provider_name):
    """
    Возвращает URL для последующего редиректа пользователя на страницу
    авторизации провайдера

    .. :quickref: auth; Адрес страницы авторизации провайдера

    **Пример запроса**:

        .. sourcecode:: http

            GET /auth/<provider_name> HTTP/1.1

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "redirect": "http://<provider's_auth_page>"
            }

    :statuscode 200: OK
    :statuscode 500: ошибки бэкенда
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
    Логин пользователя.
    Обмен *code* из обратного редиректа провайдера на JWT-токен

    .. :quickref: auth; Логин пользователя, получение JWT-токена

    **Пример запроса**:

        .. sourcecode:: http

            POST /auth/<provider_name> HTTP/1.1
            Content-Type: application/json

            {
                "code": "qwerty"
            }

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "token": "q1w2.e3r4.t5y"
            }

    :reqjson string code: код, возвращаемый провайдером после авторизации

    :statuscode 200: OK
    :statuscode 400: невалидный JSON в теле запроса
    :statuscode 500: ошибки бэкенда
    :statuscode 503: ошибки взаимодействия с провайдером
    """
    try:
        provider = current_app.providers.get(provider_name.lower(), None)
        if not provider:
            current_app.logger.warning(f'Provider [{provider_name}] not found')
            return abort(404, 'Provider not found')

        code = request.get_json()['code']
        ids = provider.tokenize(code, refresh=False)
        identity = provider.identity(ids['access_token'])

        account = Account.query.filter_by(identity=identity).first()

        user_id = get_jwt_identity()
        if user_id:
            user = User.query.get(user_id)
        else:
            user = None

        if account and user:
            account.owner = user

        elif account and not user:
            user = account.owner

        elif not account:
            if not user:
                user = User()
            account = Account(identity=identity, owner=user)

        account.provider = provider.name
        account.access = ids['access_token']
        account.refresh = ids['refresh_token']

        delta = timedelta(seconds=ids['expires_in'])
        account.expires = datetime.utcnow() + delta

        db.session.add(user)
        db.session.add(account)
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
    Обмен текущего JWT-токена на новый,
    используется для продления срока жизни токена

    .. :quickref: auth; Обновление токена

    **Пример запроса**:

        .. sourcecode:: http

            GET /auth/refresh HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "token": "q1w2.e3r4.t5y"
            }

    :reqheader Authorization: действующий JWT-токен

    :statuscode 200: OK
    :statuscode 401: ошибки авторизации/проблемы с токеном
    :statuscode 500: ошибки бэкенда
    """
    user_id = get_jwt_identity()
    token = create_access_token(user_id)
    return jsonify(token=token)
