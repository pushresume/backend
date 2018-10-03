from uuid import uuid4
from functools import wraps

from flask import Blueprint, current_app, abort, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity)
from cerberus import Validator
from sqlalchemy.exc import SQLAlchemyError
from redis import RedisError
from telebot import types

from . import cache, bot
from .providers import ProviderError
from .controllers import (
    UserController, ResumeController, StatsController,
    OTPController, SubscriptionController)


module = Blueprint('pushresume', __name__)

telegram_secret = uuid4()


def validation_required(schema):
    def wrapper(func):
        @wraps(func)
        def decorator(*args, **kwargs):
            validator = Validator(schema)
            normalized = validator.normalized(request.get_json())
            if not validator.validate(normalized):
                return abort(400, validator.errors)
            return func(*args, **kwargs)
        return decorator
    return wrapper


@module.before_app_first_request
def cache_clean():
    try:
        cache.clear()
    except Exception as e:
        current_app.logger.warning(f'Cache clean failed: {e}')
    else:
        current_app.logger.info('Cache clean successfully')


@module.before_app_first_request
def telegram_webhook():
    url = current_app.config['BACKEND_URL']
    current_app.logger.info(f'Telegram secret: {telegram_secret}')
    try:
        bot.remove_webhook()
        if not current_app.debug:
            bot.set_webhook(url=f'{url}/notif/tg/{telegram_secret}')
    except Exception as e:
        current_app.logger.warning(f'Telegram webhook create failed: {e}')
    else:
        current_app.logger.info('Telegram webhook successfully created')


@module.before_request
def before_request_handler():
    if request.method == 'POST' and not request.is_json:
        return abort(400, 'Invalid JSON')


@module.route('/auth/providers', methods=['GET'])
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


@module.route('/auth/<provider_name>', methods=['GET'])
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


@module.route('/auth/<provider_name>', methods=['POST'])
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

        user_controller = UserController(provider)
        code = request.get_json()['code']
        user = user_controller.auth(code=code)

    except ProviderError as e:
        current_app.logger.error(f'Login error: {e}')
        return abort(503, 'Provider error')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(503, 'Database error')

    else:
        current_app.logger.info(f'Logged in: {user}')
        return jsonify(token=create_access_token(user.id))


@module.route('/auth/refresh', methods=['GET'])
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


@module.route('/resume', methods=['GET'])
@jwt_required
def resume():
    """
    User's resume list

    .. :quickref: protected; Retrieve user's resume list directly from provider

    **Request**:

        .. sourcecode:: http

            GET /refresh HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            [
                {
                    "enabled": true,
                    "link": "https://<provider's resume page>",
                    "name": "John Doe",
                    "published": "2018-08-19T17:41:52+0300",
                    "title": "Proctologist-jeweler",
                    "uniq": "erwhy2333r23rd2r32er23"
                }
            ]

    :reqheader Authorization: valid JWT token

    :statuscode 200: OK
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    :statuscode 503: provider errors
    """
    try:
        user_id = get_jwt_identity()
        resume = ResumeController.fetch(user_id)

    except ProviderError as e:
        current_app.logger.error(f'Resume error: {e}')
        return abort(503, 'Provider error')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(503, 'Database error')

    else:
        return jsonify(resume)


@module.route('/resume', methods=['POST'])
@jwt_required
@validation_required({'uniq': {'type': 'string', 'required': True}})
def toggle():
    """
    Enable/disable automatically publish user's resume

    .. :quickref: protected; Toggle automatically publish user's resume

    **Request**:

        .. sourcecode:: http

            POST /resume HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y
            Content-Type: application/json

            {
                "uniq": "q1w2e3r4t5y6"
            }

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "enabled": true
            }

    :reqjson string uniq: provider's resume id

    :statuscode 200: OK
    :statuscode 400: invalid JSON in request's body
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    """
    try:
        user_id = get_jwt_identity()
        uniq = request.get_json()['uniq']
        resume = ResumeController.toggle(user_id, uniq)

        if not resume:
            return abort(404, 'Resume not found')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(500, 'Database error')

    else:
        current_app.logger.info(f'Resume toggled: {resume}')
        return jsonify(enabled=resume.enabled)


@module.route('/stats', methods=['GET'])
@cache.cached()
def stats():
    """
    Application's usage statistic, update every 5 minutes

    .. :quickref: stats; Application's usage statistic
    """
    try:
        stats = StatsController.stats()

    except RedisError as e:
        current_app.logger.error(f'Redis error: {e}')
        return abort(503, 'Redis error')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(503, 'Database error')

    else:
        return jsonify(stats)


@module.route('/notif/otp', methods=['POST'])
@jwt_required
@validation_required({
    'channel': {'type': 'string', 'required': True, 'allowed': ['telegram']}})
def otp():
    """
    Returns OTP code

    .. :quickref: notif; Generate OTP code for channel

    **Request**:

        .. sourcecode:: http

            POST /notif/otp HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y
            Content-Type: application/json

            {
                "channel": "<channel_type>"
            }

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "code": "12345678"
            }

    :reqheader Authorization: valid JWT token

    :statuscode 200: OK
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    """
    user_id = get_jwt_identity()

    post_data = request.get_json()
    channel = post_data['channel']

    otp_controller = OTPController()
    otp = otp_controller.create(user_id, channel)

    return jsonify(code=otp.code)


@module.route('/notif/subscriptions', methods=['GET'])
@jwt_required
def subscriptions():
    """
    Returns list of user subscriptions

    .. :quickref: notif; Generate OTP code

    **Request**:

        .. sourcecode:: http

            GET /notif/subscriptions HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            [
                {
                    "channel": "<channel_type_1>",
                    "enabled": true
                },
                {
                    "channel": "<channel_type_2>",
                    "enabled": false
                }
            ]

    :reqheader Authorization: valid JWT token

    :statuscode 200: OK
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    """
    user_id = get_jwt_identity()
    sub_controller = SubscriptionController()
    subscriptions = sub_controller.fetch(user_id)

    return jsonify(subscriptions)


@module.route(f'/notif/tg/{telegram_secret}', methods=['POST'])
def webhook():
    try:
        post_data = request.get_json()
        update = types.Update.de_json(post_data)
        bot.process_new_updates([update])
    except Exception as e:
        current_app.logger.error(f'Read telegram updates failed: {e}')
    finally:
        return '', 200


@bot.message_handler(commands=['start'])
def command_start(msg):
    bot.send_message(msg.chat.id, 'Please, enter the OTP code')


@bot.message_handler(regexp='^[0-9]{8}$')
def validate_otp(msg):
    otp_controller = OTPController()
    user_id = otp_controller.validate(msg.text, 'telegram')

    if not user_id:
        bot.send_message(msg.chat.id, 'Invalid OTP code')
        return

    sub_controller = SubscriptionController()
    sub = sub_controller.create(user_id, msg.chat.id, 'telegram')

    if sub:
        bot.send_message(
            msg.chat.id, 'Success. You may enable notifications on site')
        return

    bot.send_message(msg.chat.id, 'Something wrong, subscription not created')


@bot.message_handler(func=lambda msg: True)
def invalid_message(msg):
    return_text = 'Invalid message'
    current_app.logger.debug(f'{return_text}: {msg.text}')
    bot.send_message(msg.chat.id, return_text)
