from flask import Blueprint, current_app, abort, jsonify
from sqlalchemy.exc import SQLAlchemyError
from redis import RedisError

from .. import cache, __version__
from ..models import User, Resume


module = Blueprint('status', __name__)


@module.route('/stats', methods=['GET'])
@cache.cached()
def main():
    """
    Application's usage statistic, update every 5 minutes

    .. :quickref: stats; Application's usage statistic
    """
    try:
        users = User.query.count()
        resume = Resume.query.count()
        redis = current_app.redis.info('memory')

        result = {
            'providers': [],
            'health': {
                'db': {'current': users + resume, 'max': 10000},
                'cache': {'current': redis['used_memory'], 'max': 25000000}
            },
            'version': __version__
        }

        ResumeUser = Resume.query.join(User)
        for prov in current_app.providers.keys():
            provider = {
                'name': prov,
                'users': User.query.filter_by(provider=prov).count(),
                'resume': ResumeUser.filter(User.provider == prov).count()
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
