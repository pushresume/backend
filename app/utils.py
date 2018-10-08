from random import randint
from functools import wraps
from cerberus import Validator

from flask import current_app, abort, request, jsonify
from werkzeug.exceptions import HTTPException


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


def register_telegram_webhook():
    url = current_app.config['BACKEND_URL']
    current_app.logger.info(f'Telegram secret: {current_app.tgsecret}')
    try:
        current_app.bot.remove_webhook()
        if not current_app.debug:
            current_app.bot.set_webhook(
                url=f'{url}/notifications/{current_app.tgsecret}')
    except Exception as e:
        current_app.logger.warning(f'Telegram webhook create failed: {e}')
    else:
        current_app.logger.info('Telegram webhook successfully created')


def json_in_body():
    if request.method == 'POST' and not request.is_json:
        return abort(400, 'Invalid JSON')


def error_handler(e):
    if not isinstance(e, HTTPException):
        if current_app.debug:
            raise e
        current_app.logger.critical(e, exc_info=1)
        return abort(500, 'Unexpected error')

    msg = {'status': e.code, 'message': e.description, 'error': e.name}
    if e.code == 405:
        msg.update({'allowed': e.valid_methods})
    return jsonify(msg), e.code


def generate_confirm_code(length=8):
    return randint(10**(length-1), (10**length)-1)


def jwt_unauth_err(msg):
    message = {'status': 401, 'error': 'Unauthorized', 'message': msg}
    return jsonify(message), 401
