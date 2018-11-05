from logging import getLogger
from datetime import timedelta

from redis import Redis
from flask import Flask
from flask_cors import CORS
from flask_caching import Cache
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from werkzeug.contrib.fixers import ProxyFix

from .utils import (
    json_in_body, error_handler, jwt_err_handler,
    load_provider, load_controller, load_sentry, load_scout_apm)


__version__ = '0.1.4'

db = SQLAlchemy()
cache = Cache()
migrate = Migrate()
jwt = JWTManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object('config')

    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(  # must be timedelta,
        minutes=int(app.config['JWT_ACCESS_TOKEN_EXPIRES']))  # must be here

    external_logger = getLogger('gunicorn.error')
    if len(external_logger.handlers) > 0:
        app.logger.setLevel(external_logger.level)
        app.logger.handlers = external_logger.handlers

    db.init_app(app)
    cache.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r'/*': {'origins': app.config['FRONTEND_URL']}})

    jwt.init_app(app)
    jwt.invalid_token_loader(lambda m: jwt_err_handler(f'Invalid token: {m}'))
    jwt.revoked_token_loader(lambda: jwt_err_handler('Token has been revoked'))
    jwt.expired_token_loader(lambda: jwt_err_handler('Token has expired'))
    jwt.user_loader_error_loader(lambda m: jwt_err_handler(m))
    jwt.unauthorized_loader(lambda m: jwt_err_handler(m))

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.redis = Redis.from_url(app.config['REDIS_URL'])

    app.before_request(json_in_body)
    app.register_error_handler(Exception, error_handler)

    for provider in app.config['PROVIDERS']:
        load_provider(app, provider)

    with app.app_context():
        for controller in app.config['CONTROLLERS']:
            load_controller(app, controller)

    if app.config['SENTRY_DSN']:
        load_sentry(app)

    if app.config['SCOUT_KEY']:
        load_scout_apm(app, db)

    try:
        cache.clear()
    except Exception as e:
        app.logger.warning(f'Cache clean error: {e}')

    app.logger.info(f'PushResume {__version__} startup')

    return app
