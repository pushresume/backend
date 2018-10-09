from flask import Blueprint, current_app, abort, jsonify
from sqlalchemy.exc import SQLAlchemyError
from redis import RedisError

from .. import cache, __version__
from ..models import (
    User, Account, Resume, Confirmation, Subscription, Notification)


module = Blueprint('status', __name__)


@module.route('/', methods=['GET'])
def about():
    """
    Версия приложения

    .. :quickref: status; Версия приложения

    **Пример запроса**:

        .. sourcecode:: http

            GET / HTTP/1.1

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "version": "1.2.3"
            }

    :statuscode 200: OK
    :statuscode 500: ошибки бэкенда
    """
    return jsonify(version=__version__)


@module.route('/status', methods=['GET'])
@cache.cached()
def main():
    """
    Состояние и статистика приложения

    .. :quickref: status; Статистика приложения

    **Пример запроса**:

        .. sourcecode:: http

            GET /status HTTP/1.1

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "health": {
                    "cache": {
                        "current": 123,
                        "max": 100500
                    },
                    "database": {
                        "current": 456,
                        "max": 500100
                    }
                },
                "statistics": [
                    {
                        "provider": "provider_one",
                        "accounts": 123,
                        "resume": 456
                    },
                    {
                        "provider": "provider_two",
                        "accounts": 456,
                        "resume": 123
                    }
                ]
            }

    :statuscode 200: OK
    :statuscode 500: ошибки бэкенда
    """
    try:
        users = User.query.count()
        accounts = Account.query.count()
        resume = Resume.query.count()
        confirmations = Confirmation.query.count()
        subscriptions = Subscription.query.count()
        notifications = Notification.query.count()
        redis = current_app.redis.info('memory')

        rows = users + accounts + resume
        rows += confirmations + subscriptions + notifications

        result = {
            'statistics': [],
            'health': {
                'database': {
                    'current': rows,
                    'max': current_app.config['MAX_DATABASE_ROWS']
                },
                'cache': {
                    'current': redis['used_memory'],
                    'max': current_app.config['MAX_REDIS_MEMORY']
                }
            }
        }

        joined = Resume.query.join(Account)
        for prov in current_app.providers.keys():
            provider = {
                'provider': prov,
                'accounts': Account.query.filter_by(provider=prov).count(),
                'resume': joined.filter(Account.provider == prov).count()
            }
            result['statistics'].append(provider)

    except RedisError as e:
        current_app.logger.error(f'Redis error: {e}')
        return abort(503, 'Redis unavailable')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(503, 'Database error')

    else:
        return jsonify(result)
