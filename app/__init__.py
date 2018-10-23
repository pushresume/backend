from logging import getLogger
from datetime import timedelta
from importlib import import_module

from redis import Redis
from celery import Celery
from flask import Flask, jsonify, abort
from flask_cors import CORS
from flask_caching import Cache
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.exceptions import HTTPException


__version__ = '0.1.1'

db = SQLAlchemy()
cache = Cache()
migrate = Migrate()


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
    JWTManager(app)

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.redis = Redis.from_url(app.config['REDIS_URL'])
    app.queue = Celery(
        'pushresume',
        backend=app.config['REDIS_URL'],
        broker=app.config['REDIS_URL'])

    @app.errorhandler(Exception)
    def error_handler(e):
        if not isinstance(e, HTTPException):
            if app.debug:
                raise e
            app.logger.critical(e, exc_info=1)
            return abort(500, type(e).__name__)

        msg = {'status': e.code, 'message': e.description, 'error': e.name}
        if e.code == 405:
            msg.update({'allowed': e.valid_methods})
        return jsonify(msg), e.code

    app.providers = {}
    for prov in app.config['PROVIDERS']:
        try:
            mod = import_module(f'app.providers.{prov}')
            back_url = f'{app.config["FRONTEND_URL"]}/auth/{prov}'
            app.providers[prov] = mod.Provider(
                name=prov, redirect_uri=back_url, **app.config[prov.upper()])
            app.logger.info(f'Provider [{prov}] loaded')
        except Exception as e:
            app.logger.warn(f'Provider [{prov}] load failed: {e}', exc_info=1)

    from .views import module
    app.register_blueprint(module)

    app.logger.info(f'PushResume {__version__} startup')

    return app
