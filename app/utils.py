from random import randint
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


def register_telegram_webhook(app):
    url = app.config['BACKEND_URL']
    secret = app.config['TELEGRAM_WEBHOOK']
    app.logger.info(f'Telegram secret: {secret}')
    try:
        app.bot.remove_webhook()
        if not app.debug:
            app.bot.set_webhook(url=f'{url}/notifications/{secret}')
    except Exception as e:
        app.logger.warning(f'Telegram webhook create failed: {e}')
    else:
        app.logger.info('Telegram webhook successfully created')


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


def generate_confirm_code(length=8):
    return randint(10**(length-1), (10**length)-1)


def jwt_err_handler(msg):
    message = {'status': 401, 'error': 'Unauthorized', 'message': msg}
    return jsonify(message), 401


def load_providers(app):
    app.providers = {}
    for prov in app.config['PROVIDERS']:
        back_url = f'{app.config["FRONTEND_URL"]}/auth/{prov}'
        try:
            mod = import_module(f'app.providers.{prov}')
            app.providers[prov] = mod.Provider(
                name=prov, redirect_uri=back_url, **app.config[prov.upper()])
        except Exception as e:
            app.logger.error(f'Provider [{prov}] load failed: {e}', exc_info=1)
            continue
        else:
            app.logger.info(f'Provider [{prov}] loaded')


def load_controllers(app):
    for controller in app.config['CONTROLLERS']:
        try:
            mod = import_module(f'app.controllers.{controller}')
            app.register_blueprint(mod.module)
        except Exception as e:
            app.logger.error(
                f'Controller [{controller}] load failed: {e}', exc_info=1)
            continue
        else:
            app.logger.info(f'Controller [{controller}] loaded')


def _get_logger(app, celery=False):
    if celery:
        from celery.utils.log import get_task_logger
        return get_task_logger(__name__)
    return app.logger


def load_sentry(app, celery=False):
    logger = _get_logger(app, celery)
    try:
        import sentry_sdk
        if celery:
            from sentry_sdk.integrations.celery import CeleryIntegration as ext
        else:
            from sentry_sdk.integrations.flask import FlaskIntegration as ext

        sentry_sdk.init(
            dsn=app.config['SENTRY_DSN'],
            environment='development' if app.debug else 'production',
            integrations=[ext()])
    except ImportError:
        logger.warning('Sentry modules not found')
    else:
        logger.info('Sentry initialized')


def load_scout_apm(app, db, celery=False):
    logger = _get_logger(app, celery)
    try:
        if celery:
            import scout_apm.celery
            from scout_apm.api import Config
            Config.set(
                key=app.config['SCOUT_KEY'],
                monitor=app.config['SCOUT_MONITOR'],
                name=app.config['SCOUT_NAME'])
            scout_apm.celery.install()
        else:
            from scout_apm.flask import ScoutApm
            from scout_apm.flask.sqlalchemy import instrument_sqlalchemy
            ScoutApm(app)
            instrument_sqlalchemy(db)
    except ImportError:
        logger.warning('Scout APM modules not found')
    else:
        logger.info('Scout APM initialized')
