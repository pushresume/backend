from logging import getLogger
from datetime import timedelta

from redis import Redis
from telebot import TeleBot
from flask import Flask
from flask_cors import CORS
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from werkzeug.contrib.fixers import ProxyFix

from .utils import (
    register_telegram_webhook, json_in_body, error_handler, jwt_err_handler,
    load_providers, load_controllers, load_sentry, load_scout_apm)


__version__ = '0.2.0'

db = SQLAlchemy()
cache = Cache()
jwt = JWTManager()


def create_app(config=None):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app)

    app.config.from_object(config or 'config')

    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(  # must be timedelta,
        seconds=int(app.config['JWT_ACCESS_TOKEN_EXPIRES']))  # must be here

    external_logger = getLogger('gunicorn.error')
    if external_logger.handlers:
        app.logger.setLevel(external_logger.level)
        app.logger.handlers = external_logger.handlers

    db.init_app(app)
    cache.init_app(app)
    CORS(app, resources={r'/*': {'origins': app.config['FRONTEND_URL']}})

    jwt.init_app(app)
    jwt.invalid_token_loader(lambda m: jwt_err_handler(f'Invalid token: {m}'))
    jwt.revoked_token_loader(lambda: jwt_err_handler('Token has been revoked'))
    jwt.expired_token_loader(lambda: jwt_err_handler('Token has expired'))
    jwt.user_loader_error_loader(lambda m: jwt_err_handler(m))
    jwt.unauthorized_loader(lambda m: jwt_err_handler(m))

    app.bot = TeleBot(app.config['TELEGRAM_TOKEN'], threaded=False)
    app.redis = Redis.from_url(
        app.config['REDIS_URL'],
        max_connections=app.config['REDIS_MAX_CONNECTIONS'])

    app.before_request(json_in_body)
    app.register_error_handler(Exception, error_handler)

    load_providers(app)

    with app.app_context():
        load_controllers(app)

    if app.config['SENTRY_DSN']:
        load_sentry(app)

    if app.config['SCOUT_KEY']:
        load_scout_apm(app, db)

    register_telegram_webhook(app)

    try:
        cache.clear()
    except Exception as e:
        app.logger.warning(f'Cache clean error: {e}')

    app.logger.info(f'PushResume {__version__} startup')

    return app
