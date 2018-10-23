from functools import wraps
from importlib import import_module

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


def json_in_body():
    data_methods = ['POST', 'PUT', 'PATCH', 'DELETE']
    if request.method in data_methods and not request.is_json:
        return abort(400, 'Invalid JSON')


def error_handler(e):
    if not isinstance(e, HTTPException):
        current_app.logger.critical(e, exc_info=1)
        return abort(500, 'Unexpected error')

    msg = {'status': e.code, 'message': e.description, 'error': e.name}
    if e.code == 405:
        msg.update({'allowed': e.valid_methods})
    return jsonify(msg), e.code


def jwt_err_handler(msg):
    message = {'status': 401, 'error': 'Unauthorized', 'message': msg}
    return jsonify(message), 401


def load_provider(app, provider):
    if not getattr(app, 'providers', False):
        app.providers = {}

    if isinstance(app.providers, dict):
        back_url = f'{app.config["FRONTEND_URL"]}/auth/{provider}'
        try:
            mod = import_module(f'app.providers.{provider}')
            app.providers[provider] = mod.Provider(
                name=provider,
                redirect_uri=back_url, **app.config[provider.upper()])
        except Exception as e:
            app.logger.exception(f'Provider [{provider}] load failed: {e}')
        else:
            app.logger.info(f'Provider [{provider}] loaded')


def load_controller(app, controller):
    try:
        mod = import_module(f'app.controllers.{controller}')
        app.register_blueprint(mod.module)
    except Exception as e:
        app.logger.exception(f'Controller [{controller}] load failed: {e}')
    else:
        app.logger.info(f'Controller [{controller}] loaded')
