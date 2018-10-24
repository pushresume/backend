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
