from uuid import uuid4
from logging import getLogger
from datetime import timedelta
from importlib import import_module

import sentry_sdk
from redis import Redis
from celery import Celery
from telebot import TeleBot
from flask import Flask
from flask_cors import CORS
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from werkzeug.contrib.fixers import ProxyFix
from sentry_sdk.integrations.flask import FlaskIntegration

import config
from .utils import telegram_webhook, is_json, error_handler


__version__ = '0.1.1'

db = SQLAlchemy()
cache = Cache()
bot = TeleBot(config.TELEGRAM_TOKEN, threaded=False)


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(  # must be timedelta,
        minutes=int(app.config['JWT_ACCESS_TOKEN_EXPIRES']))  # must be here

    external_logger = getLogger('gunicorn.error')
    if len(external_logger.handlers) > 0:
        app.logger.setLevel(external_logger.level)
        app.logger.handlers = external_logger.handlers

    db.init_app(app)
    cache.init_app(app)
    JWTManager(app)
    CORS(app, resources={r'/*': {'origins': app.config['FRONTEND_URL']}})
    sentry_sdk.init(
        dsn=app.config['SENTRY_DSN'],
        environment='development' if app.debug else 'production',
        integrations=[FlaskIntegration()])

    app.bot = bot
    app.tgsecret = uuid4()
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.redis = Redis.from_url(app.config['REDIS_URL'])
    app.queue = Celery(
        'pushresume',
        backend=app.config['REDIS_URL'],
        broker=app.config['REDIS_URL'])

    app.before_request(is_json)
    app.before_first_request(telegram_webhook)
    app.register_error_handler(Exception, error_handler)

    app.providers = {}
    for prov in app.config['PROVIDERS']:
        try:
            mod = import_module(f'app.providers.{prov}')
            back_url = f'{app.config["FRONTEND_URL"]}/auth/{prov}'
            app.providers[prov] = mod.Provider(
                name=prov, redirect_uri=back_url, **app.config[prov.upper()])
            app.logger.info(f'Provider [{prov}] loaded')
        except Exception as e:
            app.logger.warning(
                f'Provider [{prov}] load failed: {e}', exc_info=1)

    with app.app_context():
        for controller in ['auth', 'resume', 'status', 'notifications']:
            try:
                mod = import_module(f'app.controllers.{controller}')
                app.register_blueprint(mod.module)
                app.logger.info(f'Controller [{controller}] loaded')
            except Exception as e:
                app.logger.error(
                    f'Controller [{controller}] load failed: {e}', exc_info=1)
                continue

    app.logger.info(f'PushResume {__version__} startup')

    cache.clear()

    return app
