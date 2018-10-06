from flask import Blueprint, current_app, abort, jsonify
from sqlalchemy.exc import SQLAlchemyError
from redis import RedisError

from .. import cache, __version__
from ..models import (
    User, Credential, Resume, Confirmation, Subscription, Notification)


module = Blueprint('status', __name__, url_prefix='/status')


@module.route('/', methods=['GET'])
@cache.cached()
def main():
    """
    Application's usage statistic, update every 5 minutes

    .. :quickref: stats; Application's usage statistic
    """
    try:
        users = User.query.count()
        credentials = Credential.query.count()
        resume = Resume.query.count()
        confirmations = Confirmation.query.count()
        subscriptions = Subscription.query.count()
        notifications = Notification.query.count()
        redis = current_app.redis.info('memory')

        rows = users + credentials + resume
        rows += confirmations + subscriptions + notifications

        result = {
            'providers': [],
            'health': {
                'database': {
                    'current': rows,
                    'max': current_app.config['MAX_DATABASE_ROWS']
                },
                'cache': {
                    'current': redis['used_memory'],
                    'max': current_app.config['MAX_REDIS_MEMORY']
                }
            },
            'version': __version__
        }

        for prov in current_app.providers.keys():
            provider = {
                'name': prov,
                'users': Credential.query.filter_by(provider=prov).count(),
                'resume': Resume.query.filter_by(provider=prov).count()
            }
            result['providers'].append(provider)

    except RedisError as e:
        current_app.logger.error(f'Redis error: {e}')
        return abort(503, 'Redis unavailable')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(503, 'Database error')

    else:
        return jsonify(result)
